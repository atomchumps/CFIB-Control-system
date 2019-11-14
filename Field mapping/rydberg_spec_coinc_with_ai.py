from __future__ import division
from pylab import *
import h5py
import time
import datetime
import zmq
from  multiprocessing import Process
from PyDAQmx import *


def main():

    #Input/output physical connections
    ao_hv_physchan = '/Dev1/ao2'#'/Dev1/ao2'
    ao_wavelength_physchan = '/Dev2/ao19'
    ctrin_mcp_physchan = '/Dev2/ctr1'
    ai_physchan_list = ['/Dev1/ai0', '/Dev1/ai1']
    ai_physchan_description = ['hv_monitor', 'blue_power_monitor']
    wavemeter_address = 'tcp://192.168.68.43:5678'
    plotter_port = '5679'
    
    #Output parameters
    dwell_time = 0.2
    wavelength_stabilisation_time = 0.01
    wavelenght_max_voltage_jump = 1E-3
    wavelength_jump_period = 0.001
    default_ao_wavelength_val = 0
    #hv
    ##########################
    hv_min = 0.4
    hv_max = 0.4
    hv_numpoints = 1
#    hv_min = 0.201
#    hv_max = hv_min + 0.025
#    hv_numpoints = 1
    ##########################
    hv_ramp = linspace(hv_min, hv_max, hv_numpoints)
    #wavelength
    ##########################
    wavelength_min = -1.5
    wavelength_max = 1.5
    wavelength_numpoints = 2000
#    wavelength_min = -0.1
#    wavelength_max = 0.1
#    wavelength_numpoints = 10
    ##########################
    wavelength_ramp = linspace(wavelength_min, wavelength_max, wavelength_numpoints)
    #Create hdf storage
    hdf_name = 'rydberg_data_coin.hdf'
    
    #Initialise data file
    timestamp = datetime.datetime.fromtimestamp(time.time())
    dataset_name = 'data_slab_{:d}{:0>2d}{:0>2d}:{:0>2d}:{:0>2d}:{:0>2d}'.format(timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second)
#    dataset_name = 'data_slab'
    data_file = h5py.File(hdf_name,'a')
    data_file.require_dataset(dataset_name, (hv_numpoints, len(wavelength_ramp), 6), 'float64')
    dset = data_file[dataset_name]
    dset.attrs['data_layout'] = '(voltage, wavelength, (act_voltage, act_wavelength, counts, time_for_counts, hv_monitor, measured_blue_power_input))'

    # Note! Generally speaking, a single task can't use physical channels from different devices. Also, a single device can't run more than one task of a particular type at any one time. This means as if I add more ao channels, I will have to add them to one task or the other (probably, though it seems to be working just fine as it is).
    #Initialise HV ao
    ao_hv_val = 0
    ao_hv_task = Task()
    ao_hv_task.CreateAOVoltageChan(ao_hv_physchan,"",-10.0,10.0,DAQmx_Val_Volts,None)
    ao_hv_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(float(ao_hv_val)),None,None)
    #Initialise wavelength ao
    ao_wavelength_val = 0
    ao_wavelength_task = Task()
    ao_wavelength_task.CreateAOVoltageChan(ao_wavelength_physchan,"",-10.0,10.0,DAQmx_Val_Volts,None)
    ao_wavelength_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(float(ao_wavelength_val)),None,None)
    #Initialise Counter
    ctrin_mcp_val_cytpe = (ctypes.c_ulong*1)()
    ctypes.cast(ctrin_mcp_val_cytpe, ctypes.POINTER(ctypes.c_ulong))
    ctrin_mcp_task = Task()
    ctrin_mcp_task.CreateCICountEdgesChan(ctrin_mcp_physchan,"",DAQmx_Val_Rising,0,DAQmx_Val_CountUp)
    #Initialise ai (analogue in)
    samps_per_chan = 100
    sample_rate = 10000
    buffer_size = 10000
    ai_data = numpy.zeros((samps_per_chan*len(ai_physchan_list),), dtype=numpy.float64)
    ai_data_dict = dict()
    ai_task = Task()
    read = int32()
    ai_task.CreateAIVoltageChan(','.join(ai_physchan_list),'',DAQmx_Val_Cfg_Default,-10.0,10.0,DAQmx_Val_Volts,None)
    ai_task.CfgSampClkTiming('',sample_rate,DAQmx_Val_Rising,DAQmx_Val_ContSamps,buffer_size)
    ai_task.SetReadRelativeTo(DAQmx_Val_MostRecentSamp)
    ai_task.StartTask()
   

    #Initialise wavemeter communications
    wavemeter_ctx = zmq.Context()
    wavemeter_soc = wavemeter_ctx.socket(zmq.SUB)
    wavemeter_soc.setsockopt(zmq.SUBSCRIBE,'L1')
    wavemeter_soc.connect(wavemeter_address)
    poller = zmq.Poller()
    poller.register(wavemeter_soc, zmq.POLLIN)
    #Test wavemeter communications
    print('Checking communication with wavemeter...')
    wavelenght = float(wavemeter_soc.recv_multipart()[1])
    if wavelenght > 0:
        print('Communication OK. Wavelength ={:10.4f}nm'.format(wavelenght))
    else:
        print('Communication OK, but invalid wavelength recieved. Check exposure level.')
    #Initialise plotter server
    plotter_ctx = zmq.Context()
    plotter_soc = plotter_ctx.socket(zmq.PUB)
    plotter_soc.hwm = 1
    plotter_soc.bind('tcp://*:' + plotter_port)
    time.sleep(1) #Gives subscribers time to bind

    ctrin_mcp_task.StartTask()

    ###############################################################################
    #Start to take the data
    last_ao_wavelength_val = default_ao_wavelength_val
    print('Generating ramps and receiving counts....')
    start_time = time.time()

#    #If you just want to repeat the experiment over and over at on voltege, uncomment this, and comment out the for statement
#    while True:
#        hv_idx = 0
#        ao_hv_val = 0.211
    for hv_idx, ao_hv_val in enumerate(hv_ramp):

        print('Electrode control voltage ={:.4f}, Ramp value {:d} of {:d}'.format(ao_hv_val, hv_idx + 1, len(hv_ramp)))
        online_plotter_refresh = 1

        ao_hv_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(ao_hv_val),None,None)
        for wavelength_idx, ao_wavelength_val in enumerate(wavelength_ramp):
            
            #Ramp to the desired wavelength with small steps
            wavelenght_safety_ramp = arange(last_ao_wavelength_val, ao_wavelength_val, sign(ao_wavelength_val - last_ao_wavelength_val)*wavelenght_max_voltage_jump)
            for safety_ao_wavelength_val in wavelenght_safety_ramp:
                ao_wavelength_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(safety_ao_wavelength_val),None,None)
                time.sleep(wavelength_jump_period)
            #Set the wavelenth to the actual desired val
            ao_wavelength_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(ao_wavelength_val),None,None)
            time.sleep(wavelength_stabilisation_time)
            
            #Read initial counts
            t0 = time.time()
            ctrin_mcp_task.ReadCounterScalarU32(10.0,ctrin_mcp_val_cytpe,None)
            ctrin_mcp_val0 = float(ctrin_mcp_val_cytpe[0])
            
            time.sleep(dwell_time/2) # to attempt to read wavelength in the middle of the aquisition period
            #Empty the wavelength queue, then read wavelength
            while True:
                poll_dict = dict(poller.poll(0))
                if wavemeter_soc in poll_dict and poll_dict[wavemeter_soc] == zmq.POLLIN:
                    #recieve message straight away just to remove it from the queue
                    wavemeter_soc.recv_multipart()
                else:
                    #when queue is empty, wait for the next message to come through, and use that one
                    wavelength = float(wavemeter_soc.recv_multipart()[1])
                    break
    
            #Read analogue voltages, store each channel in a dictionary
            ai_task.ReadAnalogF64(samps_per_chan,10.0,DAQmx_Val_GroupByChannel,ai_data,len(ai_data),byref(read),None)
            for idx, chan_description in enumerate(ai_physchan_description):
                ai_data_dict[chan_description] = array(ai_data[idx*samps_per_chan:(idx + 1)*samps_per_chan])

            time_remaining_in_dwell = dwell_time - (time.time() - t0)
            if time_remaining_in_dwell > 0:
                time.sleep(time_remaining_in_dwell)
            
            #Read final counts
            t1 = time.time()
            ctrin_mcp_task.ReadCounterScalarU32(10.0,ctrin_mcp_val_cytpe,None)
            ctrin_mcp_val1 = float(ctrin_mcp_val_cytpe[0])
            
            dt = t1 - t0
            dcounts = ctrin_mcp_val1 - ctrin_mcp_val0
            
            #Save data locally for later, and send it to a plotter for immeadiate visulation
            measured_hv_input = ai_data_dict['hv_monitor'].mean()
            measured_blue_power_input = ai_data_dict['blue_power_monitor'].mean()
            dset[hv_idx, wavelength_idx, :] = array((ao_hv_val, wavelength, dcounts, dt, measured_hv_input, measured_blue_power_input))
            plotter_soc.send_multipart(('data', str(measured_hv_input), str(wavelength), str(dcounts), str(dt), str(online_plotter_refresh), str(measured_blue_power_input)))
            
            online_plotter_refresh = 0
            last_ao_wavelength_val = ao_wavelength_val

        #Print update to the terminal every so often
        try:
            time_so_far = time.time() - start_time
            est_time_remaining = time_so_far/((hv_idx + 1)/len(hv_ramp)) - time_so_far
            print '########################################################'
            print 'Est. time remaining = '+str(int(floor(est_time_remaining/(60*60))))+'hrs '+str(int(floor(mod(est_time_remaining, 60*60)/60)))+'mins '+str(int(mod(est_time_remaining, 60)))+'secs'
        except ZeroDivisionError:
            pass

    #Return ao_wavelength and ao_hv to default values
    #Ramp with small steps to the desired wavelength
    print('Ramping back to default wavelength and electrode voltage')
    wavelenght_safety_ramp = arange(last_ao_wavelength_val, default_ao_wavelength_val, sign(default_ao_wavelength_val - last_ao_wavelength_val)*wavelenght_max_voltage_jump)
    for safety_ao_wavelength_val in wavelenght_safety_ramp:
        ao_wavelength_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(safety_ao_wavelength_val),None,None)
        time.sleep(wavelength_jump_period)
    ao_wavelength_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(float(default_ao_wavelength_val)),None,None)
    ao_hv_task.WriteAnalogF64(1,1,10.0,DAQmx_Val_GroupByChannel,array(float(hv_min)),None,None)

    data_file.close()

    ao_hv_task.StopTask()
    ao_wavelength_task.StartTask()
    ctrin_mcp_task.StopTask()

    ao_hv_task.ClearTask()
    ao_wavelength_task.ClearTask()
    ctrin_mcp_task.ClearTask()

    time.sleep(0.5)
    print('Experiment complete.')


#Make program run now...
if __name__ == "__main__":
    main()





























