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

from model.queue import *
from model.ftl_common import *

from sim_event import *

def log_print(message) :
	event_log_print('[ftl]', message)

def build_map_entry(way, block, page, chunk_offset) :
	address = way * CHUNKS_PER_WAY + block * CHUNKS_PER_BLOCK + page * CHUNKS_PER_PAGE + chunk_offset

	return address

def build_map_entry2(way, nand_addr, chunk_offset) :
	address = way * CHUNKS_PER_WAY + nand_addr + chunk_offset
	
	return address

def get_nand_addr(address) :
	return int(address % CHUNKS_PER_WAY)

# CHUNKS_PER_PAGE is calculated in the MLC mode, we need to consider another cell mode
def build_chunk_index(page, chunk_offset = 0) :
	return page * CHUNKS_PER_PAGE + chunk_offset

# use to check adjacent address in same way, block, page (only difference is chunk offset)
def check_same_physical_page(next_map_entry, map_entry) :
	if int(next_map_entry / CHUNKS_PER_PAGE) == int(map_entry / CHUNKS_PER_PAGE) :
		#log_print('To check adjecent is true between %x and %x'%(next_map_entry, map_entry))
		return True
	else :
		return False

def parse_map_entry(address) :
	way = int(address / CHUNKS_PER_WAY) 
	block = int((address % CHUNKS_PER_WAY) / CHUNKS_PER_BLOCK) 
	page = int((address % CHUNKS_PER_BLOCK) / CHUNKS_PER_PAGE)
	chunk_offset = int((address % CHUNKS_PER_PAGE))
	
	return way, block, page, chunk_offset

PAGE_MASK = (0x01 << CHUNKS_PER_PAGE) - 1

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

	def config(self, num_way, blocks_per_way = BLOCKS_PER_WAY) :
		# valid chunk bitmap
		self.valid_bitmap = np.empty((num_way, blocks_per_way, self.size_of_bitmap), np.uint32)

		# valid chunk count data  : valid_count[way][block]
		self.valid_count = np.empty((num_way, blocks_per_way), np.uint32)
		self.valid_sum = np.empty((blocks_per_way), np.uint32)

	# this is only useful in conventional ssd using super block concept
	def get_valid_sum(self, block) :			
		return self.valid_sum[block]

	# this is useful for zone and io determinism depending on way list
	def get_valid_sum_ext(self, block, way_list) :
		sum = 0
		for way in way_list :
			sum = sum + self.valid_count[way][block]

		return sum			

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
		
		return  self.valid_sum[block]
		
	def check_valid_bitmap(self, way, block, chunk) :
		bmp = self.valid_bitmap[way][block]
		index = int(chunk / 32)
		
		# result has all bitmap info of page
		result = (bmp[index] >> int(chunk % 32)) & PAGE_MASK		
		return result
									
	def print_meta_constants(self) :
		print('ftl meta constants')
		print('BYTES_PER_PAGE : %d KB'%int(BYTES_PER_PAGE/1024))																													
		print('PAGES_PER_BLOCK : %d'%PAGES_PER_BLOCK)
		print('BLOCKS_PER_WAY : %d\n'%BLOCKS_PER_WAY)
		
		print('CHUNKS_PER_PAGE : %d'%CHUNKS_PER_PAGE)																													
		print('CHUNKS_PER_BLOCK : %d'%CHUNKS_PER_BLOCK)
		print('CHUNKS_PER_WAY : %d\n'%CHUNKS_PER_WAY)
																																																																								
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

meta = ftl_meta() 																																				 																																				 																																				 																																				
if __name__ == '__main__' :
	print ('module ftl (flash translation layer) common')
	
	meta.config(NUM_WAYS)

	meta.print_meta_constants()

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
	
																																						