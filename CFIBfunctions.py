#!/usr/bin/env python

"""
Define functions useful for the CFIB control system or data analysis
"""

####################################################################################################
#Import modules
####################################################################################################
import os #Operating system interfacing
import sys #System-specific parameters
from datetime import datetime, timezone, timedelta #For manipuation of time

####################################################################################################
#Define functions
####################################################################################################

#Remove the element "key" from a dictionary "dic" without mutating the old dictionary
def removekey(dic, key):
    #Copy the input dictionary dic
    r = dict(dic)
    #Delete the key for the copied dictionary
    del r[key]
    #Return the dictionary with key removed
    return r

#Flatten sublists into a single list
def flattenlist(x):
    flat_list = [item for sublist in x for item in sublist]
    return flat_list

#Return a list with entries [d1,d2,range(d3)].
#Useful for generating addresses for HV supplies
def addressreturn(d1,d2,d3):
    addr = [[d1,d2,z] for z in range(d3)]
    return addr

#Determine if all elemets of a list are identical
def all_same(items):
    return all(x == items[0] for x in items)

#Convert UNIX timestamps to a readable (YMD HMS) format
def timestampconvert(unixts,toffset=0):
    #Convert the time stamp from UNIX to datetime object
    act_time = datetime.fromtimestamp(unixts, timezone.utc)
    #If the offset is defined, offset the time stamp
    if toffset != 0:
        act_time += toffset
    #Convert time to UTC time
    #utc_time = act_time.replace(tzinfo=pytz.utc)
    #Shift UTC time to local time
    local_time = act_time.astimezone()
    #print(local_time.strftime("%Y-%m-%d %H:%M:%S.%f%z (%Z)"))
    return local_time.strftime('%Y-%m-%d %H:%M:%S (%Z)')

#Return the most recent file in a directory containing the string 'filestring'
def getrecentfile(filestring, directory = None):
    #Initialise file list
    tom = []
    #Look for files in the current (or defined) directory
    for file in os.listdir(directory):
        #Look for text files with matching string
        if file.endswith('.txt') and filestring in file:
            #Time of last modification
            tom.append([file, os.path.getmtime(file)])
        else:
            pass
    #Find the file with the most recent modification
    newest = max(tom, key=lambda x:x[1])

    print("Last file update occured on {}".format(timestampconvert(newest[1])))
    return newest[0]

#Return the contents of a text file
def readfile(file):
    #Open the file
    f = open(file,'r')
    #Read the content
    content = f.read()
    #close the file
    f.close()
    return content

#Function to convert a text file containing two-column list to dictionary of {col 1: col 2}
def texttodict(filename):
    #Catch file not found errors
    try:
        #Read the text file
        rawfile = readfile(filename)
        #Extract the data from the raw file
        rawdata = [x.strip().split('#')[0].strip() for x in rawfile.replace(',','\n').splitlines() if not x.startswith('#')]
        #Make an interator over which to zip and make a list of tuples
        tozip = iter(rawdata)
        #Create a dictionary for list of tuples
        toreturn = dict(zip(tozip,tozip))
    except FileNotFoundError:
        print("File {} not found".format(filename))
        toreturn = None
    return toreturn

#Returns a list of keys from a dictionary with a corresponding value of value
def keyfromvalue(dictionary,value):
    return list(dictionary.keys())[list(dictionary.values()).index(value)]
####################################################################################################
#Definitions
####################################################################################################

#Electrode channel properties

"""Define the channels for the ISEG HV supply.
Format is module, address, number of channels at that address
module numbers are [0,1,8] (no idea why last module is 8)
"""
chaddresses = [[0,0,8],[0,1,4],[0,2,4],[0,3,4],[1,0,4],[8,0,4]]

#Voltage limits for channels
limits = flattenlist([[1000] * 4, [-1000] * 4,[20000] * 2,[-20000] * 2,[10000] * 4,[-10000] * 4,\
                      [30000] * 2,[-30000] * 2,[30000] * 2,[-30000] * 2])

#Channel IDs
chids = ('+1kV1','+1kV2','+1kV3','+1kV4','-1kV1','-1kV2','-1kV3','-1kV4',\
        '+20kV1','+20kV2','-20kV1','-20kV2','+10kV1','+10kV2','+10kV3',\
        '+10kV4','-10kV1','-10kV2','-10kV3','-10kV4','+30kV1','+30kV2',\
        '-30kV1','-30kV2','+30kV3','+30kV4','-30kV3','-30kV4')

#Generate a list of addresses for each channel
chret = [addressreturn(*x) for x in chaddresses]

#Fix the channels in modules 1 and 2 (even only)
for i in list(range(-2,0)):
    chret[i] = [[x[0],x[1],2*x[2]] for x in chret[i]]

#Flatten the list of channels
##chlist = flattenlist(chret)
addparam = ['l','a','c']
chlist = [dict(zip(addparam, add)) for add in [[str(i) for i in x] for x in flattenlist(chret)]]

#Elabels defines the electrode naming convention.
elabels = ['e'+str(x+1) for x in list(range(len(chids)))]

#Make a dictionary of channel addresses (useful for labelling data returned from the iCS2)
chaddressdict = dict(list(zip([str(d) for d in chlist],elabels)))
"""
#Give labels meaning
for x in elabels:
    #Use the index of the element x in elabels for the electrode properties
    i = elabels.index(x)
    #Set a string to a variable and then define class attributes
    vars()[x] = iCS2(chids[i],chlist[i],limits[i])
"""

#IP address of the iCS2
#NOTE: this is on the internal atomchumps network; in future we plan to transition to the university network
ip = '192.168.68.237'
#Websocket port
wsport = '8080'
#Username for iCS2
usr = 'admin'
#Shorthand string for '/api/getItem/'
apiget = 'http://'+ip+'/api/getItem/'
#Shorthand string for '/api/setItem/'
apiset = 'http://'+ip+'/api/setItem/'

#Create a dictionary of hardware addresses
NI_hardware_addresses = texttodict('NI_physical_addresses.txt')
