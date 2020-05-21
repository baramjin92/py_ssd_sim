#!/usr/bin/python

import os
import sys

import numpy as np
import pandas as pd

from model.host import host_manager
from model.hic import hic_manager

from model.nand import nand_manager
from model.nfc import nfc

from model.hil import hil_manager
from model.ftl_zns import *
from model.fil import fil_manager
from model.nand import *

from model.workload import *

from config.sim_config import unit
from config.sim_config import nand_info

from config.ssd_param import *

from model.buffer import *
from model.queue import *
from model.nandcmd import *

from sim_event import *
from sim_log import *
from sim_report import *

from progress.bar import Bar

def build_workload_zns() :
	wlm.set_capacity(range_16GB)
		
	wlm.set_workload(workload(WL_ZNS_WRITE, 0, range_16GB, 128, 128, 16, WL_SIZE_MB, 0, True, False))
	wlm.set_workload(workload(WL_ZNS_READ, 0, range_16GB, 128, 128, 16, WL_SIZE_MB, 0, True, False))
		
def host_run() :
	node = event_mgr.alloc_new_event(0)
	node.dest = event_dst.MODEL_HOST
	node.code = event_id.EVENT_SSD_READY
																								
if __name__ == '__main__' :
	log.open(None, False)
	
	#global NUM_HOST_QUEUE
	#NUM_HOST_QUEUE = 1

	global NUM_CHANNELS
	global WAYS_PER_CHANNELS
	global NUM_WAYS
		
	NUM_CHANNELS = 8
	WAYS_PER_CHANNELS = 1
	NUM_WAYS = (NUM_CHANNELS * WAYS_PER_CHANNELS) 
	
	report = report_manager()
	
	print('initialize model')
	host_model = host_manager(NUM_HOST_CMD_TABLE)
	hic_model = hic_manager(NUM_CMD_EXEC_TABLE * NUM_HOST_QUEUE)
	
	nand_model = nand_manager(NUM_WAYS, nand_info)
	nfc_model = nfc(NUM_CHANNELS, WAYS_PER_CHANNELS)
		
	print('initialize fw module')	
	hil_module = hil_manager(hic_model)
	ftl_module = ftl_zns_manager(NUM_WAYS, hic_model)
	fil_module = fil_manager(nfc_model, hic_model)

	meta.config(NUM_WAYS)
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, 10, 19, 1, 2))
	blk_grp.add('user', block_manager(NUM_WAYS, 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))

	ftl_module.start()

	print('initialize workload')
	build_workload_zns()

	host_run()
	
	event_mgr.debug()

	exit = False

	wlm.set_group_active(NUM_HOST_QUEUE)
	wlm.print_all()
	index, total_num = wlm.get_info()
	workload_title = 'workload [%d/%d] processing'%(index+1, total_num)
	bar = Bar(workload_title, max=100)
	progress_save = 0
	
	report.set_model(wlm, host_model, hic_model, nfc_model, nand_model)
	report.set_module(hil_module, ftl_module, fil_module)
	report.open(index)
	#node = event_mgr.alloc_new_event(1000000000)
	#node.dest = event_dst.MODEL_HOST | event_dst.MODEL_KERNEL
	#node.code = event_id.EVENT_TICK
					
	while exit is False :
		event_mgr.increase_time()

		hil_module.handler()
		ftl_module.handler()
		fil_module.send_command_to_nfc()
		fil_module.handle_completed_nand_ops()
																
		if event_mgr.head is not None :
			node = event_mgr.head

			something_happen = False

			if event_mgr.timetick >= node.time :
				# start first node					
				event_mgr.print_log_event(node, True)
				
				something_happen = True
				
				if node.dest & event_dst.MODEL_HOST :
					host_model.event_handler(node)					
				if node.dest & event_dst.MODEL_HIC :
					hic_model.event_handler(node)
				if node.dest & event_dst.MODEL_NAND :
					nand_model.event_handler(node)
				if node.dest & event_dst.MODEL_NFC :
					nfc_model.event_handler(node)
				if node.dest & event_dst.MODEL_KERNEL :
					report.log(node, host_model.host_stat)
					#node = event_mgr.alloc_new_event(1000000000)
					#node.dest = event_dst.MODEL_HOST | event_dst.MODEL_KERNEL
					#node.code = event_id.EVENT_TICK
										
				event_mgr.delete_node(0)
				event_mgr.prev_time = event_mgr.timetick

				# show the progress status of current workload			
				progress = wlm.get_progress(async_group = False)
				if progress_save != progress :
					progress_save = progress
					bar.index = progress
					bar.next()
					
				if progress == 99 :
					ftl_module.disable_background()
					report.disable()
					
				# end first node operation
			else : 
				if something_happen != True :
					hil_module.handler()
					ftl_module.handler()
					fil_module.send_command_to_nfc()
					fil_module.handle_completed_nand_ops()
						
					# accelerate event timer for fast simulation 
					time_gap = node.time - event_mgr.timetick
					if time_gap > 1000 :
						event_mgr.add_accel_time(200)		# increase 200ns
		else :
			pending_cmds = host_model.get_pending_cmd_num()
			
			if pending_cmds > 0 :
				print('\npending command : %d'%pending_cmds)
				host_model.debug()
				ftl_module.debug()
				
			if True:							
				print('\nrun time : %u ns [%f s]'%(event_mgr.timetick, event_mgr.timetick / 1000000000))
		
				report.close()
				report.show_result()
				report.build_html(True)
				report.show_debug_info()
										
				bar.finish()			
				print('press the button to run next workload')									
				name = input()
				if wlm.goto_next_workload(async_group = False) == True :
					index, total_num = wlm.get_info()
					workload_title = 'workload [%d/%d] processing'%(index+1, total_num)
					bar = Bar(workload_title, max=100)
					
					event_mgr.timetick = 0
					host_model.host_stat.clear()
					nfc_model.clear_statistics()
											
					node = event_mgr.alloc_new_event(0)
					node.dest = event_dst.MODEL_HOST
					node.code = event_id.EVENT_SSD_READY
					
					ftl_module.enable_background()
					
					report.open(index)
				else :
					exit = True
									
	bar.finish()
	log.close()
	report.close()	
			