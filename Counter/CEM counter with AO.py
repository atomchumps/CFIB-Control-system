from __future__ import division
from pylab import *
import os
import sys
import time
from PyDAQmx import *
import ctypes


def main():


    #counter_in_physchan = '/Dev6229/ctr0' # User 2 of board 1
    counter_in_physchan = '/Dev6229/ctr1' # PFI 3 of board 1
    ao_physchan = '/Dev6229/ao0'

    sleep_time = 0.025
    max_count_rate = 10000
    smoothing_time_constant = 1
    #overcount is the number of times the counter is returning a value greater than max_count_rate
    overcount = 0
    #oversample sets the limit for the number of samples above max_count_rate before the maximum is changed
    oversamplelimit = 2


    #Initialise ao
    ao_val = 0
    ao_task = Task()
    ao_task.CreateAOVoltageChan(ao_physchan,"",-10.0,10.0,DAQmx_Val_Volts,None)
    ao_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(float(ao_val)),None,None)

    #Initialsise counter in
    count_data = (ctypes.c_ulong*1)()
    ctypes.cast(count_data, ctypes.POINTER(ctypes.c_ulong))
    ctr_in_task = Task()
    ctr_in_task.CreateCICountEdgesChan(counter_in_physchan,"",DAQmx_Val_Rising,0,DAQmx_Val_CountUp)
    ctr_in_task.StartTask()

    print('DAQ is armed and counting...')
    print('Press Ctrl-C to end. (Or Command + . on OSX)')

    #Just stuff to calculate count frequency and moving average
    t_old = time.time()
    val_old = 0
    mooving_ave = 0
    count_rate = 0

    #Just keep reading doing it until exited
    while True:
        #Read the current counter value
        ctr_in_task.ReadCounterScalarU32(10.0,count_data,None)
        val = int(count_data[0])

        #Just stuff to calculate count frequency and moving average
        t_new = time.time()
        dt = t_new - t_old
        dval = val-val_old
        try:
            count_rate = float(dval)/dt
        except ZeroDivisionError:
            pass
        smoothing_factor = 1-exp(-dt/smoothing_time_constant)
        mooving_ave = smoothing_factor*count_rate + (1-smoothing_factor)*mooving_ave
        t_old = t_new
        val_old = val
        print('Meausred frequency:{:.1f}Hz. {:.1f} second moving ave:{:.0f}'.format(count_rate,smoothing_time_constant, mooving_ave))

        #Scale the output voltage as counts/max(counts)
        output_voltage = count_rate/max_count_rate*10
        #If the the counts are greater than the maximum count rate, output 10 V and if increment the saturation counter
        if output_voltage > 10:
            output_voltage = 10.0
            print('Analogue out saturating.')
            overcount += 1
        else:
            overcount = 0

        #If the saturation limit is reached, increase max_count_rate and reduce (slightly) overcount
        if overcount ==  oversamplelimit:
            max_count_rate *= 2
            if oversamplelimit > 10:
                overcount = oversamplelimit - int(oversamplelimit/20)
            else:
                overcount = 0

        #Update the output voltage
        ao_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(output_voltage),None,None)

        #Put the process to sleep for a while so it doen't go bonkers
        time.sleep(sleep_time)

    ctr_in_task.StopTask()
    ctr_in_task.ClearTask()


#Make program run now...
if __name__ == "__main__":

    main()
