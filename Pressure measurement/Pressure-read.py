#!/usr/bin/env python

""" Pressure-read.py: A program measuring the current from the ion pump and converting to pressure """

from __future__ import division
from pylab import *
import os
import sys
import time
from PyDAQmx import *

def main():

    ai_physchan = '/Dev6229/ai2'

    samps_per_chan = 100
    sample_rate = 100
    buffer_size = 1000

    ai_task = Task()
    read = int32()
    ai_data = zeros(samps_per_chan*len(ai_physchan))

    ai_task.CreateAIVoltageChan(ai_physchan,'',DAQmx_Val_Cfg_Default,-10.0,10.0,DAQmx_Val_Volts,None)
    ai_task.CfgSampClkTiming('',sample_rate,DAQmx_Val_Rising,DAQmx_Val_ContSamps,buffer_size)

    print('ADC is now measuring...')
    print('Press Ctrl-C to end. (Or Command + . on OSX)')

    ai_task.StartTask()

    while True:
        ai_task.ReadAnalogF64(samps_per_chan,10.0,DAQmx_Val_GroupByChannel,ai_data,len(ai_data),read,None)
        pumpcurrent = 10 ** (ai_data - 8)
        pressure = (pumpcurrent * 370)/(5000 * 10)
        print("The measured pressure is {:0.1e} Torr".format(pressure.mean()))

    ai_task.StopTask()

#Make program run now...
if __name__ == "__main__":

    main()
