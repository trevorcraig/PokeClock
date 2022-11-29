# SPDX-FileCopyrightText: 2020 Phillip Burgess for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
Poke CLOCK for Adafruit Matrix Portal: displays current time,
 your favorite pokemon. Requires WiFi internet access.

Written by Trevor Craig

BDF fonts from the X.Org project. 
"""

# pylint: disable=import-error
import gc
import time
import math
import board
import busio

import displayio
from rtc import RTC
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_bitmap_font import bitmap_font
import adafruit_display_text.label
import adafruit_lis3dh
from config import *
from utils import getrandom, hh_mm, parse_time, update_time, PokeData

try:
    from secrets import secrets
except ImportError:
    print('WiFi secrets are kept in secrets.py, please add them there!')
    raise
print("Wifi test passed")

# ONE-TIME INITIALIZATION --------------------------------------------------

MATRIX = Matrix(bit_depth=BITPLANES)
print("Guess this is working")
DISPLAY = MATRIX.display
ACCEL = adafruit_lis3dh.LIS3DH_I2C(busio.I2C(board.SCL, board.SDA),
                                   address=0x19)
_ = ACCEL.acceleration # Dummy reading to blow out any startup residue
time.sleep(0.1)
DISPLAY.rotation = (int(((math.atan2(-ACCEL.acceleration.y,
                                     -ACCEL.acceleration.x) + math.pi) /
                         (math.pi * 2) + 0.875) * 4) % 4) * 90

LARGE_FONT = bitmap_font.load_font('/fonts/helvB12.bdf')
SMALL_FONT = bitmap_font.load_font('/fonts/helvR10.bdf')
SYMBOL_FONT = bitmap_font.load_font('/fonts/6x10.bdf')
LARGE_FONT.load_glyphs('0123456789:')
SMALL_FONT.load_glyphs('0123456789:/.%')
SYMBOL_FONT.load_glyphs('\u21A5\u21A7')

# Display group is set up once, then we just shuffle items around later.
# Order of creation here determines their stacking order.
GROUP = displayio.Group()

# Element 0 is a stand-in item, later replaced with the moon phase bitmap
# pylint: disable=bare-except
try:
    #FILENAME = 'moon/splash-' + str(DISPLAY.rotation) + '.bmp'
    FILENAME = 'Splash.bmp'

    # CircuitPython 6 & 7 compatible
    BITMAP = displayio.OnDiskBitmap(open(FILENAME, 'rb'))
    TILE_GRID = displayio.TileGrid(
        BITMAP,
        pixel_shader=getattr(BITMAP, 'pixel_shader', displayio.ColorConverter())
    )

    # # CircuitPython 7+ compatible
    # BITMAP = displayio.OnDiskBitmap(FILENAME)
    # TILE_GRID = displayio.TileGrid(BITMAP, pixel_shader=BITMAP.pixel_shader)

    GROUP.append(TILE_GRID)
except:
    GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0xFF0000,
                                                   text='AWOO'))
    GROUP[0].x = (DISPLAY.width - GROUP[0].bounding_box[2] + 1) // 2
    GROUP[0].y = DISPLAY.height // 2 - 1

# Elements 1-4 are an outline around the moon percentage -- text labels
# offset by 1 pixel up/down/left/right. Initial position is off the matrix,
# updated on first refresh. Initial text value must be long enough for
# longest anticipated string later.
for i in range(4):
    GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0,
                                                   text='99.9%', y=-99))
# Element 5 is the moon percentage (on top of the outline labels)
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0xFFFF00,
                                               text='99.9%', y=-99))
# Element 6 is the current time
GROUP.append(adafruit_display_text.label.Label(LARGE_FONT, color=0x808080,
                                               text='12:00', y=-99))
# Element 7 is the current date
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0x808080,
                                               text='12/31', y=-99))
# Element 8 is a symbol indicating next rise or set
GROUP.append(adafruit_display_text.label.Label(SYMBOL_FONT, color=0x00FF00,
                                               text='x', y=-99))
# Element 9 is the time of (or time to) next rise/set event
GROUP.append(adafruit_display_text.label.Label(SMALL_FONT, color=0x00FF00,
                                               text='12:00', y=-99))
DISPLAY.show(GROUP)

NETWORK = Network(status_neopixel=board.NEOPIXEL, debug=False)
NETWORK.connect()

# LATITUDE, LONGITUDE, TIMEZONE are set up once, constant over app lifetime

# Fetch latitude/longitude from secrets.py. If not present, use
# IP geolocation. This only needs to be done once, at startup!
try:
    LATITUDE = secrets['latitude']
    LONGITUDE = secrets['longitude']
    print('Using stored geolocation: ', LATITUDE, LONGITUDE)
except KeyError:
    LATITUDE, LONGITUDE = (
        NETWORK.fetch_data('http://www.geoplugin.net/json.gp',
                           json_path=[['geoplugin_latitude'],
                                      ['geoplugin_longitude']]))
    print('Using IP geolocation: ', LATITUDE, LONGITUDE)

# Load time zone string from secrets.py, else IP geolocation for this too
# (http://worldtimeapi.org/api/timezone for list).
try:
    TIMEZONE = secrets['timezone'] # e.g. 'America/New_York'
except:
    TIMEZONE = None # IP geolocation

# Set initial clock time, also fetch initial UTC offset while
# here (NOT stored in secrets.py as it may change with DST).
# pylint: disable=bare-except
try:
    DATETIME, UTC_OFFSET = update_time(NETWORK,TIMEZONE)
except:
    DATETIME, UTC_OFFSET = time.localtime(), '+00:00'
LAST_SYNC = time.mktime(DATETIME)

# Poll server for moon data for current 24-hour period and +24 ahead
PERIOD = []
for DAY in range(2):
    #PERIOD.append(MoonData(DATETIME, DAY * 24, UTC_OFFSET))
    PERIOD.append(PokeData(DATETIME, DAY * 24, UTC_OFFSET,LATITUDE,LONGITUDE,NETWORK))
# PERIOD[0] is the current 24-hour time period we're in. PERIOD[1] is the
# following 24 hours. Data is shifted down and new data fetched as days
# expire. Thought we might need a PERIOD[2] for certain circumstances but
# it appears not, that's changed easily enough if needed.


# MAIN LOOP ----------------------------------------------------------------

while True:
    gc.collect()
    NOW = time.time() # Current epoch time in seconds

    # Sync with time server every ~12 hours
    if NOW - LAST_SYNC > 12 * 60 * 60:
        try:
            DATETIME, UTC_OFFSET = update_time(NETWORK,TIMEZONE)
            LAST_SYNC = time.mktime(DATETIME)
            continue # Time may have changed; refresh NOW value
        except:
            # update_time() can throw an exception if time server doesn't
            # respond. That's OK, keep running with our current time, and
            # push sync time ahead to retry in 30 minutes (don't overwhelm
            # the server with repeated queries).
            LAST_SYNC += 30 * 60 # 30 minutes -> seconds

    # If PERIOD has expired, move data down and fetch new +24-hour data
    if NOW >= PERIOD[1].midnight:
        PERIOD[0] = PERIOD[1]
        #PERIOD[1] = MoonData(time.localtime(), 24, UTC_OFFSET)
        PERIOD[1] = PokeData(time.localtime(), 24, UTC_OFFSET,LATITUDE,LONGITUDE,NETWORK)

    # Determine weighting of tomorrow's phase vs today's, using current time
    RATIO = ((NOW - PERIOD[0].midnight) /
             (PERIOD[1].midnight - PERIOD[0].midnight))
    # Determine moon phase 'age'
    # 0.0  = new moon
    # 0.25 = first quarter
    # 0.5  = full moon
    # 0.75 = last quarter
    # 1.0  = new moon
    if PERIOD[0].age < PERIOD[1].age:
        AGE = (PERIOD[0].age +
               (PERIOD[1].age - PERIOD[0].age) * RATIO) % 1.0
    else: # Handle age wraparound (1.0 -> 0.0)
        # If tomorrow's age is less than today's, it indicates a new moon
        # crossover. Add 1 to tomorrow's age when computing age delta.
        AGE = (PERIOD[0].age +
               (PERIOD[1].age + 1 - PERIOD[0].age) * RATIO) % 1.0

    # AGE can be used for direct lookup to moon bitmap (0 to 99) -- these
    # images are pre-rendered for a linear timescale (solar terminator moves
    # nonlinearly across sphere).
    FRAME = int(AGE * 100) % 100 # Bitmap 0 to 99

    # Then use some trig to get percentage lit
    if AGE <= 0.5: # New -> first quarter -> full
        PERCENT = (1 - math.cos(AGE * 2 * math.pi)) * 50
    else:          # Full -> last quarter -> new
        PERCENT = (1 + math.cos((AGE - 0.5) * 2 * math.pi)) * 50

    # Find next rise/set event, complicated by the fact that some 24-hour
    # periods might not have one or the other (but usually do) due to the
    # Moon rising ~50 mins later each day. This uses a brute force approach,
    # working backwards through the time periods to locate rise/set events
    # that A) exist in that 24-hour period (are not None), B) are still in
    # the future, and C) are closer than the last guess. What's left at the
    # end is the next rise or set (and the inverse of the event type tells
    # us whether Moon's currently risen or not).
    NEXT_EVENT = PERIOD[1].midnight + 100000 # Force first match
    for DAY in reversed(PERIOD):
        if DAY.rise and NEXT_EVENT >= DAY.rise >= NOW:
            NEXT_EVENT = DAY.rise
            RISEN = False
        if DAY.set and NEXT_EVENT >= DAY.set >= NOW:
            NEXT_EVENT = DAY.set
            RISEN = True

    if DISPLAY.rotation in (0, 180): # Horizontal 'landscape' orientation
        CENTER_X = 48      # Text along right
        MOON_Y = 0         # Moon at left
        TIME_Y = 6         # Time at top right
        EVENT_Y = 26       # Rise/set at bottom right
    else:                  # Vertical 'portrait' orientation
        CENTER_X = 16      # Text down center
        if RISEN:
            MOON_Y = 0     # Moon at top
            EVENT_Y = 38   # Rise/set in middle
            TIME_Y = 49    # Time/date at bottom
        else:
            TIME_Y = 6     # Time/date at top
            EVENT_Y = 26   # Rise/set in middle
            MOON_Y = 32    # Moon at bottom


    # Update moon image (GROUP[0])
    FILENAME=getrandom()

    # CircuitPython 6 & 7 compatible
    BITMAP = displayio.OnDiskBitmap(open(FILENAME, 'rb'))
    TILE_GRID = displayio.TileGrid(
        BITMAP,
        pixel_shader=getattr(BITMAP, 'pixel_shader', displayio.ColorConverter())
    )

    # # CircuitPython 7+ compatible
    # BITMAP = displayio.OnDiskBitmap(FILENAME)
    # TILE_GRID = displayio.TileGrid(BITMAP, pixel_shader=BITMAP.pixel_shader)

    TILE_GRID.x = 0
    TILE_GRID.y = MOON_Y
    GROUP[0] = TILE_GRID

    # Update percent value (5 labels: GROUP[1-4] for outline, [5] for text)
    # Set element 5 first, use its size and position for setting others
    # GROUP[5].text = STRING
    GROUP[5].text = ""
    GROUP[5].x = 16 - GROUP[5].bounding_box[2] // 2
    GROUP[5].y = MOON_Y + 16
    for _ in range(1, 5):
        GROUP[_].text = GROUP[5].text
    GROUP[1].x, GROUP[1].y = GROUP[5].x, GROUP[5].y - 1 # Up 1 pixel
    GROUP[2].x, GROUP[2].y = GROUP[5].x - 1, GROUP[5].y # Left
    GROUP[3].x, GROUP[3].y = GROUP[5].x + 1, GROUP[5].y # Right
    GROUP[4].x, GROUP[4].y = GROUP[5].x, GROUP[5].y + 1 # Down

    # Update next-event time (GROUP[8] and [9])
    # Do this before time because we need uncorrupted NOW value
    EVENT_TIME = time.localtime(NEXT_EVENT) # Convert to struct for later
    if COUNTDOWN: # Show NEXT_EVENT as countdown to event
        NEXT_EVENT -= NOW # Time until (vs time of) next rise/set
        MINUTES = NEXT_EVENT // 60
        STRING = str(MINUTES // 60) + ':' + '{0:0>2}'.format(MINUTES % 60)
    else: # Show NEXT_EVENT in clock time
        STRING = hh_mm(EVENT_TIME)
    GROUP[9].text = STRING
    XPOS = CENTER_X - (GROUP[9].bounding_box[2] + 6) // 2
    GROUP[8].x = XPOS
    if RISEN:                    # Next event is SET
        GROUP[8].text = '\u21A7' # Downwards arrow from bar
        GROUP[8].y = EVENT_Y - 2
        print('Sets:', STRING)
    else:                        # Next event is RISE
        GROUP[8].text = '\u21A5' # Upwards arrow from bar
        GROUP[8].y = EVENT_Y - 1
        print('Rises:', STRING)
    GROUP[9].x = XPOS + 6
    GROUP[9].y = EVENT_Y
    # Show event time in green if a.m., amber if p.m.
    GROUP[8].color = GROUP[9].color = (0x00FF00 if EVENT_TIME.tm_hour < 12
                                       else 0xC04000)

    # Update time (GROUP[6]) and date (GROUP[7])
    NOW = time.localtime()
    STRING = hh_mm(NOW)
    GROUP[6].text = STRING
    GROUP[6].x = CENTER_X - GROUP[6].bounding_box[2] // 2
    GROUP[6].y = TIME_Y
    if MONTH_DAY:
        STRING = str(NOW.tm_mon) + '/' + str(NOW.tm_mday)
    else:
        STRING = str(NOW.tm_mday) + '/' + str(NOW.tm_mon)
    GROUP[7].text = STRING
    GROUP[7].x = CENTER_X - GROUP[7].bounding_box[2] // 2
    GROUP[7].y = TIME_Y + 10

    DISPLAY.refresh() # Force full repaint (splash screen sometimes sticks)
    time.sleep(60)
