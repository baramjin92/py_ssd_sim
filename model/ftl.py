#!/usr/bin/python

import os
import sys
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
from model.ftl_meta import *

from sim_event import *

# ftl translates logical block address to physical address of nand

def log_print(message) :
	event_log_print('[ftl]', message)
		 																												
class ftl_manager :
	def __init__(self, num_way, hic) :
		self.name = 'conventional'
		
		self.num_way = num_way
		
		# register hic now in order to use interface queue									
		self.hic_model = hic
		
		self.run_mode = True
		
		self.seq_num = 0
				
		# read cmd
		self.num_chunks_to_read = 0
		self.read_start_chunk = 0
		self.read_cur_chunk = 0
		self.read_queue_id = 0
		self.read_cmd_tag = 0
		
		# write_cmd_queue try to gather write commands before programing data to nand
		self.write_cmd_queue = queue(32)
		self.num_chunks_to_write = 0
		
		# gc context
		self.gc_cmd_id = gc_id_context(32)
		self.gc_cmd_queue = queue(32)
		self.gc_issue_credit = 8
		self.num_chunks_to_gc_read = 0
		self.num_chunks_to_gc_write = 0
																																										
		self.ftl_stat = ftl_statistics()
		
		self.debug_mode = 0											

	def start(self) :
		self.host_sb = super_block(self.num_way, 'host', SB_OP_WRITE)
		self.gc_sb = super_block(self.num_way, 'gc', SB_OP_WRITE)
		self.gc_src_sb = super_block(self.num_way, 'victim', SB_OP_READ)						

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
		
			# ftl_cmd.code should be HOST_CMD_READ				
			lba_start = ftl_cmd.lba
			lba_end = lba_start + ftl_cmd.sector_count - 1

			# in order to read from nand, read command information is updated			
			self.num_chunks_to_read = ftl_cmd.sector_count / SECTORS_PER_CHUNK
			self.read_start_chunk = lba_start / SECTORS_PER_CHUNK
			#self.read_end_chunk = lba_end / SECTORS_PER_CHUNK			
			self.read_queue_id = ftl_cmd.qid
			self.read_cmd_tag = ftl_cmd.cmd_tag
	
			self.read_cur_chunk = self.read_start_chunk 			

			log_print('host cmd read - qid : %d, cid : %d'%(ftl_cmd.qid, ftl_cmd.cmd_tag))
										
			# set fetch flag of hic (it will be move from hil to ftl, because hil code is temporary one)
			self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)				 	 	 	 	 	
				 	 	 	 	 			 	 	 	 	 			 	 	 	 	 	
		# check low priority queue
		if hil2ftl_low_queue.length() > 0 :
			# we will change sequeuce of poping command from low queue, because we need to check the remained command 
			ftl_cmd = hil2ftl_low_queue.pop()

			if ftl_cmd.code == HOST_CMD_WRITE :				
				# write cmd should be saved for gathering write chunks in order to meet physical size of nand
				self.write_cmd_queue.push(ftl_cmd)
				self.num_chunks_to_write = self.num_chunks_to_write + ftl_cmd.sector_count

				log_print('host cmd write')

				self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)
			else :
				# check num_chunks_to_write for checking the remained write operation.
				if self.num_chunks_to_write > 0 :
					log_print('write the remain commands in internal queue')

				if ftl_cmd.code == HOST_CMD_TRIM :
					log_print('host cmd trim')	
					
					# self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)
				elif ftl_cmd.code == HOST_CMD_CALM :			
					log_print('host cmd calm')
					
					# flush remain data in order to prepare calm state
																																				
		# save vcd file if option is activate

	def do_read(self) :
		# look up map entry and get physical address
		lba_index = int(self.read_cur_chunk)
		num_remain_chunks = self.num_chunks_to_read
		next_map_entry = 0xFFFFFFFF
		num_chunks_to_read = 0
		
		# check free slots of nandcmd_table (use num_remian_chunks, there is assumption all chunks are not adjecent)
		if nandcmd_table.get_free_slot_num() < num_remain_chunks :
			return		
		
		if ENABLE_RAMDISK_MODE == True :
			if bm.get_num_free_slots(BM_READ) < CHUNKS_PER_PAGE : 			
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
				log_print('map_entry : %x, next_map_entry : %x'%(int(map_entry/CHUNKS_PER_PAGE), int(next_map_entry/CHUNKS_PER_PAGE)))
				
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
			address = build_map_entry(0, block, page, 0)
			#address = int((map_entry % CHUNKS_PER_WAY) / CHUNKS_PER_PAGE) * CHUNKS_PER_PAGE
			start_chunk_offset = end_chunk_offset - (num_chunks_to_read - 1)

			# update lba_index for last chunk
			lba_index = lba_index + 1

			if address == 0 :
				print('do read - chunk : %d [offset : %d - num : %d], remain_num : %d, way : %d, address : %x, block : %d, page : %d'%(lba_index, start_chunk_offset, num_chunks_to_read, num_remain_chunks, way, address, block, page))
						
			# issue command to fil								
			if ENABLE_RAMDISK_MODE == False :
				# if we use buffer cache, we will check buffer id from cache instead of sending command to fil
				cache_hit = False
				if ENABLE_BUFFER_CACHE == True :
					cache_lba_index = self.read_cur_chunk
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
							self.hic_model.add_tx_buffer(self.read_queue_id, cache_info[1])
					
						next_event = event_mgr.alloc_new_event(0)
						next_event.code = event_id.EVENT_USER_DATA_READY
						next_event.dest = event_dst.MODEL_HIC					
					 
				if cache_hit == False :
					# cache miss, send cmd to fil
					cmd_index = nandcmd_table.get_free_slot()
					cmd_desc = nandcmd_table.table[cmd_index]
					cmd_desc.op_code = FOP_USER_READ
					cmd_desc.way = way
					cmd_desc.nand_addr = address
					cmd_desc.chunk_offset = start_chunk_offset
					cmd_desc.chunk_num = num_chunks_to_read
					cmd_desc.seq_num = self.seq_num
					cmd_desc.cmd_tag = self.read_cmd_tag
					cmd_desc.queue_id = self.read_queue_id
				
					ftl2fil_queue.push(cmd_index)
					
			else :
				# In the ramdisk mode, buffer is allocated at ftl, and send event to hic 
				buffer_ids, ret_val = bm.get_buffer(BM_READ, self.read_queue_id, self.read_cmd_tag, num_chunks_to_read)
		
				if ret_val == True :
					for buffer_id in buffer_ids :
						self.hic_model.add_tx_buffer(self.read_queue_id, buffer_id)
				
					next_event = event_mgr.alloc_new_event(0)
					next_event.code = event_id.EVENT_USER_DATA_READY
					next_event.dest = event_dst.MODEL_HIC					
				else :
					print('no buffer for read[%d] - lba index : %d, chunks : %d'%(int(self.read_cur_chunk), lba_index, num_chunks_to_read))
			
			# reset variable for checking next chunk																																								
			next_map_entry = 0xFFFFFFFF
			num_chunks_to_read = 0

			if ENABLE_RAMDISK_MODE == True :
				if bm.get_num_free_slots(BM_READ) < CHUNKS_PER_PAGE : 			
					break		

		# check remain chunk, if do_read can't finish because of lack of resource of buffer/controller
		self.read_cur_chunk = lba_index
		self.num_chunks_to_read = num_remain_chunks
													
	def do_write(self, sb) :
		# do_write try to program data to nand
		
		# check preparation of target block of nand
		if sb.is_open() == False :
			log_print('%s superblock is not open'%(sb.name))
			return
		
		num_chunks = sb.get_num_chunks_to_write(self.num_chunks_to_write)
		 
		# check for arrival of data (check inequality between number of write and sum of write sector counts)
		if len(self.hic_model.rx_buffer_done) < num_chunks :
			#log_print('data transfer is not finished')
			return 
						
		# check free slots of nandcmd_table
		# in order to send cell mode command, we need one more nandcmd slot
		if nandcmd_table.get_free_slot_num() < (num_chunks + 1) :
			return
			
		# get write cmd
		ftl_cmd = self.write_cmd_queue.pop()
			
		# get new physical address from open block	
		way, block, page = sb.get_physical_addr()
		map_entry = build_map_entry(way, block, page, 0)
														
		# meta data update (meta datum are valid chunk bitmap, valid chunk count, map table
		# valid chunk bitamp and valid chunk count use in gc and trim 
		for index in range(num_chunks) :
			log_print('update meta data')
			# get old physical address info
			lba_index = int(ftl_cmd.lba / SECTORS_PER_CHUNK)
			old_physical_addr = meta.map_table[lba_index]
			
			# if we use buffer cache, we should check and evict buffer id from cache, in order to avoid mismatch of data
			if ENABLE_BUFFER_CACHE == True :		 
				bm_cache.evict(lba_index)
																																																					
			# validate "valid chunk bitmap", "valid chunk count", "map table" with new physical address
			meta.map_table[lba_index] = map_entry + index

			# CHUNKS_PER_PAGE is calculated in the MLC mode, we need to consider another cell mode
			chunk_index = page * CHUNKS_PER_PAGE + index
			meta.set_valid_bitmap(way, block, chunk_index)					
									
			# invalidate "valid chunk bitmap", "valid chunk count" with old physical address
			# if mapping address is 0, it is unmapped address 
			if old_physical_addr != 0 :
				# calculate way, block, page of old physical address
				old_way, old_nand_block, old_nand_page, old_chunk_offset = parse_map_entry(old_physical_addr)
						
				chunk_index = old_nand_page * CHUNKS_PER_PAGE + old_chunk_offset
				valid_sum = meta.clear_valid_bitmap(old_way, old_nand_block, chunk_index)
				if valid_sum == 0 :
					log_print('move sb to erased block')
					blk_manager = blk_grp.get_block_manager(old_nand_block) 
					blk_manager.release_block(old_nand_block)		
													
			# update lba and sector count of write command in order to check end of current write command 
			# chunk_index = chunk_index + 1
			
			ftl_cmd.sector_count = ftl_cmd.sector_count - SECTORS_PER_CHUNK
			ftl_cmd.lba = ftl_cmd.lba + SECTORS_PER_CHUNK
			
			if ftl_cmd.sector_count == 0 and self.write_cmd_queue.length() > 0:
				# get next command from queue
				ftl_cmd = self.write_cmd_queue.pop()
		
		# push first write commmand for remaine sector count
		if ftl_cmd.sector_count > 0 :
			self.write_cmd_queue.push_first(ftl_cmd)
			
		self.seq_num = self.seq_num + 1

		if ENABLE_RAMDISK_MODE == False :
			address = int(map_entry % CHUNKS_PER_WAY)
	
			# change cell mode command
			cmd_index = nandcmd_table.get_free_slot()
			cmd_desc = nandcmd_table.table[cmd_index]
			cmd_desc.op_code = FOP_SET_MODE
			cmd_desc.way = way
			cmd_desc.nand_addr = address
			cmd_desc.chunk_num = 0
			cmd_desc.option = sb.get_cell_mode()
			cmd_desc.seq_num = self.seq_num
		
			ftl2fil_queue.push(cmd_index)

			# program command		
			cmd_index = nandcmd_table.get_free_slot()
			cmd_desc = nandcmd_table.table[cmd_index]
			cmd_desc.op_code = FOP_USER_WRITE
			cmd_desc.way = way
			cmd_desc.nand_addr = address
			cmd_desc.chunk_num = num_chunks
			cmd_desc.buffer_ids = []
			for index in range(num_chunks) :
				# buffer_id is allocated by hil, and data is saved by hic
				buffer_id = self.hic_model.rx_buffer_done.pop(0)	
				cmd_desc.buffer_ids.append(buffer_id)				
			cmd_desc.seq_num = self.seq_num
		
			ftl2fil_queue.push(cmd_index)
		else :
			for index in range(num_chunks) :
				# buffer_id is allocated by hil, and data is saved by hic
				buffer_id = self.hic_model.rx_buffer_done.pop(0)	
				bm.release_buffer(buffer_id)
							
		# update super page index and check status of closing block (end of super block)
		is_close, block_addr, way_list = sb.update_page()
		
		# the block number should be moved to closed block list in block manager
		if is_close == True  :
			blk_manager = blk_grp.get_block_manager(block_addr)
			blk_manager.set_close_block(block_addr)

		# update num_chunks_to_write
		self.num_chunks_to_write = self.num_chunks_to_write - num_chunks			
																																																											
		log_print('do write')

	def do_trim(self, lba, sector_count) :
		log_print('do trim - lba : %d, sector_count : %d'%(lba, sector_count))
		
		chunk_addr_start = lba / SECTORS_PER_CHUNK
		chunk_addr_end = (lba + sector_count - 1) / SECTORS_PER_CHUNK
		
		while chunk_addr_start <= chunk_addr_end :
			meta.map_table[chunk_addr_start] = 0xFFFFFFFF	
			chunk_addr_start = chunk_addr_start + 1
	
	def select_victim_block(self, block_addr, way_list, cell_mode) :
		if self.gc_src_sb.is_open() == False :
			self.gc_src_sb.open(block_addr, way_list, meta, cell_mode)
			log_print('select victim block : %d'%(block_addr))
			return True
			
		return False	

	def do_gc_read(self, src_sb) :
#		if self.gc_issue_credit <= 0 :
#			return
		if src_sb.is_open() == False :		
			return
				
		if self.gc_cmd_id.get_num_free_slot() < 8 :
			return 

		log_print('do gc read')

		issue_count = 0
		while issue_count < 4 and src_sb.is_open() == True :
									
			# get new physical address from open block	
			way, block, page = src_sb.get_physical_addr()
			chunk = page * CHUNKS_PER_PAGE
			
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
						address = build_map_entry(0, block, page, 0)

						queue_id, cmd_tag = self.gc_cmd_id.get_slot()

						cmd_index = nandcmd_table.get_free_slot()
						cmd_desc = nandcmd_table.table[cmd_index]
						cmd_desc.op_code = FOP_GC_READ
						cmd_desc.way = way
						cmd_desc.nand_addr = address
						cmd_desc.chunk_offset = start_chunk_offset
						cmd_desc.chunk_num = num_chunks
						cmd_desc.seq_num = self.seq_num
						cmd_desc.cmd_tag = cmd_tag
						cmd_desc.queue_id = queue_id

						cmd_desc.gc_meta = []
						gc_meta = build_map_entry2(way, address, start_chunk_offset)
						for offset in range(num_chunks) :
							cmd_desc.gc_meta.append(gc_meta + offset) 
																																												
						ftl2fil_queue.push(cmd_index)						
						
						self.num_chunks_to_gc_read = self.num_chunks_to_gc_read + num_chunks																																			
						num_chunks = 0	
					
					chunk_offset = chunk_offset + 1		

				if num_chunks > 0 :
					# send command to nand, all chunks is full 
					start_chunk_offset = chunk_offset - (num_chunks - 1)
					str = str + '[%d:%d] '%(start_chunk_offset, num_chunks)
					
					# send nand cmd to fil						
					self.seq_num = self.seq_num + 1
					address = build_map_entry(0, block, page, 0)

					queue_id, cmd_tag = self.gc_cmd_id.get_slot()

					cmd_index = nandcmd_table.get_free_slot()
					cmd_desc = nandcmd_table.table[cmd_index]
					cmd_desc.op_code = FOP_GC_READ
					cmd_desc.way = way
					cmd_desc.nand_addr = address
					cmd_desc.chunk_offset = start_chunk_offset
					cmd_desc.chunk_num = num_chunks
					cmd_desc.seq_num = self.seq_num
					cmd_desc.cmd_tag = cmd_tag
					cmd_desc.queue_id = queue_id
					
					cmd_desc.gc_meta = []
					gc_meta = build_map_entry2(way, address, start_chunk_offset)
					for offset in range(num_chunks) :
						cmd_desc.gc_meta.append(gc_meta + offset) 
						
					ftl2fil_queue.push(cmd_index)						
			
					self.num_chunks_to_gc_read = self.num_chunks_to_gc_read + num_chunks																																				
					num_chunks = 0	
																														
				log_print(str)
				issue_count = issue_count + 1
				
#				self.gc_issue_credit = self.gc_issue_credit - 1
#				if self.gc_issue_credit == 0 :
#					break
				
			is_close, block_addr, way_list = src_sb.update_page()						
								
	def do_gc_read_completion(self) :
		
		if fil2ftl_queue.length() > 0 :
			# fetch gc command and parse lba and sector count for chunk 
			queue_id, cmd_tag, buffer_ids, gc_meta = fil2ftl_queue.pop()

			# if we don't use namespace, nsid is not require'
			gc_cmd = gc_cmd_desc(0, cmd_tag)
			
			for buffer_id in buffer_ids :			
				# get old physical address info
				lba_index = bm.get_meta_data(buffer_id)
				gc_physical_addr = gc_meta.pop(0)
				
				gc_cmd.buffer_ids.append(buffer_id)
				gc_cmd.lba_index.append(lba_index)
				gc_cmd.gc_meta.append(gc_physical_addr)
							
			gc_cmd.count = len(gc_cmd.buffer_ids)
			
			if gc_cmd.count > 0:
				self.gc_cmd_queue.push(gc_cmd)
				
				self.num_chunks_to_gc_read = self.num_chunks_to_gc_read - gc_cmd.count
				self.num_chunks_to_gc_write = self.num_chunks_to_gc_write + gc_cmd.count 
										
			log_print('\ngc read result - cmd id : %d, num_read : %d, num_write : %d'%(cmd_tag, self.num_chunks_to_gc_read, self.num_chunks_to_gc_write))

			#self.gc_issue_credit = self.gc_issue_credit + 1

	def gc_gather_write_data(self) :				
		ret_val = False
		
		if self.num_chunks_to_gc_write < CHUNKS_PER_PAGE :
			return False		
		
		num_chunks = self.num_chunks_to_gc_write
		
		queue_id, cmd_tag = self.gc_cmd_id.get_slot() 											 											
		gc_cmd_comp = gc_cmd_desc(queue_id, cmd_tag)
												
		# get write cmd
		gc_cmd = self.gc_cmd_queue.pop()
													
		for index in range(num_chunks) :
			buf_id = gc_cmd.buffer_ids.pop(0)
			gc_meta = gc_cmd.gc_meta.pop(0) 
			lba_index = gc_cmd.lba_index.pop(0)
			
			# get old physical address info
			old_physical_addr = meta.map_table[lba_index]

			# compare physical address
			if old_physical_addr != gc_meta :
				print('gc compaction - lbai : %d, meta : %s, gc_meta : %s'%(lba_index, str(parse_map_entry(old_physical_addr)), str(parse_map_entry(gc_meta))))
				
				bm.release_buffer(buf_id)
				
				self.num_chunks_to_gc_write = self.num_chunks_to_gc_write - 1			
			else :																
				# move to compaction cmd set		
				gc_cmd_comp.buffer_ids.append(buf_id)
				gc_cmd_comp.gc_meta.append(gc_meta)
				gc_cmd_comp.lba_index.append(lba_index)
				gc_cmd_comp.count = gc_cmd_comp.count + 1														
																										
			# update count of gc command in order to check end of current gc command 			
			gc_cmd.count = gc_cmd.count - 1

			if gc_cmd.count == 0 :
				# release cmd id
				self.gc_cmd_id.release_slot(gc_cmd.cmd_id)
			
				if self.gc_cmd_queue.length() > 0:			
					# get next command from queue
					gc_cmd = self.gc_cmd_queue.pop()

			if gc_cmd_comp.count > CHUNKS_PER_PAGE :
				ret_val = True
				break						
						
		# push write commmand for remain sector count
		if gc_cmd.count > 0 :
			self.gc_cmd_queue.push_first(gc_cmd)
			
		self.gc_cmd_queue.push_first(gc_cmd_comp)	
		
		return ret_val

	def do_gc_write(self, sb) :
		# do_write try to program data to nand
		buffer_ids = []
		
		# check preparation of target block of nand
		if sb.is_open() == False :
			print('%s superblock is not open'%(sb.name))
			return
		
		num_chunks = sb.get_num_chunks_to_write(self.num_chunks_to_gc_write)
		 						
		# check free slots of nandcmd_table
		# in order to send cell mode command, we need one more nandcmd slot		
		if nandcmd_table.get_free_slot_num() < num_chunks + 1 :
			print('%s nandcmd slot is not enough'%(sb.name))
			return
			
		# get write cmd
		gc_cmd = self.gc_cmd_queue.pop()
			
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
			lba_index = gc_cmd.lba_index.pop(0)
			
			old_physical_addr = meta.map_table[lba_index]

			# compare physical address
			if old_physical_addr != gc_meta :
				print('gc_meta is not same with current meta - lbai : %d, meta : %s, gc_meta : %s'%(lba_index, str(parse_map_entry(old_physical_addr)), str(parse_map_entry(gc_meta))))
																								
			# calculate way, block, page of old physical address
			old_way, old_nand_block, old_nand_page, old_chunk_offset = parse_map_entry(old_physical_addr)
			
			# validate "valid chunk bitmap", "valid chunk count", "map table" with new physical address
			meta.map_table[lba_index] = map_entry + index

			chunk_index = page * CHUNKS_PER_PAGE + index
			meta.set_valid_bitmap(way, block, chunk_index)			
			
			# invalidate "valid chunk bitmap", "valid chunk count" with old physical address		
			chunk_index = old_nand_page * CHUNKS_PER_PAGE + old_chunk_offset
			valid_sum = meta.clear_valid_bitmap(old_way, old_nand_block, chunk_index)
			if valid_sum == 0 :
				log_print('move sb : %d to erased block'%old_nand_block) 
				blk_manager = blk_grp.get_block_manager(old_nand_block)
				blk_manager.release_block(old_nand_block)		

			buffer_ids.append(buf_id)														
																																																
			# update count of gc command in order to check end of current gc command 			
			gc_cmd.count = gc_cmd.count - 1
			
			if gc_cmd.count == 0 :
				log_print('\ngc write - cmd id : %d'%(gc_cmd.cmd_id))

				# release cmd id
				self.gc_cmd_id.release_slot(gc_cmd.cmd_id)
			
				if self.gc_cmd_queue.length() > 0:			
					# get next command from queue
					gc_cmd = self.gc_cmd_queue.pop()
		
		# push first write commmand for remaine sector count
		if gc_cmd.count > 0 :
			self.gc_cmd_queue.push_first(gc_cmd)
			
		self.seq_num = self.seq_num + 1

		address = int(map_entry % CHUNKS_PER_WAY)
	
		# change cell mode command
		cmd_index = nandcmd_table.get_free_slot()
		cmd_desc = nandcmd_table.table[cmd_index]
		cmd_desc.op_code = FOP_SET_MODE
		cmd_desc.way = way
		cmd_desc.nand_addr = address
		cmd_desc.chunk_num = 0
		cmd_desc.option = sb.get_cell_mode()
		cmd_desc.seq_num = self.seq_num
		
		ftl2fil_queue.push(cmd_index)

		# program command		
		cmd_index = nandcmd_table.get_free_slot()
		cmd_desc = nandcmd_table.table[cmd_index]
		cmd_desc.op_code = FOP_GC_WRITE
		cmd_desc.way = way
		cmd_desc.nand_addr = address
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
			blk_manager = blk_grp.get_block_manager(block_addr)
			blk_manager.set_close_block(block_addr)

		# update num_chunks_to_gc_write
		self.num_chunks_to_gc_write = self.num_chunks_to_gc_write - num_chunks			
																																																									
		log_print('do gc write')
		log_print(buffer_ids)	

	def do_gc_write_completion(self, sb) :
		log_print('do gc write completion')
				
	def handler(self) :
		
		# super block allocation
		if self.host_sb.is_open() == False :
			blk_manager = blk_grp.get_block_manager_by_name('slc_cache')
			if blk_manager.get_free_block_num() == 0 or blk_manager.get_exhausted_status() == True :
				blk_manager = blk_grp.get_block_manager_by_name('user')
				
			blk_no, way_list = blk_manager.get_free_block(erase_request = True)
			self.host_sb.open(blk_no, way_list, meta, blk_manager.cell_mode)
		
		if self.gc_sb.is_open() == False :
			blk_manager = blk_grp.get_block_manager_by_name('user')
			blk_no, way_list = blk_manager.get_free_block(erase_request = True)
			self.gc_sb.open(blk_no, way_list, meta, blk_manager.cell_mode)

		# do host workload operation		
		# fetch command
		self.try_to_fetch_cmd()
						
		# do write
		if self.num_chunks_to_write >= CHUNKS_PER_PAGE :
			self.do_write(self.host_sb)

		# do read
		if self.num_chunks_to_read > 0 :
			self.do_read()
								
		# do garbage collection
		# select victim block between slc_cache and user area
		blk_manager = blk_grp.get_block_manager_by_name('slc_cache')
		if blk_manager.get_exhausted_status() == True  and self.gc_src_sb.is_open() == False :
			block, way_list, ret_val = blk_manager.get_victim_block()
			if ret_val == True :
				self.select_victim_block(block, way_list, blk_manager.cell_mode)
			
		blk_manager = blk_grp.get_block_manager_by_name('user')
		if blk_manager.get_exhausted_status() == True and self.gc_src_sb.is_open() == False :
			block, way_list, ret_val = blk_manager.get_victim_block()
			if ret_val == True :
				self.select_victim_block(block, way_list, blk_manager.cell_mode)
				
		# collect valid chunk from source super block
		if self.run_mode == True :		
			self.do_gc_read(self.gc_src_sb)
				
		self.do_gc_read_completion()
				
		# write valid chunk to destination super block 
		if self.gc_gather_write_data() > True :
			self.do_gc_write(self.gc_sb)
			
		#self.do_gc_write_completion()
			
	def debug(self) :
		print('hil2ftl queue status')
		print('    high queue : %d/%d'%(hil2ftl_high_queue.length(), hil2ftl_high_queue.get_depth()))
		print('    low queue : %d/%d'%(hil2ftl_low_queue.length(), hil2ftl_low_queue.get_depth()))
		print('nandcmd')
		print('    num of free slots : %d'%(nandcmd_table.get_free_slot_num()))
		print('buffer')
		print('    num of read free slots : %d'%(bm.get_num_free_slots(BM_READ)))																																	
		print('    num of write free slots : %d'%(bm.get_num_free_slots(BM_WRITE)))
																																																													
class ftl_statistics :
	def __init__(self) :
		print('statstics init')
		
		self.num_gc_victims = 0
		self.sum_gc_cost = 0
		self.min_gc_cost = 0
		self.max_gc_cose = 0
																															
	def print(self) :
		print('statstics')
												
if __name__ == '__main__' :
	print ('module ftl (flash translation layer)')
	
	ftl = ftl_manager(NUM_WAYS, None)
	meta.config(NUM_WAYS)
	
	print('ssd capacity : %d GB'%SSD_CAPACITY)
#	print('ssd actual capacity : %d'%SSD_CAPACITY_ACTUAL)
	print('num of lba (512 byte sector) : %d'%NUM_LBA)
	print('num of logical chunk (4K unit) : %d'%(NUM_LBA/SECTORS_PER_CHUNK))	
	
	blk_grp.add('meta', block_manager(NUM_WAYS, None, 1, 9))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 19, 1, 2))
	blk_grp.add('user', block_manager(NUM_WAYS, None, 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))
	
	ftl.start()
	ftl.debug()
		
	print('......select victim block')
	way_list = []
	ftl.select_victim_block(10, way_list, NAND_MODE_MLC)	
																			