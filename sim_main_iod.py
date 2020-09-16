#!/usr/bin/python

import os
import sys
import time

from model.host import host_manager
from model.hic import hic_manager

from model.nand import nand_manager
from model.nfc import nfc

from model.hil import hil_manager
from model.ftl_iod import *
from model.fil import fil_manager
from model.nand import *

from model.workload import *

from config.sim_config import *
from config.ssd_param import *

from model.buffer import *
from model.queue import *
from model.nandcmd import *

from sim_event import *
from sim_system import *
from sim_eval import *
from sim_log import *
from sim_report import *

from progress.bar import Bar

bar = None
progress_save = 0

def init_progress() :
	global progress_save
	global bar
		
	index, total_num = wlm.get_info()
	workload_title = 'workload [%d/%d] processing'%(index+1, total_num)
	bar = Bar(workload_title, max=100)
	progress_save = 0

	return index
	
def check_progress() :
	global progress_save
	
	progress = wlm.get_progress(async_group = False)
	if progress_save != progress :
		progress_save = progress
		bar.index = progress
		bar.next()
		
	return progress+1

def build_workload_gc() :
	wlm.set_capacity(range_16GB)
	
	if NUM_HOST_QUEUE >= 2 :
		wlm.add_group(NUM_HOST_QUEUE - 1)
	
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16MB, 128, 128, 16, WL_SIZE_MB, 0, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16MB, 128, 128, 16, WL_SIZE_MB, 100, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16MB, 32, 32, 8, WL_SIZE_MB, 100, True))

	wlm.set_workload(workload(WL_RAND_WRITE, 0, range_16MB, 128, 128, 16, WL_SIZE_MB, 0, True), 1)
	wlm.set_workload(workload(WL_RAND_WRITE, 0, range_16MB, 128, 128, 32, WL_SIZE_MB, 0, True, True), 1)
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16GB, 32, 32, 8, WL_SIZE_MB, 0, True, True), 1)
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16GB, 32, 32, 8, WL_SIZE_MB, 100, True), 1)
		
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16MB, 8, 8, 16, WL_SIZE_MB, 0, True), 2)
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16MB, 64, 64, 32, WL_SIZE_MB, 100, True), 2)

def build_workload_multiqueue() :
	wlm.set_capacity(range_16GB)
	
	if NUM_HOST_QUEUE >= 2 :
		wlm.add_group(NUM_HOST_QUEUE - 1)
	
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16MB, 128, 128, 16, WL_SIZE_MB, 0, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16MB, 128, 128, 16, WL_SIZE_MB, 100, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16MB, 32, 32, 8, WL_SIZE_MB, 100, True))

	wlm.set_workload(workload(WL_RAND_WRITE, 0, range_16MB, 128, 128, 16, WL_SIZE_MB, 0, True), 1)
	wlm.set_workload(workload(WL_RAND_WRITE, 0, range_16MB, 128, 128, 32, WL_SIZE_MB, 0, True), 1)
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16GB, 32, 32, 8, WL_SIZE_MB, 0, True, True), 1)
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16GB, 32, 32, 8, WL_SIZE_MB, 100, True), 1)
		
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16MB, 8, 8, 16, WL_SIZE_MB, 0, True), 2)
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16MB, 64, 64, 32, WL_SIZE_MB, 100, True), 2)
		
def host_run() :
	node = event_mgr.alloc_new_event(0)
	node.dest = event_dst.MODEL_HOST
	node.code = event_id.EVENT_SSD_READY
																								
if __name__ == '__main__' :
	log.open(None, False)
	
	global NUM_HOST_QUEUE
	global NUM_CHANNELS
	global WAYS_PER_CHANNELS
	global NUM_WAYS
	
	NUM_HOST_QUEUE = 3		
	NUM_CHANNELS = 8
	WAYS_PER_CHANNELS = 1
	NUM_WAYS = (NUM_CHANNELS * WAYS_PER_CHANNELS) 
	
	report = report_manager()
	
	print('initialize model')
	ns_percent = [10, 40, 50]
	ns_maxlba = []
	for percent in ns_percent :
		ns_maxlba.append(int(NUM_LBA * percent / 100))
			
	host_model = host_manager(NUM_HOST_CMD_TABLE, NUM_HOST_QUEUE, ns_maxlba)
	hic_model = hic_manager(NUM_CMD_EXEC_TABLE * NUM_HOST_QUEUE, NUM_HOST_QUEUE)
	
	nand_info = nand_config(nand_256gb_g3)		
	nand_model = nand_manager(NUM_WAYS, nand_info)
	nfc_model = nfc(NUM_CHANNELS, WAYS_PER_CHANNELS, nand_info)

	set_ctrl('workload', wlm)
	set_ctrl('host', host_model)
	set_ctrl('hic', hic_model)
	set_ctrl('nfc', nfc_model)
	set_ctrl('nand', nand_model)
	
	print('initialize meta')
	bits_per_cell, bytes_per_page, pages_per_block, blocks_per_way = nand_model.get_nand_dimension()
	ftl_nand = ftl_nand_info(bits_per_cell, bytes_per_page, pages_per_block, blocks_per_way)
	nand_mode = nand_cell_mode[bits_per_cell]

	meta.config(NUM_LBA, NUM_WAYS, ftl_nand)
	namespace_mgr = namespace_manager(NUM_LBA, ns_percent)	
																
	print('initialize fw module')
	hil_module = hil_manager()
	ftl_module = ftl_iod_manager(namespace_mgr)
	fil_module = fil_manager()

	set_fw('hil', hil_module)
	set_fw('ftl', ftl_module)
	set_fw('fil', fil_module)

	blk_name = ['user1', 'user2', 'user3']
	blk_grp.add('meta', block_manager(NUM_WAYS, None, 1, 9, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, NAND_MODE_SLC, ftl_nand))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 19, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, NAND_MODE_SLC, ftl_nand))
	blk_grp.add(blk_name[0], block_manager(int(NUM_WAYS/2), [0, 1, 2, 3], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, nand_mode, ftl_nand))
	blk_grp.add(blk_name[1], block_manager(int(NUM_WAYS/4), [4, 5], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, nand_mode, ftl_nand))
	blk_grp.add(blk_name[2], block_manager(int(NUM_WAYS/4), [6, 7], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, nand_mode, ftl_nand))

	for nsid in range(namespace_mgr.get_num()) :	
		ns = namespace_mgr.get(nsid)
		ns.set_blk_name(blk_name[nsid])

	ftl_module.start()

	print('initialize workload')
	build_workload_gc()
	#build_workload_multiqueue()

	host_run()
	
	event_mgr.debug()

	exit = False

	wlm.set_group_active(NUM_HOST_QUEUE)
	wlm.print_all()
	index = init_progress()
	
	report.open(index)
	#node = event_mgr.alloc_new_event(1000000000)
	#node.dest = event_dst.MODEL_HOST | event_dst.MODEL_KERNEL
	#node.code = event_id.EVENT_TICK

	init_eval_time()
										
	while exit is False :
		event_mgr.increase_time()

		hil_module.handler()
		ftl_module.handler()
		fil_module.handler()
																
		if event_mgr.head is not None :
			node = event_mgr.head

			something_happen = False

			if event_mgr.timetick >= node.time :
				# start first node
				start_eval_module('model')
													
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
				
				end_eval_module('model')		
				# end first node operation
			else : 
				if something_happen != True :
					if (event_mgr.timetick - event_mgr.prev_time) >= 3 :
						hil_module.handler()
						ftl_module.handler()
						fil_module.handler()
												 	 	
						# accelerate event timer for fast simulation 
						event_mgr.add_accel_time(node.time - event_mgr.timetick)
						
						# show the progress status of current workload
						if check_progress() == 100 and host_model.get_pending_cmd_num() == 0 :
							ftl_module.flush_request()
							ftl_module.disable_background()
							report.disable()						
		else :
			pending_cmds = host_model.get_pending_cmd_num()
			
			if pending_cmds > 0 :
				print('\npending command : %d'%pending_cmds)
				host_model.debug()
				ftl_module.debug()
				
			if True:
				print_eval_time()
				
				print('run time : %u ns [%f s]'%(event_mgr.timetick, event_mgr.timetick / 1000000000))
		
				report.close()
				report.show_result()
				report.build_html(True)
				report.show_debug_info()
										
				bar.finish()			
				print('press the button to run next workload')									
				name = input()
				if wlm.goto_next_workload(async_group = False) == True :
					index = init_progress()
					
					event_mgr.timetick = 0
					host_model.host_stat.clear()
					nfc_model.clear_statistics()
					
					if wlm.get_force_gc() == True :
						meta.print_valid_data(0, 20)
						for index in range(namespace_mgr.get_num()) :
							ns = namespace_mgr.get(index)	
							blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)
							blk_manager.set_exhausted_status(True)
						
					node = event_mgr.alloc_new_event(0)
					node.dest = event_dst.MODEL_HOST
					node.code = event_id.EVENT_SSD_READY
					
					ftl_module.enable_background()
					
					init_eval_time()
					
					report.open(index)
				else :
					exit = True
									
	bar.finish()
	log.close()
	report.close()	
			