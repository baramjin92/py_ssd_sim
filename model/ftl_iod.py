 #!/usr/bin/python

import os
import sys
import time

import random
import numpy as np
import pandas as pd

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.buffer import *
from model.buffer_cache import *
from model.queue import *
from model.nandcmd import *
from model.block_manager import *
from model.namespace import *
from model.ftl_meta import *

from sim_event import *

# ftl translates logical block address to physical address of nand

def log_print(message) :
	event_log_print('[ftl iod]', message)

def measure_time(func) :
	def measure_time(*args, **kwargs) :
		start_time = time.time()
		result = func(*args, **kwargs)
		kwargs['log_time']['ftl'] = kwargs['log_time']['ftl'] + (time.time() - start_time)
		return result
	
	return measure_time
																																
class ftl_iod_manager :
	def __init__(self, hic) :
		# there is no NUM_WAY parameter in IO determinism.
		# blk_manager has this value, if we know name of blk_manager, we can use it in each namespace.
		
		self.name = 'iod'
				
		# register hic now in order to use interface queue									
		self.hic_model = hic
		self.chunks_per_page = CHUNKS_PER_PAGE
		
		self.run_mode = True
		
		self.seq_num = 0
																																																		
		self.ftl_stat = ftl_iod_statistics()
		
	def start(self) :
		print('start iod ftl')
		
		for index in range(namespace_mgr.get_num()) :
			ns = namespace_mgr.get(index)

			blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)
			ns.logical_blk = super_block(blk_manager.num_way, ns.blk_name+' host', SB_OP_WRITE)
			ns.gc_blk = super_block(blk_manager.num_way, ns.blk_name+' gc', SB_OP_WRITE)
			ns.gc_src_blk = super_block(blk_manager.num_way, ns.blk_name+' victim', SB_OP_READ)						
				
	def enable_background(self) :
		self.run_mode = True
		
	def disable_background(self) :
		self.run_mode = False	
	
	def try_to_fetch_cmd(self) : 
		# check high priority queue
		if hil2ftl_high_queue.length() > 0 :
			# check write content of previous cmd and run do_write()

			# fetch ftl command and parse lba and sector count for chunk 
			ftl_cmd = hil2ftl_high_queue.pop()
			
			ns = namespace_mgr.get(ftl_cmd.qid)
		
			# ftl_cmd.code should be HOST_CMD_READ				
			lba_start = namespace_mgr.lba2meta_addr(ftl_cmd.qid, ftl_cmd.lba)
			lba_end = lba_start + ftl_cmd.sector_count - 1

			# in order to read from nand, read command information is updated			
			ns.num_chunks_to_read = ftl_cmd.sector_count / SECTORS_PER_CHUNK
			ns.read_start_chunk = lba_start / SECTORS_PER_CHUNK
			#ns.read_end_chunk = lba_end / SECTORS_PER_CHUNK			
			ns.read_queue_id = ftl_cmd.qid
			ns.read_cmd_tag = ftl_cmd.cmd_tag
	
			ns.read_cur_chunk = ns.read_start_chunk 			

			log_print('host cmd read - qid : %d, cid : %d'%(ftl_cmd.qid, ftl_cmd.cmd_tag))
										
			# set fetch flag of hic (it will be move from hil to ftl, because hil code is temporary one)
			self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)				 	 	 	 	 	
				 	 	 	 	 			 	 	 	 	 			 	 	 	 	 	
		# check low priority queue
		if hil2ftl_low_queue.length() > 0 :
			# we will change sequeuce of poping command from low queue, because we need to check the remained command 
			ftl_cmd = hil2ftl_low_queue.pop()

			if ftl_cmd.code == HOST_CMD_WRITE :				
				# write cmd should be saved for gathering write chunks in order to meet physical size of nand
				# actually qid and nsid is not same however we assume it is same in simulator
				ns = namespace_mgr.get(ftl_cmd.qid)
				if ns == None :
					#hil2ftl_low_queue.push_first(ftl_cmd)
					print('error : can not get namespace')
				else :					
					ns.write_cmd_queue.push(ftl_cmd)
					ns.num_chunks_to_write = ns.num_chunks_to_write + int(ftl_cmd.sector_count / SECTORS_PER_CHUNK)

					self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)
					
				log_print('host cmd write')
			else :
				if ftl_cmd.code == HOST_CMD_TRIM :
					log_print('host cmd trim')	
					
					# self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)
				elif ftl_cmd.code == HOST_CMD_CALM :			
					log_print('host cmd calm')
	
					# flush remain data in order to prepare calm state
												
				self.hic_model.set_manual_completion(ftl_cmd.qid, ftl_cmd.cmd_tag)
																																				
		# save vcd file if option is activate

	def do_read(self, ns) :
		# look up map entry and get physical address
		lba_index = int(ns.read_cur_chunk)
		num_remain_chunks = ns.num_chunks_to_read
		next_map_entry = 0xFFFFFFFF
		num_chunks_to_read = 0
		
		# check free slots of nandcmd_table (use num_remian_chunks, there is assumption all chunks are not adjecent)
		if nandcmd_table.get_free_slot_num() < num_remain_chunks :
			return		
												
		while num_remain_chunks > 0 :
			if next_map_entry == 0xFFFFFFFF :
				# 1st address
				map_entry = meta.map_table[lba_index]
			else :
				# next address
				map_entry = next_map_entry
							
			num_chunks_to_read = num_chunks_to_read + 1
			num_remain_chunks = num_remain_chunks - 1
			
			if num_remain_chunks >= 1 :
				next_map_entry = meta.map_table[lba_index+1]			
				# check twice for adjacent read(same nand page address), it reduces the power and read latency from nand
				
				log_print('chunk : %d, map_entry : %x, next_map_entry : %x'%(lba_index, map_entry, next_map_entry))
				#log_print('map_entry : %x, next_map_entry : %x'%(int(map_entry/CHUNKS_PER_PAGE), int(next_map_entry/CHUNKS_PER_PAGE)))
				
				if next_map_entry == map_entry + 1 :
					if int(next_map_entry / CHUNKS_PER_PAGE) == int(map_entry / CHUNKS_PER_PAGE) :
						#log_print('do read : adjecent')

						# go to check next adjacent
						lba_index = lba_index + 1
						continue		
												
			# try to read with map_entry from nand, because next_map_entry is not adjacent
			self.seq_num = self.seq_num + 1
			
			way, block, page, end_chunk_offset = parse_map_entry(map_entry)
			# in order to calculate nand address, way and 
			nand_addr = build_map_entry(0, block, page, 0)
			start_chunk_offset = end_chunk_offset - (num_chunks_to_read - 1)

			# update lba_index for last chunk
			lba_index = lba_index + 1

			if nand_addr == 0 :
				print('do read - chunk : %d [offset : %d - num : %d], remain_num : %d, way : %d, nand_addr : %x, block : %d, page : %d'%(lba_index, start_chunk_offset, num_chunks_to_read, num_remain_chunks, way, nand_addr, block, page))
						
			# issue command to fil								
			# if we use buffer cache, we will check buffer id from cache instead of sending command to fil
			cache_hit = False
			if ENABLE_BUFFER_CACHE == True :
				cache_lba_index = ns.read_cur_chunk
				cache_results = []
				for index in range(num_chunks_to_read) :
					buffer_id, cache_hit = bm_cache.get_buffer_id(cache_lba_index)
					if cache_hit == True :
						cache_results.append([cache_lba_index, buffer_id])
					cache_lba_index = cache_lba_index + 1
						
				# if cache buffers are not all, evict cache buffer 	
				if len(cache_results) < num_chunks_to_read :
					for cache_info in cache_results :
						bm_cache.evict(cache_info[0])
					cache_hit = False
				else :
					# cache hit, return buffer id to hic
					for cache_info in cache_results :						
						self.hic_model.add_tx_buffer(ns.read_queue_id, cache_info[1])
					
					next_event = event_mgr.alloc_new_event(0)
					next_event.code = event_id.EVENT_USER_DATA_READY
					next_event.dest = event_dst.MODEL_HIC					
					 
			if cache_hit == False :
				# cache miss, send cmd to fil
				cmd_index = nandcmd_table.get_free_slot()
				cmd_desc = nandcmd_table.table[cmd_index]
				cmd_desc.op_code = FOP_USER_READ
				cmd_desc.way = way
				cmd_desc.nand_addr = nand_addr
				cmd_desc.chunk_offset = start_chunk_offset
				cmd_desc.chunk_num = num_chunks_to_read
				cmd_desc.seq_num = self.seq_num
				cmd_desc.cmd_tag = ns.read_cmd_tag
				cmd_desc.queue_id = ns.read_queue_id
				
				ftl2fil_queue.push(cmd_index)
								
			# reset variable for checking next chunk																																								
			next_map_entry = 0xFFFFFFFF
			num_chunks_to_read = 0

		# check remain chunk, if do_read can't finish because of lack of resource of buffer/controller
		ns.read_cur_chunk = lba_index
		ns.num_chunks_to_read = num_remain_chunks

	def check_write_buffer_done(self) :												
		# check for arrival of data and move buffer pointer to buffer list of namespace
		ns = None
		
		for index in range(len(self.hic_model.rx_buffer_done))  :
			buffer_id = self.hic_model.rx_buffer_done.pop(0)
			lca = bm.get_meta_data(buffer_id)
			lba = lca * SECTORS_PER_CHUNK
						
			# actually qid and nsid is not same however we assume it is same in simulator			
			qid, cmd_tag = bm.get_cmd_id(buffer_id)
			ns = namespace_mgr.get(qid)
			if ns == None :
				print ('error check write buffer done - lba : %d'%lba)
			ns.write_buffer.append(buffer_id)
			
		return ns
																																							
	def do_write(self, ns) :
		# do_write try to program data to nand
				
		sb = ns.logical_blk							
		num_chunks = ns.get_num_chunks_to_write()
		 		 		 					
		# check free slots of nandcmd_table
		# in order to send cell mode command, we need one more nandcmd slot
		if nandcmd_table.get_free_slot_num() < (num_chunks + 1) :
			return
							
		# get write cmd
		if ns.write_cmd_queue.length() == 0 :
			print('error namespace : %d'%ns.id)
		ftl_cmd = ns.write_cmd_queue.pop()
			
		# get new physical address from open block	
		way, block, page = sb.get_physical_addr()
		map_entry = build_map_entry(way, block, page, 0)
														
		# meta data update (meta datum are valid chunk bitmap, valid chunk count, map table
		# valid chunk bitamp and valid chunk count use in gc and trim 
		for index in range(num_chunks) :
			log_print('update meta data')
			# get old physical address info
			# lba_index is calculated by api of namespace
			lba_index = int(namespace_mgr.lba2meta_addr(ns.nsid, ftl_cmd.lba) / SECTORS_PER_CHUNK)
			old_physical_addr = meta.map_table[lba_index]
			
			# if we use buffer cache, we should check and evict buffer id from cache, in order to avoid mismatch of data
			if ENABLE_BUFFER_CACHE == True :		 
				bm_cache.evict(lba_index)
																																																					
			# validate "valid chunk bitmap", "valid chunk count", "map table" with new physical address
			meta.map_table[lba_index] = map_entry + index

			# CHUNKS_PER_PAGE is calculated in the MLC mode, we need to consider another cell mode
			chunk_index = build_chunk_index(page, index)
			meta.set_valid_bitmap(way, block, chunk_index)					
									
			# invalidate "valid chunk bitmap", "valid chunk count" with old physical address
			# if mapping address is 0, it is unmapped address 
			if old_physical_addr != 0 :
				# calculate way, block, page of old physical address
				old_way, old_nand_block, old_nand_page, old_chunk_offset = parse_map_entry(old_physical_addr)
				chunk_index = build_chunk_index(old_nand_page, old_chunk_offset)
				
				# return value of clear_valid_bitmap() is not correct in io determinism, use get_valid_sum_ext() 
				meta.clear_valid_bitmap(old_way, old_nand_block, chunk_index)
				valid_sum = meta.get_valid_sum_ext(old_nand_block, sb.ways)
				if valid_sum == 0 :
					log_print('move sb to erased block')
					blk_manager = blk_grp.get_block_manager_by_zone(old_nand_block, sb.ways) 
					blk_manager.release_block(old_nand_block)		
													
			# update lba and sector count of write command in order to check end of current write command 
			# chunk_index = chunk_index + 1
			
			ftl_cmd.sector_count = ftl_cmd.sector_count - SECTORS_PER_CHUNK
			ftl_cmd.lba = ftl_cmd.lba + SECTORS_PER_CHUNK
			
			if ftl_cmd.sector_count == 0 and ns.write_cmd_queue.length() > 0:
				# get next command from queue
				ftl_cmd = ns.write_cmd_queue.pop()
		
		# push first write commmand for remaine sector count
		if ftl_cmd.sector_count > 0 :
			ns.write_cmd_queue.push_first(ftl_cmd)
			
		self.seq_num = self.seq_num + 1

		# start nand cmd for fil
		nand_addr = get_nand_addr(map_entry)
		
		# change cell mode command
		cmd_index = nandcmd_table.get_free_slot()
		cmd_desc = nandcmd_table.table[cmd_index]
		cmd_desc.op_code = FOP_SET_MODE
		cmd_desc.way = way
		cmd_desc.nand_addr = nand_addr
		cmd_desc.chunk_num = 0
		cmd_desc.option = sb.get_cell_mode()
		cmd_desc.seq_num = self.seq_num
		
		ftl2fil_queue.push(cmd_index)

		# program command		
		cmd_index = nandcmd_table.get_free_slot()
		cmd_desc = nandcmd_table.table[cmd_index]
		cmd_desc.op_code = FOP_USER_WRITE
		cmd_desc.way = way
		cmd_desc.nand_addr = nand_addr
		cmd_desc.chunk_num = num_chunks
		cmd_desc.buffer_ids = []
		for index in range(num_chunks) :
			# buffer_id is allocated by hil, and data is saved by hic
			buffer_id = ns.write_buffer.pop(0)	
			cmd_desc.buffer_ids.append(buffer_id)				
		cmd_desc.seq_num = self.seq_num
		
		ftl2fil_queue.push(cmd_index)		
		#end nand cmd for fil
																								
		# update super page index and check status of closing block (end of super block)
		is_close, block_addr, way_list = sb.update_page()
		
		# the block number should be moved to closed block list in block manager
		if is_close == True  :
			# namespace has name of blk_manager, if we don't use slc buffer, we can get blk_manager by name'
			blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)
			blk_manager.set_close_block(block_addr)

		# update num_chunks_to_write
		ns.update_write_info(num_chunks)			
																																																				
		log_print('do write')

	def do_trim(self, lba, sector_count) :
		log_print('do trim - lba : %d, sector_count : %d'%(lba, sector_count))
		
		chunk_addr_start = lba / SECTORS_PER_CHUNK
		chunk_addr_end = (lba + sector_count - 1) / SECTORS_PER_CHUNK
		
		while chunk_addr_start <= chunk_addr_end :
			meta.map_table[chunk_addr_start] = 0xFFFFFFFF	
			chunk_addr_start = chunk_addr_start + 1

	def select_victim_block(self, ns, block_addr, way_list, cell_mode) :		
		if ns.gc_src_blk.is_open() == False :
			ns.gc_src_blk.open(block_addr, way_list, meta, cell_mode)
			return True
			
		return False	

	def do_gc_read(self, ns) :
		src_sb = ns.gc_src_blk
		
#		if ns.gc_issue_credit <= 0 :
#			return
		if src_sb.is_open() == False :		
			return
				
		if ns.gc_cmd_id.get_num_free_slot() < 8 :
			return 

		log_print('do gc read')

		issue_count = 0
		while issue_count < 4 and src_sb.is_open() == True :
									
			# get new physical address from open block	
			way, block, page = src_sb.get_physical_addr()
			chunk = build_chunk_index(page)
			
			page_bmp = meta.check_valid_bitmap(way, block, chunk)
			str = 'issue count : %d, way : %d, block : %d, page : %d bmp : 0x%08x '%(issue_count, way, block, page, page_bmp)
			if page_bmp > 0 :
				chunk_offset = -1
				num_chunks = 0
				for index in range(CHUNKS_PER_PAGE) :
					mask = 1 << index
					if page_bmp & mask == mask :
						num_chunks = num_chunks + 1
					elif num_chunks > 0 :
						# because of random write chunks are not adjacent, we send command to nand
						start_chunk_offset = chunk_offset - (num_chunks - 1)
						str = str + '[%d:%d] '%(start_chunk_offset, num_chunks)

						# send nand cmd to fil						
						self.seq_num = self.seq_num + 1
						nand_addr = build_map_entry(0, block, page, 0)

						queue_id, cmd_tag = ns.gc_cmd_id.get_slot()

						cmd_index = nandcmd_table.get_free_slot()
						cmd_desc = nandcmd_table.table[cmd_index]
						cmd_desc.op_code = FOP_GC_READ
						cmd_desc.way = way
						cmd_desc.nand_addr = nand_addr
						cmd_desc.chunk_offset = start_chunk_offset
						cmd_desc.chunk_num = num_chunks
						cmd_desc.seq_num = self.seq_num
						cmd_desc.cmd_tag = cmd_tag
						cmd_desc.queue_id = queue_id

						cmd_desc.gc_meta = []
						gc_meta = build_map_entry2(way, nand_addr, start_chunk_offset)
						for offset in range(num_chunks) :
							cmd_desc.gc_meta.append(gc_meta + offset) 
																				
						ftl2fil_queue.push(cmd_index)						
						
						ns.num_chunks_to_gc_read = ns.num_chunks_to_gc_read + num_chunks																																			
						num_chunks = 0	
					
					chunk_offset = chunk_offset + 1		

				if num_chunks > 0 :
					# send command to nand, all chunks is full 
					start_chunk_offset = chunk_offset - (num_chunks - 1)
					str = str + '[%d:%d] '%(start_chunk_offset, num_chunks)
					
					# send nand cmd to fil						
					self.seq_num = self.seq_num + 1
					nand_addr = build_map_entry(0, block, page, 0)

					queue_id, cmd_tag = ns.gc_cmd_id.get_slot()

					cmd_index = nandcmd_table.get_free_slot()
					cmd_desc = nandcmd_table.table[cmd_index]
					cmd_desc.op_code = FOP_GC_READ
					cmd_desc.way = way
					cmd_desc.nand_addr = nand_addr
					cmd_desc.chunk_offset = start_chunk_offset
					cmd_desc.chunk_num = num_chunks
					cmd_desc.seq_num = self.seq_num
					cmd_desc.cmd_tag = cmd_tag
					cmd_desc.queue_id = queue_id

					cmd_desc.gc_meta = []
					gc_meta = build_map_entry2(way, nand_addr, start_chunk_offset)
					for offset in range(num_chunks) :
						cmd_desc.gc_meta.append(gc_meta + offset) 
												
					ftl2fil_queue.push(cmd_index)						
			
					ns.num_chunks_to_gc_read = ns.num_chunks_to_gc_read + num_chunks																																				
					num_chunks = 0	
																														
				log_print(str)
				issue_count = issue_count + 1
				
#				ns.gc_issue_credit = ns.gc_issue_credit - 1
#				if ns.gc_issue_credit == 0 :
#					break
				
			is_close, block_addr, way_list = src_sb.update_page()						
								
	def do_gc_read_completion(self) :
		ns = None
		
		if fil2ftl_queue.length() > 0 :
			# fetch gc command and parse lba and sector count for chunk 
			queue_id, cmd_tag, buffer_ids, gc_meta = fil2ftl_queue.pop()

			# get ns by queue_id
			ns = namespace_mgr.get_by_qid(queue_id)

			gc_cmd = gc_cmd_desc(queue_id, cmd_tag)
						
			for buffer_id in buffer_ids :			
				# get old physical address info
				ns_lba_index = bm.get_meta_data(buffer_id)				
				gc_physical_addr = gc_meta.pop(0)
				
				gc_cmd.buffer_ids.append(buffer_id)
				gc_cmd.lba_index.append(ns_lba_index)
				gc_cmd.gc_meta.append(gc_physical_addr)
							
			gc_cmd.count = len(gc_cmd.buffer_ids)
				
			if gc_cmd.count > 0 :	
				ns.gc_cmd_queue.push(gc_cmd)
					
				ns.num_chunks_to_gc_read = ns.num_chunks_to_gc_read - gc_cmd.count
				ns.num_chunks_to_gc_write = ns.num_chunks_to_gc_write + gc_cmd.count 
											
			log_print('\ngc read result - nsid : %d, queue_id : %d, cmd id : %d, num_read : %d, num_write : %d, buf : %s'%(ns.nsid, queue_id, cmd_tag, ns.num_chunks_to_gc_read, ns.num_chunks_to_gc_write, str(buffer_ids)))

			#ns.gc_issue_credit = ns.gc_issue_credit + 1
				
		return ns

	def gc_gather_write_data(self, ns) :				
		ret_val = False
		
		if ns.num_chunks_to_gc_write < CHUNKS_PER_PAGE :
			return False		
		
		num_chunks = ns.num_chunks_to_gc_write
		
		queue_id, cmd_tag = ns.gc_cmd_id.get_slot() 											 											
		gc_cmd_comp = gc_cmd_desc(queue_id, cmd_tag)
												
		# get write cmd
		gc_cmd = ns.gc_cmd_queue.pop()
													
		for index in range(num_chunks) :
			buf_id = gc_cmd.buffer_ids.pop(0)
			gc_meta = gc_cmd.gc_meta.pop(0) 
			ns_lba_index = gc_cmd.lba_index.pop(0)
			
			# get old physical address info
			lba_index = int(namespace_mgr.lba2meta_addr(ns.nsid, ns_lba_index * SECTORS_PER_CHUNK) / SECTORS_PER_CHUNK)			
			old_physical_addr = meta.map_table[lba_index]

			# compare physical address
			if old_physical_addr != gc_meta :
				print('gc compaction - lbai : %d, meta : %s, gc_meta : %s'%(lba_index, str(parse_map_entry(old_physical_addr)), str(parse_map_entry(gc_meta))))
				
				bm.release_buffer(buf_id)
				
				ns.num_chunks_to_gc_write = ns.num_chunks_to_gc_write - 1			
			else :																
				# move to compaction cmd set		
				gc_cmd_comp.buffer_ids.append(buf_id)
				gc_cmd_comp.gc_meta.append(gc_meta)
				gc_cmd_comp.lba_index.append(ns_lba_index)
				gc_cmd_comp.count = gc_cmd_comp.count + 1														
																										
			# update count of gc command in order to check end of current gc command 			
			gc_cmd.count = gc_cmd.count - 1

			if gc_cmd.count == 0 :
				# release cmd id
				ns.gc_cmd_id.release_slot(gc_cmd.cmd_id)
			
				if ns.gc_cmd_queue.length() > 0:			
					# get next command from queue
					gc_cmd = ns.gc_cmd_queue.pop()

			if gc_cmd_comp.count > CHUNKS_PER_PAGE :
				ret_val = True
				break						
						
		# push write commmand for remain sector count
		if gc_cmd.count > 0 :
			ns.gc_cmd_queue.push_first(gc_cmd)
			
		ns.gc_cmd_queue.push_first(gc_cmd_comp)	
		
		return ret_val
						
	def do_gc_write(self, ns) :
		# do_write try to program data to nand
		buffer_ids = []
		
		sb = ns.gc_blk
		# check preparation of target block of nand
		if sb.is_open() == False :
			print('namespace %d -  %s superblock is not open'%(ns.nsid, sb.name))
			return
		
		num_chunks = sb.get_num_chunks_to_write(ns.num_chunks_to_gc_write)
		 						
		# check free slots of nandcmd_table
		# in order to send cell mode command, we need one more nandcmd slot		
		if nandcmd_table.get_free_slot_num() < num_chunks + 1 :
			print('namespace %d - %s nandcmd slot is not enough'%(ns.nsid, sb.name))
			return
			
		# get write cmd
		gc_cmd = ns.gc_cmd_queue.pop()
																																																																	
		# get new physical address from open block	
		way, block, page = sb.get_physical_addr()
		map_entry = build_map_entry(way, block, page, 0)
														
		# meta data update (meta datum are valid chunk bitmap, valid chunk count, map table
		# valid chunk bitamp and valid chunk count use in gc and trim 
		for index in range(num_chunks) :
			log_print('update meta data')

			buf_id = gc_cmd.buffer_ids.pop(0)
			gc_meta = gc_cmd.gc_meta.pop(0) 
			
			# get old physical address info
			ns_lba_index = gc_cmd.lba_index.pop(0)
			lba_index = int(namespace_mgr.lba2meta_addr(ns.nsid, ns_lba_index * SECTORS_PER_CHUNK) / SECTORS_PER_CHUNK)			
			
			old_physical_addr = meta.map_table[lba_index]

			# compare physical address for debugging : start 
			if old_physical_addr != gc_meta :
				print('gc_meta is not same with current meta - lbai : %d, meta : %s, gc_meta : %s'%(lba_index, str(parse_map_entry(old_physical_addr)), str(parse_map_entry(gc_meta))))
			# compare physical address for debugging : end
															
			# calculate way, block, page of old physical address
			old_way, old_nand_block, old_nand_page, old_chunk_offset = parse_map_entry(old_physical_addr)
			
			# validate "valid chunk bitmap", "valid chunk count", "map table" with new physical address
			meta.map_table[lba_index] = map_entry + index

			chunk_index = build_chunk_index(page, index)
			meta.set_valid_bitmap(way, block, chunk_index)			
			
			# invalidate "valid chunk bitmap", "valid chunk count" with old physical address		
			chunk_index = build_chunk_index(old_nand_page, old_chunk_offset)
			valid_sum = meta.clear_valid_bitmap(old_way, old_nand_block, chunk_index)
			if valid_sum == 0 :
				log_print('move sb : %d to erased block'%old_nand_block) 
				blk_manager = blk_grp.get_block_manager_by_zone(old_nand_block, sb.ways)
				blk_manager.release_block(old_nand_block)		

			buffer_ids.append(buf_id)														
																										
			# update count of gc command in order to check end of current gc command 			
			gc_cmd.count = gc_cmd.count - 1
			
			if gc_cmd.count == 0 :
				log_print('\ngc write - cmd id : %d'%(gc_cmd.cmd_id))

				# release cmd id
				ns.gc_cmd_id.release_slot(gc_cmd.cmd_id)
			
				if ns.gc_cmd_queue.length() > 0:			
					# get next command from queue
					gc_cmd = ns.gc_cmd_queue.pop()
		
		# push first write commmand for remaine sector count
		if gc_cmd.count > 0 :
			ns.gc_cmd_queue.push_first(gc_cmd)
			
		self.seq_num = self.seq_num + 1

		nand_addr = get_nand_addr(map_entry)
			
		# change cell mode command
		cmd_index = nandcmd_table.get_free_slot()
		cmd_desc = nandcmd_table.table[cmd_index]
		cmd_desc.op_code = FOP_SET_MODE
		cmd_desc.way = way
		cmd_desc.nand_addr = nand_addr
		cmd_desc.chunk_num = 0
		cmd_desc.option = sb.get_cell_mode()
		cmd_desc.seq_num = self.seq_num
		
		ftl2fil_queue.push(cmd_index)

		# program command		
		cmd_index = nandcmd_table.get_free_slot()
		cmd_desc = nandcmd_table.table[cmd_index]
		cmd_desc.op_code = FOP_GC_WRITE
		cmd_desc.way = way
		cmd_desc.nand_addr = nand_addr
		cmd_desc.chunk_num = num_chunks
		cmd_desc.buffer_ids = []
		for index in range(num_chunks) :
			# buffer_id is allocated during gc read operation	
			cmd_desc.buffer_ids.append(buffer_ids[index])
				
		cmd_desc.seq_num = self.seq_num
		
		ftl2fil_queue.push(cmd_index)
							
		# update super page index and check status of closing block (end of super block)
		is_close, block_addr, way_list = sb.update_page()

		# the block number should be moved to closed block list in block manager
		if is_close == True  :
			blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)
			blk_manager.set_close_block(block_addr)

		# update num_chunks_to_gc_write
		ns.num_chunks_to_gc_write = ns.num_chunks_to_gc_write - num_chunks			
																																																									
		log_print('do gc write - buf : %s'%(str(buffer_ids)))

	def do_gc_write_completion(self, sb) :
		log_print('do gc write completion')					

	@measure_time			
	def handler(self, log_time = None) :				
		# do host workload operation		
		# fetch command
		self.try_to_fetch_cmd()
				
		for index in range(namespace_mgr.get_num()) :															
			# do write
			ns = self.check_write_buffer_done()
			
			if ns != None :
				# check open logical block
				if ns.logical_blk.is_open() == False :
					# in the io determinism, each namespace context has the own block manager in order to seperate nand
					blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)	
				
					blk_no, way_list = blk_manager.get_free_block(erase_request = True)

					# meta is global variable, it is required for reseting during open, current setting is None
					ns.logical_blk.open(blk_no, way_list, None, blk_manager.cell_mode)
				
				# check ready to write of current namespace
				if ns.is_ready_to_write() == True:
					self.do_write(ns)
					break
							
		for index in range(namespace_mgr.get_num()) :
			ns = namespace_mgr.get(index)	
			# do read
			if ns.num_chunks_to_read > 0 :
				self.do_read(ns)
				
			# gc operation					
			blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)
			if blk_manager.get_exhausted_status() == True and ns.gc_src_blk.is_open() == False :
				block, way_list, ret_val = blk_manager.get_victim_block()
				if ret_val == True :
					self.select_victim_block(ns, block, way_list, blk_manager.cell_mode)
					
			# collect valid chunk from source super block
			if self.run_mode == True :		
				self.do_gc_read(ns)
				
		ns = self.do_gc_read_completion()
				
		# write valid chunk to destination super block
		if ns != None :
			if ns.gc_blk.is_open() == False :
				blk_manager = blk_grp.get_block_manager_by_name(ns.blk_name)	
				blk_no, way_list = blk_manager.get_free_block(erase_request = True)

				# meta is global variable, it is required for reseting during open, current setting is None
				ns.gc_blk.open(blk_no, way_list, None, blk_manager.cell_mode)
			  
			if self.gc_gather_write_data(ns) == True :
				self.do_gc_write(ns)
					
				#self.do_gc_write_completion()
																																		
		return
			
	def debug(self) :
		print('hil2ftl queue status')
		print('    high queue : %d/%d'%(hil2ftl_high_queue.length(), hil2ftl_high_queue.get_depth()))
		print('    low queue : %d/%d'%(hil2ftl_low_queue.length(), hil2ftl_low_queue.get_depth()))
		print('nandcmd')
		print('    num of free slots : %d'%(nandcmd_table.get_free_slot_num()))
		print('buffer')
		print('    num of read free slots : %d'%(bm.get_num_free_slots(BM_READ)))
		print('    num of write free slots : %d'%(bm.get_num_free_slots(BM_WRITE)))
			
class ftl_iod_statistics :
	def __init__(self) :
		print('iod statstics init')
																																	
	def print(self) :
		print('iod statstics')
												
if __name__ == '__main__' :
	print ('module ftl (flash translation layer for iod)')
	
	ftl = ftl_iod_manager(None)
			
																						