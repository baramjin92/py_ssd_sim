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

from sim_event import *

# ftl translates logical block address to physical address of nand

def log_print(message) :
	event_log_print('[ftl]', message)

PAGE_MASK = (0x01 << CHUNKS_PER_PAGE) - 1

def build_map_entry(way, block, page, chunk_offset) :
	address = way * CHUNKS_PER_WAY + block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE + chunk_offset

	return address

def parse_map_entry(address) :
	way = int(address / CHUNKS_PER_WAY) 
	block = int((address % CHUNKS_PER_WAY) / CHUNKS_PER_BLOCK) 
	page = int((address % CHUNKS_PER_BLOCK) / CHUNKS_PER_PAGE)
	chunk_offset = int((address % CHUNKS_PER_PAGE))
	
	return way, block, page, chunk_offset

# ftl should have meta datum for managing nand and mapping
# in this simulation, it has 3 meta datum.
#  1. map_table : (size of entry : 32bit)
#  2. valid_chunk_bitmap[way][block]
#  3. valid_chunk_count[way][block] : (size of entry : 32bit)
class ftl_meta :
	def __init__(self) :
		# meta data of ftl																				
		# so far, we use simple np, in order to support real capacity of ssd, we should change it by "memmap" of numpy		
		self.map_table = np.empty((NUM_LBA), np.uint32)
#		for index in range(NUM_LBA) :
#			self.map_table[index] = 0xFFFFFFFF

		# valid chunk bitmap
		self.size_of_bitmap = int(CHUNKS_PER_BLOCK / 32)

	def config(self, num_way) :
		# valid chunk bitmap
		self.valid_bitmap = np.empty((num_way, BLOCKS_PER_WAY, self.size_of_bitmap), np.uint32)

		# valid chunk count data  : valid_count[way][block]
		self.valid_count = np.empty((num_way, BLOCKS_PER_WAY), np.uint32)
		self.valid_sum = np.empty((BLOCKS_PER_WAY), np.uint32)

	def get_valid_sum(self, block) :			
		return self.valid_sum[block]

	def reset_valid_info(self, way, block) :
		self.valid_bitmap[way][block] = np.zeros(self.size_of_bitmap)
		self.valid_count[way][block] = 0
		self.valid_sum[block] = 0

	def set_valid_bitmap(self, way, block, chunk) :
		bmp = self.valid_bitmap[way][block]
		index = int(chunk / 32)
		mask = 0x01 << int(chunk % 32)
		bmp[index] = (bmp[index] | mask) & 0xFFFFFFFF		
		self.valid_bitmap[way][block] = bmp

		self.valid_count[way][block] = self.valid_count[way][block] + 1
		self.valid_sum[block] = self.valid_sum[block] + 1

	def clear_valid_bitmap(self, way, block, chunk) :
		bmp = self.valid_bitmap[way][block]
		index = int(chunk / 32)
		mask = ~(0x01 << int(chunk % 32))
		bmp[index] = (bmp[index] & mask) & 0xFFFFFFFF		
		self.valid_bitmap[way][block] = bmp

		self.valid_count[way][block] = self.valid_count[way][block] - 1
		self.valid_sum[block] = self.valid_sum[block] - 1
		
		# is this block empty or not? the super block should be moved to erased state
		if self.valid_sum[block] == 0 :
			return False
		else : 	
			return True
		
	def check_valid_bitmap(self, way, block, chunk) :
		bmp = self.valid_bitmap[way][block]
		index = int(chunk / 32)
		
		# result has all bitmap info of page
		result = (bmp[index] >> int(chunk % 32)) & PAGE_MASK		
		return result
																														
	def print_map_table(self, lba, num_sectors) :
		print('\nmap table - start lba : %d, end lba : %d'%(lba, lba+num_sectors-SECTORS_PER_CHUNK))
		chunk_index = int(lba / SECTORS_PER_CHUNK)
		length = int(num_sectors / SECTORS_PER_CHUNK)
		unit = 4
		str = '' 
		for index in range(length) :
			if index % unit == 0 :
				value = 'lba %08d : 0x%08x'%(chunk_index *SECTORS_PER_CHUNK, self.map_table[chunk_index])
			else :
				value = ' 0x%08x'%(self.map_table[chunk_index])
				
			str = str + value
			if index % unit == (unit-1) :
				print(str)
				str = ''	
				
			chunk_index = chunk_index + 1		
		
		print(str)
				
	def print_valid_data(self, way, block) :
		print('\nvalid info - way %d, block %d'%(way, block))
		print('valid count : %04d'%(self.valid_count[way][block]))
		str = ''
		for index in range(self.size_of_bitmap) :
			value = '0x%08x'%(self.valid_bitmap[way][block][index])
			str = str + ' ' + value
			
			if index % 8 == 7 :
				print(str)
				str = ''
				
		print(str)
		
class gc_cmd_desc :
	def __init__(self, cmd_tag) :
		self.cmd_id = cmd_tag
		self.lba_index = []
		self.buffer_ids = []
		self.count = 0

class gc_id_context :
	def __init__(self, gc_id_num, id_base = 0x2000, queue_id = 1000) :
		self.queue_id = queue_id
		self.cmd_id_base = id_base
														
		self.gc_id_free_slot = []
		for index in range(id_base, id_base+gc_id_num) :
			self.gc_id_free_slot.append(index)	
			
	def get_slot(self) :
		queue_id = self.queue_id
		cmd_id = self.gc_id_free_slot.pop(0)
		return queue_id, cmd_id		
		
	def release_slot(self, cmd_id) :
		self.gc_id_free_slot.append(cmd_id)	
										
	def get_num_free_slot(self) :
		return len(self.gc_id_free_slot)																							

# 'hil2ftl_high/low_queue' conveys ftl_cmd_desc
# hil created entry of ftl_cmd_desc and send it via 'hil2ftl_high/low_qeueu'
# ftl get entry of ftl_cmd_desc from these queues
# ftl has another queue like 'write_cmd_queue' in order to gather write command 
class ftl_cmd_desc :
	def __init__(self) :
		self.qid = 0					# qid can have queue id, zone id, stream id and so on. 
		self.cmd_tag = 0
		self.code = 0
		self.lba = 0
		self.sector_count = 0
 																												
class ftl_manager :
	def __init__(self, num_way, hic) :
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
				ret_val = meta.clear_valid_bitmap(old_way, old_nand_block, chunk_index)
				if ret_val == False :
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
			
		# update num_chunks_to_write
		self.num_chunks_to_write = self.num_chunks_to_write - num_chunks			

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
		is_close, block_addr = sb.update_page()
		
		# the block number should be moved to closed block list in block manager
		if is_close == True  :
			blk_manager = blk_grp.get_block_manager(block_addr)
			blk_manager.set_close_block(block_addr)
																														
		log_print('do write')

	def do_trim(self, lba, sector_count) :
		log_print('do trim - lba : %d, sector_count : %d'%(lba, sector_count))
		
		chunk_addr_start = lba / SECTORS_PER_CHUNK
		chunk_addr_end = (lba + sector_count - 1) / SECTORS_PER_CHUNK
		
		while chunk_addr_start <= chunk_addr_end :
			meta.map_table[chunk_addr_start] = 0xFFFFFFFF	
			chunk_addr_start = chunk_addr_start + 1
	
	def select_victim_block(self, block_addr, cell_mode) :
		if self.gc_src_sb.is_open() == False :
			way_list = []
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
						
					ftl2fil_queue.push(cmd_index)						
			
					self.num_chunks_to_gc_read = self.num_chunks_to_gc_read + num_chunks																																				
					num_chunks = 0	
																														
				log_print(str)
				issue_count = issue_count + 1
				
#				self.gc_issue_credit = self.gc_issue_credit - 1
#				if self.gc_issue_credit == 0 :
#					break
				
			is_close, block_addr = src_sb.update_page()						
								
	def do_gc_read_completion(self) :
		
		if fil2ftl_queue.length() > 0 :
			# fetch gc command and parse lba and sector count for chunk 
			cmd_tag, buffer_ids = fil2ftl_queue.pop()

			gc_cmd = gc_cmd_desc(cmd_tag)
			
			for buffer_id in buffer_ids :
				gc_cmd.buffer_ids.append(buffer_id)
				gc_cmd.lba_index.append(bm.get_meta_data(buffer_id))
			
			gc_cmd.count = len(buffer_ids)

			self.gc_cmd_queue.push(gc_cmd)
			
			self.num_chunks_to_gc_read = self.num_chunks_to_gc_read - gc_cmd.count
			self.num_chunks_to_gc_write = self.num_chunks_to_gc_write + gc_cmd.count 
									
			log_print('\ngc read result - cmd id : %d, num_read : %d, num_write : %d'%(cmd_tag, self.num_chunks_to_gc_read, self.num_chunks_to_gc_write))
			#print(buffer_ids)

			#self.gc_issue_credit = self.gc_issue_credit + 1

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
			# get old physical address info
			lba_index = gc_cmd.lba_index.pop(0)
			buffer_ids.append(gc_cmd.buffer_ids.pop(0))
			
			old_physical_addr = meta.map_table[lba_index]
			
			# calculate way, block, page of old physical address
			old_way, old_nand_block, old_nand_page, old_chunk_offset = parse_map_entry(old_physical_addr)
			
			# validate "valid chunk bitmap", "valid chunk count", "map table" with new physical address
			meta.map_table[lba_index] = map_entry + index

			chunk_index = page * CHUNKS_PER_PAGE + index
			meta.set_valid_bitmap(way, block, chunk_index)			
			
			# invalidate "valid chunk bitmap", "valid chunk count" with old physical address		
			chunk_index = old_nand_page * CHUNKS_PER_PAGE + old_chunk_offset
			ret_val = meta.clear_valid_bitmap(old_way, old_nand_block, chunk_index)
			if ret_val == False :
				log_print('move sb : %d to erased block'%old_nand_block) 
				blk_manager = blk_grp.get_block_manager(old_nand_block)
				blk_manager.release_block(old_nand_block)		
												
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
			
		# update num_chunks_to_gc_write
		self.num_chunks_to_gc_write = self.num_chunks_to_gc_write - num_chunks			

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
		is_close, block_addr = sb.update_page()

		# the block number should be moved to closed block list in block manager
		if is_close == True  :
			blk_manager = blk_grp.get_block_manager(block_addr)
			blk_manager.set_close_block(block_addr)
																																																				
		log_print('do gc write')
		log_print(buffer_ids)	

	def do_gc_write_completion(self, sb) :
		log_print('do gc write completion')
				
	def handler(self) :
		
		# super block allocation
		if self.host_sb.is_open() == False :
			blk_manager = blk_grp.get_block_manager_by_name('slc_cache')
			if blk_manager.get_free_block_num() > 0 and blk_manager.get_exhausted_status() == False :
				cell_mode = NAND_MODE_SLC
			else : 
				blk_manager = blk_grp.get_block_manager_by_name('user')
				cell_mode = NAND_MODE_MLC
				
			blk_no = blk_manager.get_free_block(erase_request = True)
			way_list = []
			self.host_sb.open(blk_no, way_list, meta, cell_mode)
		
		if self.gc_sb.is_open() == False :
			blk_manager = blk_grp.get_block_manager_by_name('user')
			blk_no = blk_manager.get_free_block(erase_request = True)
			way_list = []
			self.gc_sb.open(blk_no, way_list, meta)

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
		# select victim block
		if True :
			blk_manager = blk_grp.get_block_manager_by_name('slc_cache')
			if blk_manager.get_exhausted_status() == True  and self.gc_src_sb.is_open() == False :
				block, ret_val = blk_manager.get_victim_block()
				if ret_val == True :
					self.select_victim_block(block, NAND_MODE_SLC)
			
			blk_manager = blk_grp.get_block_manager_by_name('user')
			if blk_manager.get_exhausted_status() == True and self.gc_src_sb.is_open() == False :
				block, ret_val = blk_manager.get_victim_block()
				if ret_val == True :
					self.select_victim_block(block, NAND_MODE_MLC)
				
			# collect valid chunk from source super block
			if self.run_mode == True :		
				self.do_gc_read(self.gc_src_sb)
				
			self.do_gc_read_completion()
				
			# write valid chunk to destination super block 
			if self.num_chunks_to_gc_write >= CHUNKS_PER_PAGE :
				self.do_gc_write(self.gc_sb)
				#self.do_gc_write_completion()
		else :
			blk_manager = blk_grp.get_block_manager_by_name('user')
			if blk_manager.get_exhausted_status() == True :
				block, ret_val = blk_manager.get_victim_block()
				if ret_val == True :
					self.select_victim_block(block, NAND_MODE_MLC)
				
				# collect valid chunk from source super block
				if self.gc_src_sb.is_open() == True :		
					self.do_gc_read(self.gc_src_sb)
					self.do_gc_read_completion()
					
				# write valid chunk to destination super block 
				if self.num_chunks_to_gc_write >= CHUNKS_PER_PAGE :
					self.do_gc_write(self.gc_sb)
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
																																																													
class ftl_statistics :
	def __init__(self) :
		print('statstics init')
		
		self.num_gc_victims = 0
		self.sum_gc_cost = 0
		self.min_gc_cost = 0
		self.max_gc_cose = 0
																															
	def print(self) :
		print('statstics')

blk_grp = block_group()				
meta = ftl_meta()				
								
if __name__ == '__main__' :
	print ('module ftl (flash translation layer)')
	
	ftl = ftl_manager(NUM_WAYS, None)
	meta.config(NUM_WAYS)
	
	print('ssd capacity : %d GB'%SSD_CAPACITY)
#	print('ssd actual capacity : %d'%SSD_CAPACITY_ACTUAL)
	print('num of lba (512 byte sector) : %d'%NUM_LBA)
	print('num of logical chunk (4K unit) : %d'%(NUM_LBA/SECTORS_PER_CHUNK))	
	
	blk_grp.add('meta', block_manager(NUM_WAYS, 1, 9))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, 10, 19, 1, 2))
	blk_grp.add('user', block_manager(NUM_WAYS, 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))
	
	ftl.start()
	ftl.debug()
	
	print('.....test mapping table')
	start_lba = 40
	meta.print_map_table(start_lba, 128)
	
	lba_index = int(start_lba / SECTORS_PER_CHUNK)
	meta.map_table[lba_index] = 0x1234
	meta.map_table[lba_index+1] = 0x5678
	meta.map_table[lba_index+2] = 0xFFFF
	
	print('....check mapping table')
	meta.print_map_table(start_lba, 8*5)
	
	print('.....valid data')
	valid_bmp = meta.valid_bitmap[0][10]
	print(valid_bmp)
	print('.....')
	valid_bmp[0] = 0x08
	valid_bmp[1] = 0x04
	meta.valid_bitmap[0][10] = valid_bmp
	valid_bmp[2] = 0x02
	valid_bmp[3] = 0x01
	meta.valid_bitmap[0][10] = valid_bmp	
	print(meta.valid_bitmap[0][10])
	print('......')
	meta.valid_bitmap[0][20][0] = 0x7fffffff
	meta.set_valid_bitmap(0, 20, 30)
	meta.set_valid_bitmap(0, 20, 31)
	meta.print_valid_data(0, 20)
	
	print('......select victim block')
	ftl.select_victim_block(10, NAND_MODE_MLC)	
																			