#!/usr/bin/python

import os
import sys
import time

from model.host import host_manager
from model.hic import hic_manager

from model.nand import nand_manager
from model.nfc import nfc

from model.hil import hil_manager
from model.ftl import *
from model.fil import fil_manager
from model.nand import *

from model.workload import *

from model.vcd_ssd import *

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
	wlm.set_capacity('16GiB')
	
	if NUM_HOST_QUEUE >= 2 :
		wlm.add_group(NUM_HOST_QUEUE - 1)
	
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, '1GiB', 128, 128, '1GiB', WL_TYPE_SIZE, 0, True, False))
	#wlm.set_workload(workload(WL_SEQ_WRITE, 0, '1GiB', 128, 128, '1GiB', WL_TYPE_SIZE, 0, True, False))
	#wlm.set_workload(workload(WL_SEQ_WRITE, 0, '1GiB', 64, 64, '1GiB', WL_TYPE_SIZE, 0, True, False))
	wlm.set_workload(workload(WL_SEQ_READ, 0, '1GiB', 128, 128, '1GiB', WL_TYPE_SIZE, 0, True, False))
	wlm.set_workload(workload(WL_SEQ_READ, 0, '1GiB', 64, 64, '1GiB', WL_TYPE_SIZE, 0, True, False))	
	wlm.set_workload(workload(WL_SEQ_READ, 0, '1GiB', 4, 4, '1GiB', WL_TYPE_SIZE, 0, True, False))
	wlm.set_workload(workload(WL_SEQ_READ, 0, '16MiB', 128, 128, '4MiB', WL_TYPE_SIZE, 0, True, False))
		
	wlm.set_workload(workload(WL_RAND_WRITE, 0, '16MiB', 4, 4, '32MiB', WL_TYPE_SIZE, 0, True, False), 1)
	wlm.set_workload(workload(WL_RAND_READ, 0, '16MiB', 64, 64, '32MiB', WL_TYPE_SIZE, 100, True, True), 1)

	wlm.set_workload(workload(WL_RAND_WRITE, 0, '16MiB', 4, 4, '16MiB', WL_TYPE_SIZE, 0, True, False), 2)
	wlm.set_workload(workload(WL_RAND_READ, 0, '16MiB', 64, 64, '16MiB', WL_TYPE_SIZE, 100, True, False), 2)

def build_workload_multiqueue() :
	wlm.set_capacity('16GiB')
	
	if NUM_HOST_QUEUE >= 2 :
		wlm.add_group(NUM_HOST_QUEUE - 1)
	
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, '16MiB', 128, 128, '16MiB', WL_TYPE_SIZE, 0, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, '16MiB', 128, 128, '16MiB', WL_TYPE_SIZE, 0, True))

	wlm.set_workload(workload(WL_SEQ_WRITE, 0, '16GiB', 128, 128, '32MiB', WL_TYPE_SIZE, 0, True), 1)
	wlm.set_workload(workload(WL_SEQ_READ, 0, '16GiB', 128, 128, '16MiB', WL_TYPE_SIZE, 100, True), 1)
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, '16GiB', 32, 32, '8MiB', WL_TYPE_SIZE, 0, True), 1)
	wlm.set_workload(workload(WL_SEQ_READ, 0, '16GiB', 32, 32, '8MiB', WL_TYPE_SIZE, 100, True), 1)
		
	wlm.set_workload(workload(WL_RAND_WRITE, 0, '16MiB', 8, 8, '16MiB', WL_TYPE_SIZE, 0, True), 2)
	wlm.set_workload(workload(WL_RAND_READ, 0, '16MiB', 64, 64, '32MiB', WL_TYPE_SIZE, 100, True), 2)

def build_workload_zns() :
	wlm.set_capacity('16GiB')
		
	wlm.set_workload(workload(WL_ZNS_WRITE, 0, '16GiB', 128, 128, '1GiB', WL_TYPE_SIZE, 0, True, False))
	wlm.set_workload(workload(WL_ZNS_READ, 0, '16GiB', 128, 128, '128MiB', WL_TYPE_SIZE, 0, True, False))
				
def host_run() :
	node = event_mgr.alloc_new_event(0)
	node.dest = event_dst.MODEL_HOST
	node.code = event_id.EVENT_SSD_READY
																								
if __name__ == '__main__' :
	log.open(None, False)
															
	load_ssd_config_xml('./config/ssd_config.xml')
	print_setting_info('xml parameter value')

	NUM_HOST_QUEUE = ssd_param.NUM_HOST_QUEUE
	NUM_CHANNELS = ssd_param.NUM_CHANNELS
	WAYS_PER_CHANNELS = ssd_param.WAYS_PER_CHANNELS
	NUM_WAYS = ssd_param.NUM_WAYS 
	
	'''
	# don't use xml configuration'
	nand_info = nand_config(nand_256gb_g4)
	'''
	# use xml configuration
	nand_info = nand_config(None)
	#ssd_param.NAND_MODEL = '256gb_g4'
	nand_info.load_xml('./config/nand_config.xml', ssd_param.NAND_MODEL)
	nand_info.print_type(report_title = 'xml nand type[%s]'%ssd_param.NAND_MODEL)
	nand_info.print_param(report_title = 'xml nand parameter[%s]'%ssd_param.NAND_MODEL)	
																							
	report = report_manager()
	ssd_vcd_open('ssd.vcd', NUM_CHANNELS, WAYS_PER_CHANNELS)
	
	print('initialize model')
	host_model = host_manager(NUM_HOST_CMD_TABLE, NUM_HOST_QUEUE, [NUM_LBA])
	hic_model = hic_manager(NUM_CMD_EXEC_TABLE * NUM_HOST_QUEUE, NUM_HOST_QUEUE)
	
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
																		
	print('initialize fw module')	
	hil_module = hil_manager()
	ftl_module = ftl_manager(NUM_WAYS)
	fil_module = fil_manager()

	set_fw('hil', hil_module)
	set_fw('ftl', ftl_module)
	set_fw('fil', fil_module)

	blk_grp.add('meta', block_manager(NUM_WAYS, None, 1, 9, 1, 3, NAND_MODE_SLC, ftl_nand))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 39, 1, 3, NAND_MODE_SLC, ftl_nand))
	blk_grp.add('user', block_manager(NUM_WAYS, None, 40, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, nand_mode, ftl_nand))

	ftl_module.start()

	print('initialize workload')
	build_workload_gc()
	#build_workload_multiqueue()
	#build_workload_zns()

	host_run()
	
	exit = False

	wlm.set_group_active(NUM_HOST_QUEUE)
	wlm.print_all()
	index = init_progress()
		
	report.open(index)
	#node = event_mgr.alloc_new_event(1000000000)
	#node.dest = event_dst.MODEL_HOST | event_dst.MODEL_KERNEL
	#node.code = event_id.EVENT_TICK
															
	init_eval_time()
	
	accel_num = 0
											
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
						accel_num = accel_num + 1
						
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
				#print('acceleration num : %d'%accel_num)
		
				report.close()
				report.show_result()
				report.build_html(True)
				report.show_debug_info()
										
				bar.finish()
				
				key_wait = True 
				while key_wait == True :			
					key_value = input('press the button [q:quit, r:run next workload, s:save meta]')
					if key_value == 'q' :
						key_wait = False
						exit = True					
					elif key_value == 'r' :
						key_wait = False
						if wlm.goto_next_workload(async_group = False) == True :
							index = init_progress()
							
							event_mgr.timetick = 0
							host_model.host_stat.clear()
							nfc_model.clear_statistics()
							
							if wlm.get_force_gc() == True :
								meta.print_valid_data(0, 20)
								blk_manager = blk_grp.get_block_manager_by_name('user')
								blk_manager.set_exhausted_status(True)
								
							node = event_mgr.alloc_new_event(0)
							node.dest = event_dst.MODEL_HOST
							node.code = event_id.EVENT_SSD_READY
							
							ftl_module.enable_background()
							
							init_eval_time()
												
							accel_num = 0
							
							report.open(index)
						else :
							exit = True	
					elif key_value == 's':
							print('save meta info')					
									
	bar.finish()
	ssd_vcd_close()
	log.close()
	report.close()	
			