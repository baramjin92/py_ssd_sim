 #!/usr/bin/python

import os
import sys
import time

import random

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
	event_log_print('[zns]', message)

def measure_time(func) :
	def measure_time(*args, **kwargs) :
		start_time = time.time()
		result = func(*args, **kwargs)
		kwargs['log_time']['ftl'] = kwargs['log_time']['ftl'] + (time.time() - start_time)
		return result
	
	return measure_time

ZONE_STATE_EMPTY = 0
ZONE_STATE_EOPEN = 1
ZONE_STATE_IOPEN = 2
ZONE_STATE_CLOSE = 3
ZONE_STATE_FULL = 4
ZONE_STATE_READONLY = 5
ZONE_STATE_OFFLINE = 6

class zone_desc :
	def __init__(self, zone_no, slba = 0) :
		self.state = ZONE_STATE_EMPTY
		self.no = zone_no
		self.slba = slba
		self.logical_blk = None
		
		self.write_pointer = 0
		self.max_num_chunks = ZONE_SIZE / BYTES_PER_CHUNK
							
		# write_cmd_queue try to gather write commands before programing data to nand
		self.write_cmd_queue = queue(32)
		self.num_chunks_to_write = 0
		
		self.write_buffer = []
		
		# flush
		self.flush_req = False
		
		# close
		self.close_req = False
			
	def is_idle(self) :
		if self.num_chunks_to_write == 0 :
			return True
		else :
			self.debug()
			return False
				
	def is_ready_to_write(self, cell_mode) :
		program_unit = get_num_chunks_for_write(cell_mode)
		if self.num_chunks_to_write >= program_unit and len(self.write_buffer) >= program_unit :
			if self.write_cmd_queue.length() == 0 :
				print('error zone : %d, num_chunks_to_write : %d, length write buffer : %d'%(self.no, self.num_chunks_to_write, len(self.write_buffer)))

			return True
		else :
			return False							
						
	def get_num_chunks_to_write(self) :					
		num_chunks, num_dummy = self.logical_blk.get_num_chunks_to_write(self.num_chunks_to_write)																				
		return num_chunks, num_dummy																								
																																																																						
	def update_write_info(self, num_chunks) :
		self.num_chunks_to_write = self.num_chunks_to_write - num_chunks			

		self.write_pointer = self.write_pointer + num_chunks
		if self.write_pointer >= self.max_num_chunks :
			self.state = ZONE_STATE_FULL
		
			print('update_write_info : close by full')
			# close zone block
					
		return self.state

	def flush_request(self, close_req) :		
		if self.flush_req == False and self.num_chunks_to_write > 0 :			
			print('\nzone %d flush request remained chunks : %d'%(self.no, self.num_chunks_to_write))			
			self.flush_req = True
			
		self.close_req = close_req	

	def is_flush(self) :
		if self.flush_req == True and self.num_chunks_to_write > 0 :			
			return True
		else :
			return False	

	def check_flush_done(self) :			
		if self.flush_req == True  and self.num_chunks_to_write == 0 :
			self.flush_req = False
			print('flush done')		
			
		if self.close_req == True :
			print('zone %d close after flush done'%self.no)							
		
	def debug(self) :
		print('zone : %d'%self.no)
		print('state : %d'%self.state)
		print('write_pointer : %d'%self.write_pointer)
		print('num_chunks_to_write : %d'%self.num_chunks_to_write)
		print('length write buffer : %d'%len(self.write_buffer))
			
class zone_manager :
	def __init__(self, num_zone, num_way, max_open_zone) :
		self.num_zone = num_zone
		self.num_way = num_way
		self.num_open_zone = 0
		self.max_open_zone = max_open_zone
		self.table = []
		
		self.empty_list = []
		self.close_list = []
		self.open_list = []
		
		self.open_index = -1
		
		for index in range(num_zone) :
			self.table.append(zone_desc(index, 0))
			self.empty_list.append(index)

	def set_num_way(self, num_way) :
		self.num_way = num_way

	def get_open_zone_num(self) :
		return self.num_open_zone

	def get_open_zone(self, lba) :
		zone_no = int((lba * BYTES_PER_SECTOR) / ZONE_SIZE)
		
		if zone_no in self.open_list :
			zone =  self.table[zone_no]
		else :
			zone = None
									
		return zone
																														
	def get(self, lba) :
		zone_no = int((lba * BYTES_PER_SECTOR) / ZONE_SIZE)
		
		if zone_no in self.open_list :
			zone =  self.table[zone_no]
			#log_print('\nget zone %d - state %d'%(zone.no, zone.state))
		else :
			# implict open zone
			print('\nget zone %d by implict open'%(zone_no))			
			zone = self.open(lba, ZONE_STATE_IOPEN)
													
		return zone
	
	def open(self, lba, state = ZONE_STATE_EOPEN) :
		zone_no = int((lba * BYTES_PER_SECTOR) / ZONE_SIZE)

		print('open zone : %d, lba : %d, state :%d'%(zone_no, lba, state))

		# explict open zone
		if self.num_open_zone < self.max_open_zone :
			if zone_no in self.empty_list :
				self.empty_list.remove(zone_no)
				self.open_list.append(zone_no)
				self.num_open_zone = self.num_open_zone + 1
					
				zone = self.table[zone_no]
				zone.state = state
				zone.slba = lba
				zone.write_pointer = 0
				
				# alloc zone block
				# so far we assume that size of zone is same with size of super block
				# however it will be changed later 
				zone_name = 'zone_%d'%(zone_no)
				zone.logical_blk = super_block(self.num_way, zone_name, SB_OP_WRITE)
				
				blk_manager = blk_grp.select_block_manager_for_free_block(FREE_BLK_LEVELING)	
				
				blk_no, way_list = blk_manager.get_free_block(erase_request = True)

				# meta is global variable, it is required for reseting during open, current setting is None
				zone.logical_blk.open(blk_no, way_list, None, blk_manager.cell_mode, blk_manager.nand_info)
													
				return zone
			else :
				print('error : zone %d is not in empty'%(zone_no))
		else :
			print('error : max open zone - %d, %d'%(self.num_open_zone, self.max_open_zone))
			
		return None
		
	def close(self, lba) :			
		zone_no = int((lba * BYTES_PER_SECTOR) / ZONE_SIZE)
	
		if zone_no in self.open_list :
			zone = self.table[zone_no]
			
			if zone.state == ZONE_STATE_EOPEN or zone.state == ZONE_STATE_IOPEN or zone.state == ZONE_STATE_FULL :
				zone.state = ZONE_STATE_CLOSE 

				self.open_list.remove(zone_no)
				self.num_open_zone = self.num_open_zone - 1
				self.close_list.append(zone_no)
				
				log_print('close zone %d'%zone_no)
	
	def empty(self, zone_no) :
		if zone_no in self.close_list :
			zone = self.table[zone_no]

			if zone.state == ZONE_STATE_CLOSE :
				zone.state = ZONE_STATE_EMPTY
				zone.write_pointer = 0

				self.close_list.remove(zone_no)
				self.empty_list.append(zone_no)
				
				log_print('empty zone %d'%zone_no)
		else :
			log_print('error : zone %d is not closed'%zone_no)

	def debug(self) :																																																		
		print('\nnum of open zone : %d'%(self.num_open_zone))
		print('list of open zone')
		for zone_no in self.open_list :
			zone = self.table[zone_no]
			percent = int(zone.write_pointer / zone.max_num_chunks * 100)
			print('zone %d, state : %d, count : %d'%(zone_no, zone.state, percent))
		print('end')
		
		print('list of close zone')
		for zone_no in self.close_list :
			zone = self.table[zone_no]
			print('zone %d, state : %d'%(zone_no, zone.state))
		print('end')		
																
class ftl_zns_manager :
	def __init__(self, num_way, hic) :
		self.name = 'zns'
		
		self.num_way = num_way
		zone_mgr.set_num_way(num_way)
		
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

		### write_cmd_queue is moved to zone_descriptor		
																																														
		self.ftl_stat = ftl_zns_statistics()
		
	def start(self) :
		print('start zns ftl')

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
				zone = zone_mgr.get(ftl_cmd.lba)
				if zone == None :
					#hil2ftl_low_queue.push_first(ftl_cmd)
					print('error : can not get zone')
				else :					
					zone.write_cmd_queue.push(ftl_cmd)
					zone.num_chunks_to_write = zone.num_chunks_to_write + int(ftl_cmd.sector_count / SECTORS_PER_CHUNK)

					self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)
					
				log_print('host cmd write')
			else :
				if ftl_cmd.code == HOST_CMD_TRIM :
					log_print('host cmd trim')	
					
					# self.hic_model.set_cmd_fetch_flag(ftl_cmd.qid, ftl_cmd.cmd_tag)
				elif ftl_cmd.code == HOST_CMD_CALM :			
					log_print('host cmd calm')
	
					# flush remain data in order to prepare calm state
				elif ftl_cmd.code == HOST_CMD_ZONE_SEND :
					log_print('zone management send command - slba : %d, zsa : %d'%(ftl_cmd.lba, ftl_cmd.sector_count))
					
					if ftl_cmd.sector_count == HOST_ZSA_CLOSE :
						zone = zone_mgr.get_open_zone(ftl_cmd.lba)
						if zone != None :
							zone.flush_request(True)
							if zone.is_flush() == True :
								self.do_write(zone)	
								
							if zone.state == ZONE_STATE_FULL :							
								print('close zone in FTL')
								zone.debug()						
								zone_mgr.close(ftl_cmd.lba)
							else :
								print('error : can not close zone in FTL')
								input()
						else :
							print('error : zone is not opend')
								
					elif ftl_cmd.sector_count == HOST_ZSA_OPEN :
						zone = zone_mgr.open(ftl_cmd.lba)
						if zone == None :
							log_print('error : can not open new zone')
					elif ftl_cmd.sector_count == HOST_ZSA_RESET :
						log_print('reset')
							
					self.hic_model.set_manual_completion(ftl_cmd.qid, ftl_cmd.cmd_tag)
																																				
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
				
				if next_map_entry == map_entry + 1 :
					if check_same_physical_page(next_map_entry, map_entry) == True :
						# go to check next adjacent
						lba_index = lba_index + 1
						continue		
												
			# try to read with map_entry from nand, because next_map_entry is not adjacent
			self.seq_num = self.seq_num + 1
			
			if map_entry != UNMAP_ENTRY :
				way, block, page, end_chunk_offset = parse_map_entry(map_entry)
				# in order to calculate nand address, way and 
				nand_addr = build_map_entry(0, block, page, 0)
				start_chunk_offset = end_chunk_offset - (num_chunks_to_read - 1)
	
				# update lba_index for last chunk
				lba_index = lba_index + 1
	
				if nand_addr == 0 :
					print('do read - lba : %d [offset : %d - num : %d], remain_num : %d, way : %d, nand_addr : %x, block : %d, page : %d'%(lba_index*SECTORS_PER_CHUNK, start_chunk_offset, num_chunks_to_read, num_remain_chunks, way, nand_addr, block, page))
			else :
				print('unmap read - lba : %d, entry : %x'%(lba_index*SECTORS_PER_CHUNK, map_entry))
							
			# issue command to fil								
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
				cmd_desc.nand_addr = nand_addr
				cmd_desc.chunk_offset = start_chunk_offset
				cmd_desc.chunk_num = num_chunks_to_read
				cmd_desc.seq_num = self.seq_num
				cmd_desc.cmd_tag = self.read_cmd_tag
				cmd_desc.queue_id = self.read_queue_id
				
				ftl2fil_queue.push(cmd_index)
								
			# reset variable for checking next chunk																																								
			next_map_entry = 0xFFFFFFFF
			num_chunks_to_read = 0

		# check remain chunk, if do_read can't finish because of lack of resource of buffer/controller
		self.read_cur_chunk = lba_index
		self.num_chunks_to_read = num_remain_chunks

	def check_write_buffer_done(self) :												
		# check for arrival of data and move buffer pointer to buffer list of zone
		zone = None
		
		for index in range(len(self.hic_model.rx_buffer_done))  :
			buffer_id = self.hic_model.rx_buffer_done.pop(0)
			lca = bm.get_meta_data(buffer_id)
			lba = lca * SECTORS_PER_CHUNK
						
			zone = zone_mgr.get(lba)
			if zone == None :
				print ('error check write buffer done - lba : %d'%lba)
			zone.write_buffer.append(buffer_id)
			
		return zone
																																							
	def do_write(self, zone) :
		# do_write try to program data to nand
				
		sb = zone.logical_blk							
		num_chunks, num_dummy = zone.get_num_chunks_to_write()
		 		 		 					
		# check free slots of nandcmd_table
		# in order to send cell mode command, we need one more nandcmd slot
		if nandcmd_table.get_free_slot_num() < (num_chunks + 1) :
			return
							
		# get write cmd
		if zone.write_cmd_queue.length() == 0 :
			print('error zone : %d'%zone.no)
		ftl_cmd = zone.write_cmd_queue.pop()
			
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

			chunk_index = build_chunk_index(page, index)
			meta.set_valid_bitmap(way, block, chunk_index)					
									
			# invalidate "valid chunk bitmap", "valid chunk count" with old physical address
			# if mapping address is 0, it is unmapped address 
			if old_physical_addr != UNMAP_ENTRY :
				# calculate way, block, page of old physical address
				old_way, old_nand_block, old_nand_page, old_chunk_offset = parse_map_entry(old_physical_addr)		
				chunk_index = build_chunk_index(old_nand_page, old_chunk_offset)
				
				# return value of clear_valid_bitmap() is not correct in zns, use get_valid_sum_ext()
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
			
			if ftl_cmd.sector_count == 0 and zone.write_cmd_queue.length() > 0:
				# get next command from queue
				ftl_cmd = zone.write_cmd_queue.pop()
		
		# push first write commmand for remaine sector count
		if ftl_cmd.sector_count > 0 :
			zone.write_cmd_queue.push_first(ftl_cmd)
			
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
			buffer_id = zone.write_buffer.pop(0)	
			cmd_desc.buffer_ids.append(buffer_id)				
		cmd_desc.seq_num = self.seq_num
		
		ftl2fil_queue.push(cmd_index)		
		#end nand cmd for fil
		
		if num_dummy > 0 :				
			print('program dummy')						
																										
		# update super page index and check status of closing block (end of super block)
		is_close, block_addr, way_list = sb.update_page()
		
		# the block number should be moved to closed block list in block manager
		if is_close == True  :
			# to do something for zone close
			blk_manager = blk_grp.get_block_manager_by_zone(block_addr, way_list)
			blk_manager.set_close_block(block_addr)

		# update num_chunks_to_write
		zone.update_write_info(num_chunks)
		
		zone.check_flush_done()						
																																																				
	def do_trim(self, lba, sector_count) :
		log_print('do trim - lba : %d, sector_count : %d'%(lba, sector_count))
		
		chunk_addr_start = lba / SECTORS_PER_CHUNK
		chunk_addr_end = (lba + sector_count - 1) / SECTORS_PER_CHUNK
		
		while chunk_addr_start <= chunk_addr_end :
			meta.map_table[chunk_addr_start] = 0xFFFFFFFF	
			chunk_addr_start = chunk_addr_start + 1
					
	@measure_time			
	def handler(self, log_time = None) :				
		# do host workload operation		
		# fetch command
		self.try_to_fetch_cmd()
				
		for index in range(zone_mgr.get_open_zone_num()) :															
			# do write
			zone = self.check_write_buffer_done()
			
			if zone != None :
				# check open logical block
				if zone.logical_blk.is_open() == False :
					# this code is required when size of zone is larger than size of super block
					# in this simulation, size of zone is aligned by multiplication of size of super block
					blk_manager = blk_grp.select_block_manager_for_free_block(FREE_BLK_LEVELING)	
				
					blk_no, way_list = blk_manager.get_free_block(erase_request = True)

					# meta is global variable, it is required for reseting during open, current setting is None
					zone.logical_blk.open(blk_no, way_list, None, blk_manager.cell_mode, blk_manager.nand_info)
				
				# check ready to write to zone
				if zone.is_ready_to_write(zone.logical_blk.cell_mode) == True:
					self.do_write(zone)
					
					if zone.state == ZONE_STATE_FULL :
						print('zone %d is full'%(zone.no))
					break
					
				if zone.is_flush() == True :
					self.do_write(zone)	
			
		# do read
		if self.num_chunks_to_read > 0 :
			self.do_read()
												
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
	
	def zone_debug(self) :
		zone_mgr.debug()																												
		
class ftl_zns_statistics :
	def __init__(self) :
		print('zns statstics init')
																																	
	def print(self) :
		print('zns statstics')

zone_mgr = zone_manager(NUM_ZONES, NUM_WAYS, NUM_OPEN_ZONES)
												
if __name__ == '__main__' :
	print ('module ftl (flash translation layer of zns)')
	
	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)
	meta.config(NUM_WAYS, ftl_nand)	
	ftl = ftl_zns_manager(NUM_WAYS, None)
			
	print('ssd capacity : %d GB'%SSD_CAPACITY)
#	print('ssd actual capacity : %d'%SSD_CAPACITY_ACTUAL)
	print('num of lba (512 byte sector) : %d'%NUM_LBA)
	print('num of logical chunk (4K unit) : %d'%(NUM_LBA/SECTORS_PER_CHUNK))	
	
	print('size of zone : %d MB'%(ZONE_SIZE / 1024 / 1024))
	print('num of zone : %d'%NUM_ZONES)

	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 19, 1, 2, NAND_MODE_SLC, ftl_nand))
	blk_grp.add('user', block_manager(NUM_WAYS, None, 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, NAND_MODE_MLC, ftl_nand))

	print('\ntest zone operation')

	zone = zone_mgr.open(32)
	for index in range(int(zone.max_num_chunks / 4)) :
		zone.update_write_info(2)

	zone = zone_mgr.open(64)
	zone = zone_mgr.open(262144)	
	zone_mgr.debug()
	
	zone = zone_mgr.get(262144*4)
	for index in range(5) :
		zone = zone_mgr.open(262144*8*index)
	
	zone_mgr.debug()
	
	zone = zone_mgr.get(262144*4)
	
	if zone != None :
		print('close zone %d'%zone.no)	
	zone_mgr.close(262144*4)
	
	zone_mgr.debug()
	
	zone_mgr.empty(0)
	zone_mgr.empty(4)
																													
	ftl.start()
	ftl.debug()
																						