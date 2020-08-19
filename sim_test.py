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
from model.ftl import *
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

from progress.bar import Bar

log_time_data = {}

def init_log_time() :
	log_time_data['hil'] = 0
	log_time_data['ftl'] = 0
	log_time_data['fil'] = 0
	log_time_data['model'] = 0

	log_time_data['start_time'] = time.time()

def test_ftl_write() :
	qid = 0
	cmd_tag = 0
	sector_count = 64
	
	# 1st ftl command
	ftl_cmd = ftl_cmd_desc()
	ftl_cmd.code = HOST_CMD_WRITE
	ftl_cmd.lba = 0
	ftl_cmd.sector_count = sector_count
	ftl_cmd.cmd_tag = cmd_tag
	ftl_cmd.qid = qid
					
	# allocated buffer for write commmnad
	num_buffer = int(sector_count / SECTORS_PER_CHUNK)
	buffer_ids, ret_val = bm.get_buffer(BM_WRITE, qid, cmd_tag, num_buffer)
	
	ftl_module.hic_model.rx_buffer_done = ftl_module.hic_model.rx_buffer_done + buffer_ids
	
	# send command to ftl								
	hil2ftl_low_queue.push(ftl_cmd)	

	# 2nd ftl command
	cmd_tag = 1
	sector_count = 16
	
	ftl_cmd = ftl_cmd_desc()
	ftl_cmd.code = HOST_CMD_WRITE
	ftl_cmd.lba = 64
	ftl_cmd.sector_count = sector_count
	ftl_cmd.cmd_tag = cmd_tag
	ftl_cmd.qid = qid
			
	# allocated buffer for write commmnad
	num_buffer = int(sector_count / SECTORS_PER_CHUNK)
	buffer_ids, ret_val = bm.get_buffer(BM_WRITE, qid, cmd_tag, num_buffer)
	
	ftl_module.hic_model.rx_buffer_done = ftl_module.hic_model.rx_buffer_done + buffer_ids
	
	# send command to ftl								
	hil2ftl_low_queue.push(ftl_cmd)	

def test_ftl_read() :
	way = 0
	block = 1
	page = 1
	address = way * CHUNKS_PER_WAY + block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE

	meta.map_table[0] = address 
	meta.map_table[1] = address + 1

	way = 1
	block = 1
	page = 1
	address = way * CHUNKS_PER_WAY + block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE
		
	meta.map_table[2] = address
	meta.map_table[3] = address + 1
	
	# 3rd ftl command
	cmd_tag = 2
	sector_count = 24
	
	ftl_cmd = ftl_cmd_desc()
	ftl_cmd.code = HOST_CMD_READ
	ftl_cmd.lba = 8
	ftl_cmd.sector_count = sector_count
	ftl_cmd.cmd_tag = cmd_tag
	ftl_cmd.qid = 0
								
	# send command to ftl								
	hil2ftl_high_queue.push(ftl_cmd)	

def test_nfc() :
	# 1st cmd	
	way = 0
	block = 1
	page = 10
	address = block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE

	cmd_index = 0
	cmd_desc = nandcmd_table.table[cmd_index]
	cmd_desc.way = way
	cmd_desc.code = 2		# NFC_CMD_WRITE
	cmd_desc.nand_addr = address
	cmd_desc.chunk_num = 2
	bm_id1, ret_val = bm.get_buffer(BM_WRITE, 0, 0)
	bm.set_data(bm_id1[0], 256, 128)
	cmd_desc.buffer_ids = cmd_desc.buffer_ids + bm_id1

	bm_id2, ret_val = bm.get_buffer(BM_WRITE, 0, 0)
	bm.set_data(bm_id2[0], 512, 0)
	cmd_desc.buffer_ids = cmd_desc.buffer_ids + bm_id2
	cmd_desc.seq_num = 0

	nfc_model.fil2nfc_queue[way].push(cmd_index)
		
	node = event_mgr.alloc_new_event(0)
	node.dest = event_dst.MODEL_NFC
	node.nand_id = way

	# 2nd cmd
	way = 1
	block = 0
	page = 128
	address = block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE

	cmd_index = 1
	cmd_desc = nandcmd_table.table[cmd_index]
	cmd_desc.way = way
	cmd_desc.code = 1		# NFC_CMD_READ
	cmd_desc.nand_addr = address
	cmd_desc.chunk_num = 2
	cmd_desc.seq_num = 1

	nfc_model.fil2nfc_queue[way].push(cmd_index)

	#node = event_mgr.alloc_new_event(0)
	#node.dest = event_dst.MODEL_NFC
	#node.nand_id = way

def test_fil_erase() :	
	way = 1
	block = 1
	address = block * CHUNKS_PER_BLOCK
	
	cmd_index = nandcmd_table.get_free_slot()
	cmd_desc = nandcmd_table.table[cmd_index]
	cmd_desc.op_code = FOP_SET_MODE
	cmd_desc.way = way
	cmd_desc.nand_addr = address
	cmd_desc.chunk_num = 0
	cmd_desc.option = NAND_MODE_SLC
	cmd_desc.seq_num = 0

	ftl2fil_queue.push(cmd_index)
		
	cmd_index = nandcmd_table.get_free_slot()
	cmd_desc = nandcmd_table.table[cmd_index]
	cmd_desc.op_code = FOP_ERASE
	cmd_desc.way = way
	cmd_desc.nand_addr = address
	cmd_desc.chunk_num = 0
	cmd_desc.seq_num = 1

	ftl2fil_queue.push(cmd_index)
										
def test_fil_program_read() :
	# 1st cmd	
	way = 0
	block = 1
	page = 10
	address = block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE	

	qid = 0
	cid = 0

	cmd_index = nandcmd_table.get_free_slot()
	cmd_desc = nandcmd_table.table[cmd_index]
	cmd_desc.op_code = FOP_GC_WRITE
	cmd_desc.way = way
	cmd_desc.nand_addr = address
	cmd_desc.chunk_num = 2
	bm_id, ret_val = bm.get_buffer(BM_WRITE, qid, cid, 2)
	bm.set_data(bm_id[0], 256, 128)
	bm.set_data(bm_id[1], 512, 0)

	cmd_desc.buffer_ids = cmd_desc.buffer_ids + bm_id
	cmd_desc.seq_num = 0

	ftl2fil_queue.push(cmd_index)
		
	# 2nd cmd
	way = 0
	block = 0
	page = 128
	address = block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE

	cmd_index = nandcmd_table.get_free_slot()
	cmd_desc = nandcmd_table.table[cmd_index]
	cmd_desc.op_code = FOP_GC_READ
	cmd_desc.way = way
	cmd_desc.nand_addr = address
	cmd_desc.chunk_num = 2
	cmd_desc.seq_num = 1

	ftl2fil_queue.push(cmd_index)
																								
if __name__ == '__main__' :
	log.open(None, True)
	
	print('initialize model')
	host_model = host_manager(NUM_HOST_CMD_TABLE)
	hic_model = hic_manager(NUM_CMD_EXEC_TABLE)
	
	nand_model = nand_manager(NUM_WAYS, nand_info)
	nfc_model = nfc(NUM_CHANNELS, WAYS_PER_CHANNELS)
		
	print('initialize fw module')	
	hil_module = hil_manager(hic_model)
	ftl_module = ftl_manager(NUM_WAYS, hic_model)
	fil_module = fil_manager(nfc_model, hic_model)
	
	meta.config(NUM_WAYS)
	blk_grp.add('meta', block_manager(NUM_WAYS, None, 1, 9))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 19, 1, 2))
	blk_grp.add('user', block_manager(NUM_WAYS, None, 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))
		
	ftl_module.start()
	
	test_ftl_write()
	#test_ftl_read()						
						
	#test_fil_erase()
	#test_fil_program_read()	
	
	#test_nfc()
	
	event_mgr.debug()

	exit = False
	
	node = event_mgr.alloc_new_event(0)
	node.dest = event_dst.MODEL_KERNEL
	node.code = event_id.EVENT_TICK

	init_log_time()
										
	while exit is False :
		event_mgr.increase_time()
		
		#hil_module.handler(log_time = log_time_data)
		ftl_module.handler(log_time = log_time_data)
		fil_module.handler(log_time = log_time_data)
																														
		if event_mgr.head is not None :
			node = event_mgr.head

			something_happen = False

			if event_mgr.timetick >= node.time :
				# start first node									
				something_happen = True
				
				#if node.dest & event_dst.MODEL_HOST :
				#	host_model.event_handler(node)					
				#if node.dest & event_dst.MODEL_HIC :
				#	hic_model.event_handler(node)
				if node.dest & event_dst.MODEL_NAND :
					nand_model.event_handler(node)
				if node.dest & event_dst.MODEL_NFC :
					nfc_model.event_handler(node)
				if node.dest & event_dst.MODEL_KERNEL :
					#node = event_mgr.alloc_new_event(1000000000)
					#node.dest = event_dst.MODEL_HOST | event_dst.MODEL_KERNEL
					#node.code = event_id.EVENT_TICK
					print('......')
										
				event_mgr.delete_node(0)
				event_mgr.prev_time = event_mgr.timetick
					
				# end first node operation
			else : 
				if something_happen != True :
					hil_module.handler(log_time = log_time_data)
					ftl_module.handler(log_time = log_time_data)
					fil_module.handler(log_time = log_time_data)
						
					# accelerate event timer for fast simulation 
					time_gap = node.time - event_mgr.timetick
					if time_gap > 1000 :
						event_mgr.add_accel_time(200)		# increase 200ns

		else :	
			#host_model.host_stat.print(event_mgr.timetick)			
			nfc_model.print_cmd_descriptor()
			nfc_model.print_ch_statistics()
			nfc_model.print_way_statistics()
			
			print('\npress the button to run next test')									
			name = input()
			exit = True
								
	log.close()	
			