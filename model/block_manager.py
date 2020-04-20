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
	
	
	
																			