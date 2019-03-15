#!/usr/bin/env python

'''
CEM counter plot.py: A program measuring the count rate from the channel eletron multiplier and plotting it in real time.
A. J. McCulloch, November 2018

####################################################################################################

Largely built from previous code; however a useful resource is given below:
Parts taken from https://github.com/MarcoForte/PyDAQmx_Helper/blob/master/pydaqmx_helper/counter.py
'''

####################################################################################################
#Import modules
####################################################################################################

from PyDAQmx import * #PyDAQmx module for working with the NI DAQ
import ctypes #Module required for creating C type ojects - required for some PyDAQmx operations
import time #Time access and conversions
from pylab import * #For interactive calculations and plotting
from CFIBfunctions import * #Function definitions

####################################################################################################
#Define classes
####################################################################################################

#A mysterious class which seems to be required for live plotting (legacy code from R. Speirs, 2018)
class DataSaver:
    """ I just needed to be able to access an array inside some strange matplotlip function """
    def __init__(self, data = []):
        self.data = data

####################################################################################################
#AOsimple class for simple analogue output
class AOsimple:
    #Initialise the analogue out task
    def __init__(self, ao_physchan = NI_hardware_addresses['AO01'], V_default = 0):
        self.task = Task() #Define the task as Task()
        self.ao_physchan = ao_physchan #Define the analogue output physical channel
        self.voltage = V_default #Set the default voltage
        self.task.CreateAOVoltageChan(ao_physchan,"",-10.0,10.0,DAQmx_Val_Volts,None) #Set the analogu output task

    #Set the AO voltage
    def setvoltage(self, value, confirm = False):
        #Write the voltage
        self.task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(float(value)),None,None)
        #Update the voltage attribute
        self.voltage = value
        #Print a confimation if required
        if confirm == True:
            #Figure out which AO channel is being addressed
            chan = keyfromvalue(NI_hardware_addresses, self.ao_physchan)
            print("Channel {} was set to {} V".format(chan, value))

    #Clear the task
    def clear(self, zero = True):
        #Zero the channel
        if zero == True:
            self.setvoltage(0, True)
        #Clear the task
        self.task.ClearTask()
        print("Analogue output task cleared")

####################################################################################################
#AIsimple class for simple analogue input reading
class AIsimple:
    def __init__(self, samples = 10, sample_rate = 10000, ai_physchan = NI_hardware_addresses['AI01'], read_most_recent = False):
        self.task = Task() #Define the task as Task()
        self.samples = samples #Number of samples per channel
        self.sample_rate = sample_rate #Sampling rate of the analogue input
        self.ai_physchan = ai_physchan #Physical address of the analogue input channel
        self.read = ctypes.c_int32() #Make a ctype to store the measurement
        self.data = np.zeros(self.samples, dtype=np.float64) #Make a data array
        self.task.CreateAIVoltageChan(self.ai_physchan, '', DAQmx_Val_Cfg_Default, -10.0, 10.0, DAQmx_Val_Volts, None) #Create the AI task
        self.buffer_size = 10000 #NOTE: Infrequent measurement/insufficient buffer size will cause overflow!
        self.task.CfgSampClkTiming('', self.sample_rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.buffer_size) #Set the sampling of the task
        #This is legacy code (R. Speirs, 2018), not certain of functionality
        if read_most_recent:
            self.task.SetReadRelativeTo(DAQmx_Val_MostRecentSamp)#be careful with this. Depends what you want to do.
            #self.task.SetReadOffset(-self.samples)

    #Measure the analogue input. Task is started and stopped to avoid buffer overflow
    def readvoltage(self, returnmean = True):
        #Start the task
        self.task.StartTask()
        #Perform the measurement
        self.task.ReadAnalogF64(self.samples, 10.0, DAQmx_Val_GroupByScanNumber, self.data, self.data.size, ctypes.byref(self.read), None)
        #Return the mean of the measured values
        if returnmean == True:
            toreturn = self.data.mean()
        #Retrun an array of measured values
        elif returnmean == False:
            toreturn = self.data
        #Stop the task
        self.task.StopTask()
        return toreturn

    #Clear the task
    def close(self):
        self.task.ClearTask()
        print("Analogue input task cleared")

####################################################################################################
#Counter class for defining counter objects
class Counter:
    #Initialise the counting task
    def __init__(self, ctr_physchan = NI_hardware_addresses['Counter 1']):
        self.ctr_physchan = ctr_physchan #Define the physical channel for the coutner
        self.task = Task() #Define the task as Task()
        self.task.CreateCICountEdgesChan(ctr_physchan, '', DAQmx_Val_Rising, 0, DAQmx_Val_CountUp) #Set the counting task
        self.cnt = (ctypes.c_ulong*4)() #Initialise the count - must be unsigned long!
        ctypes.cast(self.cnt, ctypes.POINTER(ctypes.c_ulong))  #Use ctypes cast to constuct a pointer
        self.count = 0 #The most recent count measurement
        self.freq = 0 #The most recent frequency measurement
        self.time = time.time() #Time of the last measurement

    #Start the counter
    def start(self):
        #count_data = (ctypes.c_ulong*1)()
        #ctypes.cast(count_data, ctypes.POINTER(ctypes.c_ulong))
        self.task.StartTask()
        print("DAQ is armed and counting...")

    #Return a count without stopping the counter
    def getCount(self, totalcount = False, sample_rate = 0, samples = 1):
        #Initialise list
        meas = []
        #Perform measurement to initialise the attributes
        self.task.ReadCounterScalarU32(10.0, self.cnt, None)
        #Update the count attribute
        self.count = self.cnt[0]
        #Update the time attribute
        self.time = time.time()
        #Include a pause to allow for sampling at a particular rate
        if sample_rate > 0:
            time.sleep(1/sample_rate)
        #Loop over the number of samples
        for i in range(samples):
            #Read the counter
            self.task.ReadCounterScalarU32(10.0, self.cnt, None)
            #Update the time attribute
            self.time = time.time()
            #Return either the total count (from start) or since last measurement
            #Option 1: The counts since start
            if totalcount == True:
                value = self.cnt[0]
            #Option 2: The coutns since last count measurement (default)
            elif totalcount == False:
                #Difference between the measured count (since start) and previous measurment (since start)
                value = self.cnt[0] - self.count

            #Update the count attribute
            self.count = self.cnt[0]
            #Append the measured value
            meas.append(int(value))

            #Include a pause to allow for sampling at a particular rate
            if sample_rate > 0:
                time.sleep(1/sample_rate)
        if samples == 1:
            meas = meas[0]
        return meas

    #Return a frequency without stopping the counter
    def getfreq(self, sample_rate = 0, samples = 1):
        #Initialise list
        meas = []
        #Perform measurement to initialise the attributes
        self.task.ReadCounterScalarU32(10.0, self.cnt, None)
        #Update the count attribute
        self.count = self.cnt[0]
        #Update the time attribute
        if samples > 1:
            self.time = time.time()
        #Include a pause to allow for sampling at a particular rate
        if sample_rate > 0:
            time.sleep(1/sample_rate)
        #Loop over the number of samples
        for i in range(samples):
            #Time since last measurement
            t_old = self.time
            #Read the counter
            self.task.ReadCounterScalarU32(10.0, self.cnt, None)
            #Update the time attribute
            self.time = time.time()
            #Difference between the measured count (since start) and previous measurment (since start)
            numcounts = self.cnt[0] - self.count
            #Calculate the count rate
            value = numcounts/(self.time-t_old)
            #Update the count attribute
            self.freq = value
            #Update the count attribute
            self.count = self.cnt[0]
            #Append the measured value
            meas.append(value)
            #Include a pause to allow for sampling at a particular rate
            if sample_rate > 0:
                time.sleep(1/sample_rate)

        if samples == 1:
            meas = meas[0]
        return meas

    #Stop the counter and return the count
    def stop(self, totalcount = False):
        #Get the counter value
        value = self.getCount(totalcount)
        #Stop the task
        self.task.StopTask()
        print("DAQ is armed but no longer counting")
        return value

    #Stop the counter and clear the task
    def close(self):
        self.task.StopTask()
        self.task.ClearTask()
        print("DAQ is no longer armed and tasks have been cleared")

####################################################################################################
#Create a dynamically updating plot
def makeplot():
    t_span = 2 #Span of the data in seconds
    t_points = 50 #Number of divisions over the span

    fig1, ax1 = plt.subplots(1, 1, tight_layout=True)
    line, = ax1.plot(linspace(-t_span, 0, t_points), zeros(t_points))
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Count rate (Hz)')
    ax1.set_ylim(-100, 2100)
    ax1.set_xlim(-t_span, 0)
    ax1.set_title('CEM count rate')
    ax1.grid()

    #Plot the ion rate in real time
    sample_rate = t_points/t_span #Sampling rate of the measurement
    refresh_rate = 10 #this is only approx. Should be 100ms updates - see animation interval
    samples = int(sample_rate/refresh_rate) #(how many points per refresh)


    #Initialise the counts
    CEM_counts = Counter(NI_hardware_addresses['Counter 2'])
    #Start the counter
    CEM_counts.start()

    saved = DataSaver()
    saved.data_save = zeros(t_points)

    def update_data(update_number):
        #roll left to right
        saved.data_save = roll(saved.data_save, -samples)
        saved.data_save[-samples:] = CEM_counts.getfreq(sample_rate, samples)
        line.set_ydata(saved.data_save)  # update the data
        return line,

    import matplotlib.animation as animation
    print('Plotting transmission photodiode voltage. Close figure to end.')
    ani = animation.FuncAnimation(fig1, update_data, interval=int(1/refresh_rate), blit=True)
    plt.show()

####################################################################################################
####################################################################################################
#Code starts here
####################################################################################################
####################################################################################################

if __name__ == '__main__':
    #Make a animated plot of the count rate vs time
    makeplot()
