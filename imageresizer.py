# Creating a tool to help create better images
# In order for this to work we need to find 3D space points
# Written By Trevor Craig
# Started on November 22, 2022

# Libraries
from PIL import Image
import os

 # We need to end with a 32*32 BMP File
def ResizeImage(Input,Output):
    img=Image.open(Input)
    (w, h) = img.size
    wadj=16
    hadj=16#20
    img = img.crop((wadj, hadj, w-wadj, h))#(left, upper, right, lower)
    res_img = img.resize((32,32))
    res_img.save(Output)

def GetNewFileName(file):
    data=file.split('.')
    returndata=data[0]+".bmp"
    return(returndata)


def main2():
    inputdir="pokemon/orginal2"
    outputdir="pokemon/edited2"
    dir_list=os.listdir(inputdir)
    for file in dir_list:
        newname=GetNewFileName(file)
        fullname=outputdir+"/"+newname
        inimg=inputdir+"/"+file
        #ResizeImage(inimg,fullname)
        try:
            ResizeImage(inimg,fullname)
            print(file)
        except:
            print(f"Couldn't resize {file}")

def main():
    ResizeImage("pokemon/orginal/1.png","pokemon/edited/1.bmp")
    ResizeImage("pokemon/Shiut.png","pokemon/555.bmp")


    # https://stackoverflow.com/questions/23951836/using-python-pillow-lib-to-set-color-depth
if __name__ == "__main__":
    print("Starting")
    main2()
    print("Finished!")