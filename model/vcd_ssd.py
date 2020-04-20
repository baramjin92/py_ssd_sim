#!/usr/bin/python

import os
import sys
import datetime

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from sim_vcd import *

vcd = vcd_manager()

# symbol character should be unique,
# define symbol for 'sim' module
VCD_SYMBOL_GC_COST = 'A'
VCD_SYMBOL_THROUGHPUT = 'B'
VCD_SYMBOL_LATENCY = 'C'
VCD_SYMBOL_HOST_QD ='D'
VCD_SYMBOL_FTL_QD = 'E'
VCD_SYMBOL_UPLINK ='F'
VCD_SYMBOL_DOWNLINK = 'G'
VCD_SYMBOL_NEW_WT = 'H'
VCD_SYMBOL_NEW_GT = 'I'

# define symbol for 'channel'
VCD_SYMBOL_FLASH_QD = 'J'
VCD_SYMBOL_SEQ_STATE = 'K'
VCD_SYMBOL_CELL_BUSY = 'L'
VCD_SYMBOL_IO_BUSY = 'M'
VCD_SYMBOL_WAIT = 'N'
VCD_SYMBOL_CHANEL_BUSY = 'O'

VCD_SYMBOL_BUF_LEVEL = 'P'
VCD_SYMBOL_BUF_LEVEL_0 = 'Q'
VCD_SYMBOL_BUF_LEVEL_1 = 'R'
VCD_SYMBOL_BUF_LEVEL_2 = 'S'

def ssd_vcd_init() :
	vcd.set_date()
	vcd.set_version('python ssd simulator vcd')
	vcd.set_comment('developed by yong jin')
	vcd.set_time_scale('1ns')

	vcd.add_module('sim')
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_GC_COST, 'cost', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_THROUGHPUT, 'MB/s', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_LATENCY, 'latency', '0', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_HOST_QD, 'QD_HOST', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_FTL_QD, 'QD_FTL', 'x', 'sim'))
	
	vcd.add_variable(vcd_variable('wire', 2, VCD_SYMBOL_UPLINK, 'uplink', 'bxx', 'sim'))
	vcd.add_variable(vcd_variable('wire', 2, VCD_SYMBOL_DOWNLINK, 'downlink', 'bxx', 'sim'))
	vcd.add_variable(vcd_variable('event', 1, VCD_SYMBOL_NEW_WT, 'new_wt', '1', 'sim'))
	vcd.add_variable(vcd_variable('event', 1, VCD_SYMBOL_NEW_GT, 'new_gt', '0', 'sim'))

	# CHANNEL : from A to A+n
	# WAY : from 0 to m
	capital = list(range(ord('A'), ord('Z')))
	number = list(range(ord('0'), ord('9')))
	
	# loop channel
	num_channel = 4
	ways_per_channel = 2
	for index in range(num_channel) :
		ch_name = 'channel' + chr(capital[index])
		ch_num = chr(number[index])
		    
		vcd.add_module(ch_name)
		
		# loop way per chnnel
		for index2 in range(ways_per_channel) :
			way_name = chr(capital[index]) + chr(number[index2])				# A0, A1, ... An, B0, B1, ... Bn, ...
			way_index = str(num_channel * index + index2)
						
			vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_FLASH_QD+way_index, way_name+'_QD', 'x', ch_name))
			vcd.add_variable(vcd_variable('wire', 5, VCD_SYMBOL_SEQ_STATE+way_index, way_name+'_state', 'bxxxxx', ch_name))
			vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_CELL_BUSY+way_index, way_name+'_cell_bsy', '0', ch_name))
			vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_IO_BUSY+way_index, way_name+'_io_bsy', 'x', ch_name))
			vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_WAIT+way_index, way_name+'_wait', 'x', ch_name))
		# end loop way
		
		vcd.add_variable(vcd_variable('wire', 1, VCD_SYMBOL_CHANEL_BUSY+ch_num, 'ch_'+chr(capital[index])+'_bsy', 'x', ch_name))
	# end loop channel
	
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL, 'buf', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL_0, 'rbuf', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL_1, 'wbuf', 'x', 'sim'))
	vcd.add_variable(vcd_variable('real', 1, VCD_SYMBOL_BUF_LEVEL_2, 'gcbuf', 'x', 'sim'))

def ssd_vcd_make() :	
	vcd.make_header()
	vcd.make_variable('sim')	
	
	capital = list(range(ord('A'), ord('Z')))	
	num_channel = 4
	for index in range(num_channel) :
		ch_name = 'channel' + chr(capital[index])
		vcd.make_variable(ch_name)
					
	#vcd.make_init_state()						
	
if __name__ == '__main__' :
	ssd_vcd_init()
	ssd_vcd_make()
	