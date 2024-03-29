#!/usr/bin/python

import os
import sys
import random

import csv
import re

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.nandcmd import *
from model.ftl_common import *
from model.ftl_meta import *

from sim_event import *

# block manager and super block need nand info
# this information is shared from block manager to super block when new super block is opend.

debug_log_msg = ''

def log_print(message) :
	event_log_print('[ftl]', message)

def print_log(func) :
	def print_log(*args, **kwargs) :
		result = func(*args, **kwargs)
		
		global debug_log_msg
		#print(debug_log_msg)
		debug_log_msg = ''
		
		return result
	
	return print_log

cell_mode_name = { NAND_MODE_SLC : 'SLC', NAND_MODE_MLC : 'MLC', NAND_MODE_TLC : 'TLC', NAND_MODE_QLC : 'QLC' }
cell_mode_conv = { 'NAND_MODE_SLC' : NAND_MODE_SLC, 'NAND_MODE_MLC' : NAND_MODE_MLC, 'NAND_MODE_TLC' : NAND_MODE_TLC, 'NAND_MODE_QLC' : NAND_MODE_QLC }

FREE_BLOCKS_THRESHOLD_HIGH = 20
FREE_BLOCKS_THRESHOLD_LOW = 10

BLK_STATUS_ERASED = 0
BLK_STATUS_OPEN = 1
BLK_STATUS_CLOSE = 2
BLK_STATUS_VICTIM = 3
BLK_STATUS_DEFECTED = 4

FREE_BLK_LEVELING = 0
FREE_BLK_RANDOM = 1

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
	def __init__(self, num_way, way_list, start_block, end_block, threshold_low = 1, threshold_high = 2, cell_mode = NAND_MODE_MLC, nand_info = None) :
		self.exhausted = False
		self.start_block = start_block
		self.end_block = end_block
		self.num_free_block = end_block - start_block + 1
		self.num_close_block = 0
		self.num_defect_block = 0
		self.threshold_low = threshold_low
		self.threshold_high = threshold_high
		self.cell_mode = cell_mode
		
		self.nand_info = nand_info
						
		# when we use super block concept in conventional ssd, we only need representative value for blk_status and way_list
		# we extend then to list type, in order to use sub block policy for zns or sata ssd. 
		self.num_way = num_way
		self.blk_status = []
		self.way_list = []
		for index in range(num_way) :
			self.blk_status.append(block_status(self.nand_info.blocks_per_way))
			if way_list == None :
				self.way_list.append(index)
			else :
				self.way_list.append(way_list[index])
			
		# in the python, list is used for managing blocks
		# in the c code, bitmap is better than array in order to reduce size of memory 
		# free_blocks, close_blocks, defect_blocks should be update in order to distinguish same block number with having different ways
		self.free_blocks = []
		self.close_blocks = []
		for index in range(start_block, end_block+1) :
			self.free_blocks.append(index)
		
		self.defect_blocks = []

	def set_blk_status(self, block, status) :
		for way in self.way_list :
			index = self.way_list.index(way)
			blk_status = self.blk_status[index]
			blk_status.set(block, status)
						
	def get_free_block_num(self) :
		return self.num_free_block						
																	
	def get_free_block(self, erase_request = False) :
		block = self.free_blocks.pop(0)
		self.num_free_block = self.num_free_block - 1
		
		# check threshold of number in free blocks
		if self.num_free_block < self.threshold_low and self.exhausted == False :
			self.exhausted = True
			
			# send event to host for throttling 
			log_print('block manager : low free blocks')

		# erase block by the request		
		if erase_request == True :								
			for way in self.way_list :
				cmd_index = nandcmd_table.get_free_slot()
				cmd_desc = nandcmd_table.table[cmd_index]
				cmd_desc.op_code = FOP_ERASE
				cmd_desc.way = way
				cmd_desc.nand_addr = block
				cmd_desc.chunk_num = 0
				cmd_desc.seq_num = 0				
	
				ftl2fil_queue.push(cmd_index)

		self.set_blk_status(block, BLK_STATUS_OPEN)

		return block, self.way_list
		
	def release_block(self, block, way_list = None) :
		if way_list == None :
			way_list = self.way_list

		self.set_blk_status(block, BLK_STATUS_ERASED)
		
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

	def set_close_block(self, block, way_list = None) :
		if way_list == None :
			way_list = self.way_list

		self.set_blk_status(block, BLK_STATUS_CLOSE)
			
		self.close_blocks.append(block)
		self.num_close_block = self.num_close_block + 1
		log_print('close block %d'%(block))
			
	def set_defect_block(self, block, way_list = None) :
		if way_list == None :
			way_list = self.way_list

		self.set_blk_status(block, BLK_STATUS_DEFECTED)
			
		self.defect_blocks.append(block)
		self.num_defect_block = self.num_defect_block + 1
		
	def get_victim_block(self) :
		# in this function, wear-level is not considered. it select victim from closed block list by round-robin policy
		if len(self.close_blocks) == 0 :
			return -1, self.way_list, False
		
		# for test, we didn't check minimum valid count, get first closed block
		block = self.close_blocks[0]
		
		for way in self.way_list :
			index = self.way_list.index(way)			
			blk_status = self.blk_status[index]
			if blk_status.get(block) == BLK_STATUS_CLOSE :
				blk_status.set(block, BLK_STATUS_VICTIM)				
				ret_val = True
			else :
				ret_val = False
				block = -1
		
		return block, self.way_list, ret_val
	
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
	
	@report_print				
	def print_sb_valid_info(self, meta_info = None, name = 'default', report_title = 'blk manager SB valid info') :																								
		
		unit = 10
		str_status = ['E', 'O', 'C', 'D']
		
		start_block = int(self.start_block / unit) * unit
		label = []
		for index in range(start_block, self.end_block+1, unit) :
			label.append('SB %04d'%index)
			
		table = self.get_table(label)
								 				 				 
		# check first way only for super block
		way = self.way_list[0]
		for block in range(start_block, self.end_block+1) :
			row = int((block-start_block)/unit)
			if block < self.start_block :
				table[row].append('N[XXXXX]')
			else :
				index = self.way_list.index(way)
				blk_status = self.blk_status[index]
				status = blk_status.get(block)
				if status == BLK_STATUS_ERASED or meta_info == None :
					valid_sum = 0
				else :
					valid_sum = meta_info.get_valid_sum(block)
				
				value = ' %s[%05d]'%(str_status[status], valid_sum)		
				table[row].append(value)	

		if report_title != None :
			report_title = 'blk manager [%s] SB valid info'%name				
		
		return report_title, table	
					
	def get_label(self) :
		return ['name', 'start block no', 'end block no', 'num of free block', 'num of close block', 'threshold1', 'threshold2', 'ways', 'cell']
		
	def get_table(self, label) :
		table = []
		for index, item in enumerate(label) :
			table.append([item])
					
		return table																														

	def get_value(self, name) :
		return [name, self.start_block, self.end_block, self.num_free_block, self.num_close_block, self.threshold_high, self.threshold_low, self.way_list, cell_mode_name[self.cell_mode]]

	def get_info(self, name = 'default', table = None) :
		# report form
		if table == None :
			table = self.get_table(self.get_label())
		value = self.get_value(name)						
						
		for index, item in enumerate(table) :
			item.append(value[index])
			
		return table
								
class block_group :								
	def __init__(self) :
		self.reset()

	def reset(self) :
		self.name = []
		self.range = []
		self.blk = []
		self.num_way = 0
		self.nand_info = None
									
	def set_physical_info(self, num_way, nand_info) :
		self.num_way = num_way
		self.nand_info = nand_info	
		
	def add(self,blk_name, blk_manager) :
		blk_range = (blk_manager.start_block, blk_manager.end_block)
		self.name.append(blk_name)
		self.range.append(blk_range)
		self.blk.append(blk_manager)

	def select_block_manager_for_free_block(self, mode) :
		if mode == FREE_BLK_LEVELING :
			num_free_block = []
			for blk in self.blk :
				num_free_block.append(blk.get_free_block_num())
			
			#print(num_free_block)
			min_value = max(num_free_block)
			index = num_free_block.index(min_value)
			return self.blk[index]
		elif mode == FREE_BLK_RANDOM :
			blk = random.choice(self.blk)
			return blk
			 				 													 				 										
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

	def get_block_manager_by_zone(self, block, way_list) :
		for index, blk_range in enumerate(self.range) :
			if block >= blk_range[0] and block <= blk_range[1] :
				blk = self.blk[index]
				if blk.way_list == way_list :
					return self.blk[index]
				
		return None		
	
	def load_csv(self, filename) :
		if self.num_way == 0 :
			print('error : need to set number of ways')
			return
		
		fp = open(filename, 'r')
		rows = csv.reader(fp)
				
		blk_grp = []		
		for row in rows :
			if row[0].find('#') != 0 :
				name = row[0]
				
				row[1] = row[1].strip()
				if row[1].upper() == 'ALL' :
					num_way = self.num_way
				else :
					num_way = int(row[1])

				row[2] = row[2].strip()
				if row[2].upper() == 'NONE' :
					num_list = None
				else :
					# make list from input
					ways= re.findall('\d', row[2])
					num_list = []
					for way in ways :
						num_list.append(int(way))
	
				sblk_no = int(row[3])
				eblk_no = int(row[4])
				threshold_low = int(row[5])
				threshold_high = int(row[6])
				row[7] = row[7].upper()
				row[7] = row[7].strip()
				cell_mode = cell_mode_conv[row[7]]

				blk = [name, num_way, num_list, sblk_no, eblk_no, threshold_low, threshold_high, cell_mode]
				blk_grp.append(blk)
																																																																									
		fp.close()
		
		#print(blk_grp)
		self.set_from_list(blk_grp)
		
	def set_from_list(self, blk_grp) :
		for blk in blk_grp :
			if type(blk[1]) != int :
				if blk[1].upper() == 'ALL' :
					num_way = self.num_way
			else :
				num_way = blk[1]
			
			if type(blk[7]) == int : 
				self.add(blk[0], block_manager(num_way, blk[2], blk[3], blk[4], blk[5], blk[6], blk[7], self.nand_info))
			else :
				self.add(blk[0], block_manager(num_way, blk[2], blk[3], blk[4], blk[5], blk[6], cell_mode_conv[blk[7]], self.nand_info))
						
	@report_print																																																																																														
	def print_info(self, report_title = 'block group info') :		
		table = self.blk[0].get_table(self.blk[0].get_label())				
												
		for index, blk in enumerate(self.blk) :				
			blk_name = self.name[index]
			table = blk.get_info(blk_name, table)
								
		return report_title, table
		
	def debug(self, meta_info = None) :
		for index, blk_manager in enumerate(self.blk) :
			blk_manager.print_sb_valid_info(meta_info, self.name[index])				

SB_OP_WRITE = 0
SB_OP_READ = 1		
						
# in order to gurantee nand parallem, ftl use super block context]
class super_block :
	def __init__(self, num_way, name, op_mode = SB_OP_WRITE) :
		self.cur_way_index = num_way - 1		# set last way in order to next operation	
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

	@print_log
	def open(self, block_addr, way_list, meta_info, cell_mode = NAND_MODE_MLC, nand_info = None) :	
		self.block_addr = block_addr	
		# in order to start from 0, cur_way_index is initialized by last value
		self.cur_way_index = self.num_way - 1 		
		
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

		self.nand_info = nand_info
		#	print('%s : BYTES_PER_PAGE : %d, PAGES_PER_BLOCK : %d, BLOCKS_PER_WAY : %d'%(self.__class__.__name__, self.nand_info.bytes_per_page, self.nand_info.pages_per_block, self.nand_info.blocks_per_way))
					
		if self.cell_mode == NAND_MODE_SLC :
			self.end_page = int(self.nand_info.pages_per_block / self.nand_info.bits_per_cell)
			self.size = int((self.num_way * self.nand_info.pages_per_block * self.nand_info.bytes_per_page / self.nand_info.bits_per_cell)/1024/1024)
		else :
			self.end_page = self.nand_info.pages_per_block
			self.size = int((self.num_way * self.nand_info.pages_per_block * self.nand_info.bytes_per_page)/1024/1024)

		# TLC use one shot program method, the other nand use page program method
		if self.cell_mode == NAND_MODE_TLC :
		 	self.page_unit = 3
		 	self.program_unit = self.nand_info.chunks_per_page * self.page_unit		
		else :
		 	self.page_unit = 1
		 	self.program_unit = self.nand_info.chunks_per_page
			
		global debug_log_msg
		debug_log_msg = '\n%s [%s] open : %d, alloc num : %d, mode : %s, size : %d MB, end_page : %d'%(self.__class__.__name__, self.name, block_addr, self.allocated_num, cell_mode_name[self.cell_mode], self.size, self.end_page)
		#debug_log_msg = debug_log + '\nway list : %s'%(self.ways)
		
	def is_open(self) :
		if self.allocated_num == 0 :
			return False
		else :
			return True

	def get_cell_mode(self) :
		return self.cell_mode

	def get_num_chunks_to_write(self, num_chunks_to_write) :
		 num_chunks = min(num_chunks_to_write, self.program_unit)
		 num_dummy = self.program_unit - num_chunks
		 
		 return num_chunks, num_dummy
			                 	                 
	def get_block_addr(self) :
		return self.block_addr  

	# return value : way, block, page (plane will be added later)
	def get_physical_addr(self) :
		# look for unclosed way and return physical address
		for loop in range(self.num_way) :
			self.cur_way_index = (self.cur_way_index + 1) % self.num_way
			
			index = self.cur_way_index
			
			if self.block[index] != 0xFFFFFFFF :
				return self.ways[index], self.block[index], self.page[index]
		
	# it is called after sending the program command		
	@print_log														
	def update_page(self) :
		index = self.cur_way_index		
	
		# get way
		way = self.ways[index]
		
		# increase page addr
		self.page[index] = self.page[index] + self.page_unit
				 							 			
		# check last page
		if self.page[index] == self.end_page :
			# close block
			self.block[index] = 0xFFFFFFFF
			self.allocated_num = self.allocated_num - 1

			#print('\n%s sb way %d close'%(self.name, way))							
			# to do for updating valid count														 			

		if self.allocated_num == 0 :
			global debug_log_msg
			debug_log_msg = '\n%s sb close : %d, end page : %d'%(self.name, self.block_addr, self.end_page)
							
			return True, self.block_addr, self.ways
		
		return False, self.block_addr, self.ways
		
	def get_value(self, meta_info = None) :																	
		last_page = []
		valid_count = 0
		for index in range(self.num_way) :			
			last_page.append(self.page[index] - 1)
			if meta_info != None :
				way = self.ways[index]
				valid_count = valid_count + meta_info.valid_count[way][self.block_addr]

		columns = []
		columns.append(['name', self.name])
		columns.append(['cell_mode', cell_mode_name[self.cell_mode]])
		columns.append(['size', '%d MB'%self.size])
		columns.append(['block addr', self.block_addr])
		columns.append(['way_list', self.ways])
		columns.append(['valid_count', valid_count])			
		columns.append(['last page', last_page])
		
		return columns																				
		 
	@report_print	 
	def debug(self, meta_info = None, report_title = 'SB info') :
		if report_title != None :
			report_title = 'SB [%s] info'%self.name
		table = self.get_value(meta_info)
		return report_title, table

def unit_test_conv_ssd() :
	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)

	blk_grp.add('meta', block_manager(NUM_WAYS, None, 1, 9, 1,  2, NAND_MODE_SLC, ftl_nand))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 20, 1, 2, NAND_MODE_SLC, ftl_nand))
	blk_grp.add('user', block_manager(NUM_WAYS, None, 20, 100, 1, 2, NAND_MODE_TLC, ftl_nand))
	
	blk_grp.print_info()
	blk_grp.debug()
	
	#print('\n\nget blk manager with block number (5)')
	#blk_manager = blk_grp.get_block_manager(5)	
	#block, way_list, ret_val = blk_manager.get_victim_block()
	#print(block)

def unit_test_zns_ssd() :
	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)

	num_way = 2
	blk_grp.add('user1', block_manager(num_way, [0,4], 1, 100, 1, 2, NAND_MODE_MLC, ftl_nand))
	blk_grp.add('user2', block_manager(num_way, [1,5], 1, 100, 1, 2, NAND_MODE_MLC, ftl_nand))
	blk_grp.add('user3', block_manager(num_way, [2,6], 1, 100, 1, 2, NAND_MODE_MLC, ftl_nand))
	blk_grp.add('user4', block_manager(num_way, [3,7], 1, 100, 1, 2, NAND_MODE_MLC, ftl_nand))

	blk_grp.print_info()

	print('test select blk manager for free block')
		
	for index in range(10) :
		blk_mgr = blk_grp.select_block_manager_for_free_block(FREE_BLK_LEVELING)
		blk, way_list = blk_mgr.get_free_block()
		print('get free block no : %d, ways : %s'%(blk, str(way_list)))
	
	print('\n')
	blk_grp.debug()
	
def unit_test_sb() :
	print('test super block operation')
	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)

	sb = super_block(4, 'host')
	if sb.is_open() == False :
		sb.open(10, [1, 5, 3, 10],  None, NAND_MODE_MLC, ftl_nand)
	
	num_chunks, num_dummy  = sb.get_num_chunks_to_write(10)	
	print('chunk num to write of SB : %d'%num_chunks)

	for index in range(24) :
		way, block, page = sb.get_physical_addr()
		print('current write position - way : %d, block : %d, page : %d'%(way,block, page))
		
		sb.update_page()
	
	sb.debug(None)	
		
blk_grp = block_group()																																																																																																
if __name__ == '__main__' :
	print ('module block manager of ftl (flash translation layer)')
	
	#unit_test_conv_ssd()
	unit_test_zns_ssd()
	unit_test_sb()
	
	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)

	blk_grp.reset()
	blk_grp.set_physical_info(8, ftl_nand)
	blk_grp.load_csv('test_blk_config.csv')	
	blk_grp.print_info()
	
																			