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

from model.nandcmd import *
from model.ftl_common import *

from sim_event import *

# block manager 

def log_print(message) :
	event_log_print('[ftl]', message)

FREE_BLOCKS_THRESHOLD_HIGH = 20
FREE_BLOCKS_THRESHOLD_LOW = 10

BLK_STATUS_ERASED = 0
BLK_STATUS_OPEN = 1
BLK_STATUS_CLOSE = 2
BLK_STATUS_VICTIM = 3
BLK_STATUS_DEFECTED = 4

class block_status :
	def __init__(self, block_num) :
		self.status = []
		self.erase_count = []
		for index in range(block_num) :
			self.status.append(BLK_STATUS_ERASED)
			self.erase_count.append(0)
			
	def set(self, block, status) :
		self.status[block] = status
		
	def get(self, block) :
		return self.status[block]

# if we use super block concept, one block manager is needed
# if we want to separate block concept, it extend to number of way
class block_manager :
	def __init__(self, num_way, start_block, end_block, threshold_low = 1, threshold_high = 2) :
		self.exhausted = False
		self.start_block = start_block
		self.end_block = end_block
		self.num_free_block = end_block - start_block + 1
		self.num_close_block = 0
		self.num_defect_block = 0
		self.threshold_low = threshold_low
		self.threshold_high = threshold_high
		
		self.num_way = num_way
		self.blk_status = block_status(BLOCKS_PER_WAY)
		
		# in the python, list is used for managing blocks
		# in the c code, bitmap is better than array in order to reduce size of memory 
		self.free_blocks = []
		self.close_blocks = []
		for index in range(start_block, end_block+1) :
			self.free_blocks.append(index)
		
		self.defect_blocks = []
		
	def get_free_block_num(self) :
		return self.num_free_block						
																	
	def get_free_block(self, erase_request = False, way = 0) :
		block = self.free_blocks.pop(0)
		self.num_free_block = self.num_free_block - 1
		
		# check threshold of number in free blocks
		if self.num_free_block < self.threshold_low and self.exhausted == False :
			self.exhausted = True
			
			# send event to host for throttling 
			log_print('block manager : low free blocks')
					
		# erase block by the request		
		if erase_request == True :
			for index in range(self.num_way) :
				cmd_index = nandcmd_table.get_free_slot()
				cmd_desc = nandcmd_table.table[cmd_index]
				cmd_desc.op_code = FOP_ERASE
				cmd_desc.way = index
				cmd_desc.nand_addr = block
				cmd_desc.chunk_num = 0
				cmd_desc.seq_num = 0				
	
				ftl2fil_queue.push(cmd_index)

		self.blk_status.set(block, BLK_STATUS_OPEN)

		return block
		
	def release_block(self, block) :
		self.blk_status.set(block, BLK_STATUS_ERASED)
		
		if block in self.close_blocks : 
			self.close_blocks.remove(block)
			self.num_close_block = self.num_close_block - 1
			
		self.free_blocks.append(block)
		self.num_free_block = self.num_free_block + 1

		# check threshold of number in free blocks
		if self.num_free_block >= self.threshold_low and self.exhausted == True :
			self.exhausted = False
			
			# send event to host for throttling 
			log_print('block manager : enough free blocks')

	def set_close_block(self, block) :
		self.blk_status.set(block, BLK_STATUS_CLOSE)
		self.close_blocks.append(block)
		self.num_close_block = self.num_close_block + 1
		log_print('close block %d'%(block))
			
	def set_defect_block(self, block) :
		self.blk_status.set(block, BLK_STATUS_DEFECTED)
		self.defect_blocks.append(block)
		self.num_defect_block = self.num_defect_block + 1
		
	def get_victim_block(self) :
		# in this function, wear-level is not considered. it select victim from closed block list by round-robin policy
		if len(self.close_blocks) == 0 :
			return -1, False
		
		# for test, we didn't check minimum valid count, get first closed block
		block = self.close_blocks[0]
		if self.blk_status.get(block) == BLK_STATUS_CLOSE :
			self.blk_status.set(block, BLK_STATUS_VICTIM)
			return block, True
		else :
			return -1, False

	def set_exhausted_status(self, status) :
		self.exhausted = status

	def get_exhausted_status(self) :
		return self.exhausted						
																					
	def debug_valid_block_info(self, meta_info = None) :
		print('\nvalid block info')
		
		for block in self.close_blocks :
			if meta_info == None :
				sum = 100
			else :
				sum = meta_info.get_valid_sum(block)
			print('block no : %d, valid sum : %d'%(block, sum))
			
	def debug(self, meta_info = None, name = 'default') :
		print('\nblock manager : %s'%(name))
		print('start block no : %d, end block no : %d'%(self.start_block, self.end_block))
		print('num of free block : %d'%self.num_free_block)
		print('num of close block : %d'%self.num_close_block)
		print('free block threshold1 : %d, threshold2 : %d'%(self.threshold_high, self.threshold_low))
												
		unit = 10
		str_status = ['E', 'O', 'C', 'D']
		
		if self.start_block % unit != 0 :
			str = 'SB %04d :'%(self.start_block % unit)
		else :
			str = ''
		  		  
		for block in range(self.start_block, self.end_block+1) :
			status = self.blk_status.get(block)
			if status == BLK_STATUS_ERASED :
				valid_sum = 0
			else :
				if meta_info == None :
					valid_sum = 0
				else :
					valid_sum = meta_info.get_valid_sum(block)
				
			if block % unit == 0 :
				value = 'SB %04d : %s[%05d]'%(block, str_status[status], valid_sum)
			else :
				value = ' %s[%05d]'%(str_status[status], valid_sum)
				
			str = str + value
			if block % unit == (unit-1) :
				print(str)
				str = ''			
		print(str)
	
class block_group :								
	def __init__(self) :
		self.name = []
		self.range = []
		self.blk = []
		
	def add(self,blk_name, blk_manager) :
		blk_range = (blk_manager.start_block, blk_manager.end_block)
		self.name.append(blk_name)
		self.range.append(blk_range)
		self.blk.append(blk_manager)
		
	def get_block_manager(self, block) :
		for index, blk_range in enumerate(self.range) :
			if block >= blk_range[0] and block <= blk_range[1] :
				return self.blk[index]
				
		return None		
	
	def get_block_manager_by_name(self, name) :
		for index, blk_name in enumerate(self.name) :
			if name == blk_name :
				return self.blk[index]

		return None 
						
	def print_info(self) :		
		blk_name = {'name' : ['name', 'start block', 'end_block']}				
						
		blk_pd = pd.DataFrame(blk_name)																
		for index in range(len(self.blk)) :				
			blk_name = self.name[index]
			blk_range = self.range[index]							
							
			blk_columns = []
			blk_columns.append(blk_name)
			blk_columns.append(blk_range[0])
			blk_columns.append(blk_range[1])
																				
			blk_pd['%d'%(index)] = pd.Series(blk_columns, index=blk_pd.index)
				
		print('block group info')		
		print(blk_pd)
		print('\n')					

	def debug(self, meta_info = None) :
		for index, blk_manager in enumerate(self.blk) :
			blk_manager.debug(meta_info, self.name[index])				

SB_OP_WRITE = 0
SB_OP_READ = 1		
						
# in order to gurantee nand parallem, ftl use super block context]
class super_block :
	def __init__(self, num_way, name, op_mode = SB_OP_WRITE) :
		self.way_index = num_way - 1		# set last way in order to next operation	
		self.num_way = num_way
		self.allocated_num = 0
		self.cell_mode = NAND_MODE_MLC
		self.op_mode = op_mode
		
		# in order to consider block replacement policy, blocks are managed by array 		
		self.block_addr = 0
		self.ways = []		
		self.block = []
		self.page = []
		for index in range(num_way) :
			self.ways.append(index)
			self.block.append(0xFFFFFFFF)
			self.page.append(0)	

			self.name = name

	def open(self, block_addr, way_list, meta_info, cell_mode = NAND_MODE_MLC) :	
		self.block_addr = block_addr	
		# in order to start from 0, way_index is initialized by last value
		self.way_index = self.num_way - 1 		
		
		if len(way_list) == self.num_way :
			self.ways = way_list
								
		for index in range(self.num_way) :
			# normal super block concept, each block address is same
			# this value can be changed by non super block concept.
			self.block[index] = block_addr
			self.page[index] = 0	
	
			if self.op_mode == SB_OP_WRITE and meta_info != None :
				# initialize valid bitmap and count
				way = self.ways[index]
				meta_info.reset_valid_info(way, block_addr) 
		
		self.allocated_num = self.num_way
		self.cell_mode = cell_mode
		if self.cell_mode == NAND_MODE_MLC or self.cell_mode == NAND_MODE_TLC :
			self.end_page = PAGES_PER_BLOCK
		elif self.cell_mode == NAND_MODE_SLC :
			self.end_page = PAGES_PER_BLOCK / 2		# this calculation is based on MLC nand

		print('\n%s sb open : %d, allocated num : %d'%(self.name, block_addr, self.allocated_num))

	def is_open(self) :
		if self.allocated_num == 0 :
			return False
		else :
			return True

	def get_cell_mode(self) :
		return self.cell_mode

	def get_num_chunks_to_write(self, num_chunks_to_write) :
		# when we decide num_chunks with CHUNKS_PER_PAGE, it is basic policy based on MLC multi-plane nand. 
		# in order to consider TLC we need to change num_chunks decision logic
		if self.cell_mode == NAND_MODE_MLC or self.cell_mode == NAND_MODE_SLC :
		 	num_chunks = min(num_chunks_to_write, CHUNKS_PER_PAGE)
		else :
		 	num_chunks = min(num_chunks_to_write, (CHUNKS_PER_PAGE  * 3))			# one shot program

		return num_chunks
		                 
	def get_block_addr(self) :
		return self.block_addr  

	# return value : way, block, page (plane will be added later)
	def get_physical_addr(self) :
		# look for unclosed way and return physical address
		for index in range(self.num_way) :
			self.way_index = (self.way_index + 1) % self.num_way
			
			index = self.way_index
			
			way  = self.ways[index]
			if self.block[index] != 0xFFFFFFFF :
				return way, self.block[index], self.page[index]
		
	# it is called after sending the program command																	
	def update_page(self) :
		index = self.way_index		
	
		# get way
		way = self.ways[index]
		
		# increase page addr
		self.page[index] = self.page[index] + 1
				 							 			
		# check last page
		if self.page[index] == self.end_page :
			# close block
			self.block[index] = 0xFFFFFFFF
			self.allocated_num = self.allocated_num - 1

			#print('\n%s sb way %d close'%(self.name, way))							
			# to do for updating valid count														 			

		if self.allocated_num == 0 :
			print('\n%s sb close : %d, end page : %d'%(self.name, self.block_addr, self.end_page))
							
			return True, self.block_addr
		
		return False, self.block_addr

	def debug(self, meta_info = None) :
		block_size = self.num_way * PAGES_PER_BLOCK * BYTES_PER_PAGE
		
		print('\n%s super block (size of SB : %d MB)'%(self.name, block_size/1024/1024))
		print('current block addr  : %d'%self.block_addr)
										
		last_page = []
		valid_count = 0
		for index in range(self.num_way) :			
			last_page.append(self.page[index] - 1)
			if meta_info != None :
				way = self.ways[index]
				valid_count = valid_count + meta_info.valid_count[way][self.block_addr]
		
		print('valid count of SB : %d'%valid_count)
		print('last page of SB')
		print(last_page)
																																																
if __name__ == '__main__' :
	print ('module block manager of ftl (flash translation layer)')

	#blk_manager = block_manager(NUM_WAYS, 10, 100)	
	
	blk_grp = block_group()
	blk_grp.add('meta', block_manager(NUM_WAYS, 1, 9))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, 10, 20))
	blk_grp.add('user', block_manager(NUM_WAYS, 20, 100))
	
	blk_grp.print_info()
	blk_grp.debug()
	
	print('block 5')
	blk_manager = blk_grp.get_block_manager(5)
	blk_manager.debug()
	
	block = blk_manager.get_victim_block()
	print(block)
	
	print('test super block operation')
	sb = super_block(4, 'host')
	if sb.is_open() == False :
		sb.open(10, [1, 5, 3, 10],  None, NAND_MODE_MLC)
		
	print('chunk num to write of SB : %d'%sb.get_num_chunks_to_write(10))

	for index in range(24) :
		way, block, page = sb.get_physical_addr()
		print('current write position - way : %d, block : %d, page : %d'%(way,block, page))
		
		sb.update_page()
	
	sb.debug(None)	
																			