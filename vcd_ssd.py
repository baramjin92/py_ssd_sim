#!/usr/bin/python

import os
import sys
import datetime

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.ssd_param import *

from sim_event import *
from sim_vcd import *

def enable_vcd(func) :
	def enable_vcd(*args, **kwargs) :
		if ssd_param.ENABLE_VCD == False :
			return 0

		result = func(*args, **kwargs)
		return result
	
	return enable_vcd

vcd = vcd_manager()

# symbol character should be unique,
# define symbol for 'sim' module
VCD_SYMBOL_THROUGHPUT = 'A'
VCD_SYMBOL_LATENCY = 'B'
VCD_SYMBOL_HOST_QD ='C'
VCD_SYMBOL_FTL_QD = 'D'
VCD_SYMBOL_GC_COST = 'E'
VCD_SYMBOL_UPLINK ='F'
VCD_SYMBOL_DOWNLINK = 'G'
VCD_SYMBOL_NEW_WT = 'H'
VCD_SYMBOL_NEW_GT = 'I'
VCD_SYMBOL_BUF_LEVEL = 'J'
VCD_SYMBOL_BUF_LEVEL_0 = 'K'
VCD_SYMBOL_BUF_LEVEL_1 = 'L'
VCD_SYMBOL_BUF_LEVEL_2 = 'M'

# define symbol for 'channel'
VCD_SYMBOL_FLASH_QD = 'N'
VCD_SYMBOL_SEQ_STATE = 'O'
VCD_SYMBOL_CELL_BUSY = 'P'
VCD_SYMBOL_IO_BUSY = 'Q'
VCD_SYMBOL_WAIT = 'R'
VCD_SYMBOL_CHANEL_BUSY = 'S'

def ssd_vcd_init(num_channel, ways_per_channel) :
	vcd.set_date()
	vcd.set_version('python ssd simulator vcd')
	vcd.set_comment('developed by yong jin')
	vcd.set_time_scale('1ns')

	vcd.add_module('sim')
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_THROUGHPUT, 'MB/s', '0', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_LATENCY, 'latency', '0', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_HOST_QD, 'QD_HOST', '0', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_FTL_QD, 'QD_FTL', '0', 'sim'))
	#vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_GC_COST, 'cost', 'x', 'sim'))
	
	vcd.add_variable(vcd_variable('wire', 2, VCD_SYMBOL_UPLINK, 'uplink', 'bxx', 'sim'))
	vcd.add_variable(vcd_variable('wire', 2, VCD_SYMBOL_DOWNLINK, 'downlink', 'bxx', 'sim'))
	vcd.add_variable(vcd_variable('event', 1, VCD_SYMBOL_NEW_WT, 'new_wt', '1', 'sim'))
	vcd.add_variable(vcd_variable('event', 1, VCD_SYMBOL_NEW_GT, 'new_gt', '0', 'sim'))

	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL, 'buf', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL_0, 'rbuf', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL_1, 'wbuf', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL_2, 'gcbuf', 'x', 'sim'))
	
	# loop channel
	for index in range(num_channel) :
		ch_name = 'channel%d'%index
		    
		vcd.add_module(ch_name)
		
		# loop way per chnnel
		for index2 in range(ways_per_channel) :
			way_index = '%d'%(num_channel * index2 + index)
			#way_name = 'ch_%d_%d_'%(index, index2)
			way_name = 'way_'+way_index+'_'
						
			vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_FLASH_QD+way_index, way_name+'QD', 'x', ch_name))
			vcd.add_variable(vcd_variable('wire', 5, VCD_SYMBOL_SEQ_STATE+way_index, way_name+'state', 'bxxxxx', ch_name))
			vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_CELL_BUSY+way_index, way_name+'cell_bsy', '0', ch_name))
			vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_IO_BUSY+way_index, way_name+'io_bsy', 'x', ch_name))
			vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_WAIT+way_index, way_name+'wait', 'x', ch_name))
		# end loop way
		
		vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_CHANEL_BUSY+'%d'%index, 'ch_%d_bsy'%index, 'x', ch_name))
	# end loop channel
	
def ssd_vcd_make(num_channel) :	
	vcd.make_header()
	vcd.make_variable('sim')	
	
	for index in range(num_channel) :
		ch_name = 'channel%d'%index
		vcd.make_variable(ch_name)
					
	vcd.make_init_state()			
	
	# need to save #0 event 			
	event_mgr.timetick = 0
	ssd_vcd_set_integer(VCD_SYMBOL_HOST_QD, 0)
	
@enable_vcd
def ssd_vcd_set_integer(symbol, value) :
	vcd.change_state(event_mgr.timetick, symbol, str(value))		

@enable_vcd
def ssd_vcd_set_binary(symbol, value) :
	vcd.set_time(event_mgr.timetick)
	vcd.set_binary_n(symbol, value)		

@enable_vcd
def ssd_vcd_set_value(symbol, value) :
	vcd.change_state(event_mgr.timetick, symbol, value)		


@enable_vcd
def ssd_vcd_set_nfc_busy(channel, value) :
	vcd.set_time(event_mgr.timetick)		
	vcd.set_binary_1(VCD_SYMBOL_CHANEL_BUSY+'%d'%channel, value)			

@enable_vcd
def ssd_vcd_set_nfc_state(way, state, cell, io, wait) :
	way_index = '%d'%way

	vcd.set_time(event_mgr.timetick)		
	vcd.set_binary_n(VCD_SYMBOL_SEQ_STATE+way_index, state)			
	vcd.set_binary_1(VCD_SYMBOL_CELL_BUSY+way_index, cell)		
	vcd.set_binary_1(VCD_SYMBOL_IO_BUSY+way_index, io)		
	vcd.set_binary_1(VCD_SYMBOL_WAIT+way_index, wait)		
	
@enable_vcd								
def ssd_vcd_open(filename, num_channels, ways_per_channel) :				
	vcd.open(filename)
	ssd_vcd_init(ssd_param.NUM_CHANNELS, ssd_param.WAYS_PER_CHANNELS)
	ssd_vcd_make(ssd_param.NUM_CHANNELS)

@enable_vcd
def ssd_vcd_close() :
	vcd.close()
								
if __name__ == '__main__' :
	ssd_vcd_open('ssd.vcd', ssd_param.NUM_CHANNELS, ssd_param.WAYS_PER_CHANNELS)
	
	event_mgr.timetick = 2000
	ssd_vcd_set_integer(VCD_SYMBOL_HOST_QD, 2)
	event_mgr.timetick = 3000
	ssd_vcd_set_integer(VCD_SYMBOL_HOST_QD, 3)
	event_mgr.timetick = 4000
	ssd_vcd_set_integer(VCD_SYMBOL_HOST_QD, 4)
	
	ssd_vcd_close()
	