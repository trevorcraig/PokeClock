import gc
import time
import math
import board
import busio
import random
import displayio
from rtc import RTC
from secrets import secrets

LATITUDE = secrets['latitude']
LONGITUDE = secrets['longitude']
class MoonData():
    """ Class holding lunar data for a given day (00:00:00 to 23:59:59).
        App uses two of these -- one for the current day, and one for the
        following day -- then some interpolations and such can be made.
        Elements include:
        age      : Moon phase 'age' at midnight (start of period)
                   expressed from 0.0 (new moon) through 0.5 (full moon)
                   to 1.0 (next new moon).
        midnight : Epoch time in seconds @ midnight (start of period).
        rise     : Epoch time of moon rise within this 24-hour period.
        set      : Epoch time of moon set within this 24-hour period.
    """
    def __init__(self, datetime, hours_ahead, utc_offset):
        """ Initialize MoonData object elements (see above) from a
            time.struct_time, hours to skip ahead (typically 0 or 24),
            and a UTC offset (as a string) and a query to the MET Norway
            Sunrise API (also provides lunar data), documented at:
            https://api.met.no/weatherapi/sunrise/2.0/documentation
        """
        if hours_ahead:
            # Can't change attribute in datetime struct, need to create
            # a new one which will roll the date ahead as needed. Convert
            # to epoch seconds and back for the offset to work
            datetime = time.localtime(time.mktime(time.struct_time((
                datetime.tm_year,
                datetime.tm_mon,
                datetime.tm_mday,
                datetime.tm_hour + hours_ahead,
                datetime.tm_min,
                datetime.tm_sec,
                -1, -1, -1))))
        # strftime() not available here
        url = ('https://api.met.no/weatherapi/sunrise/2.0/.json?lat=' +
               str(LATITUDE) + '&lon=' + str(LONGITUDE) +
               '&date=' + str(datetime.tm_year) + '-' +
               '{0:0>2}'.format(datetime.tm_mon) + '-' +
               '{0:0>2}'.format(datetime.tm_mday) +
               '&offset=' + utc_offset)
        print('Fetching moon data via', url)
        # pylint: disable=bare-except
        for _ in range(5): # Retries
            try:
                location_data = NETWORK.fetch_data(url,
                                                   json_path=[['location']])
                moon_data = location_data['time'][0]
                #print(moon_data)
                # Reconstitute JSON data into the elements we need
                self.age = float(moon_data['moonphase']['value']) / 100
                self.midnight = time.mktime(parse_time(
                    moon_data['moonphase']['time']))
                if 'moonrise' in moon_data:
                    self.rise = time.mktime(
                        parse_time(moon_data['moonrise']['time']))
                else:
                    self.rise = None
                if 'moonset' in moon_data:
                    self.set = time.mktime(
                        parse_time(moon_data['moonset']['time']))
                else:
                    self.set = None
                return # Success!
            except:
                # Moon server error (maybe), try again after 15 seconds.
                # (Might be a memory error, that should be handled different)
                time.sleep(15)

def parse_time(timestring, is_dst=-1):
    """ Given a string of the format YYYY-MM-DDTHH:MM:SS.SS-HH:MM (and
        optionally a DST flag), convert to and return an equivalent
        time.struct_time (strptime() isn't available here). Calling function
        can use time.mktime() on result if epoch seconds is needed instead.
        Time string is assumed local time; UTC offset is ignored. If seconds
        value includes a decimal fraction it's ignored.
    """
    date_time = timestring.split('T')        # Separate into date and time
    year_month_day = date_time[0].split('-') # Separate time into Y/M/D
    hour_minute_second = date_time[1].split('+')[0].split('-')[0].split(':')
    return time.struct_time((int(year_month_day[0]),
                            int(year_month_day[1]),
                            int(year_month_day[2]),
                            int(hour_minute_second[0]),
                            int(hour_minute_second[1]),
                            int(hour_minute_second[2].split('.')[0]),
                            -1, -1, is_dst))