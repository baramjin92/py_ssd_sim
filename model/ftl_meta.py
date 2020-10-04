#!/usr/bin/python

import os
import sys
import random

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import *
from config.ssd_param import *

from model.queue import *
from model.ftl_common import *

from sim_event import *
from sim_array import *

def log_print(message) :
	event_log_print('[ftl]', message)

# define term of chunk
# size of chunk is 4K, chunk is minimum unit for saving data
# nand page has multiple chunks, if the size of nand page is 8k, nand page has 2 chunks 
# BYTES_PER_PAGE = single plane page size x plane number
#CHUNKS_PER_PAGE = int(BYTES_PER_PAGE / BYTES_PER_CHUNK)
#CHUNKS_PER_BLOCK = int(CHUNKS_PER_PAGE * PAGES_PER_BLOCK)
#CHUNKS_PER_WAY = int(CHUNKS_PER_BLOCK * BLOCKS_PER_WAY)

#UNMAP_ENTRY = 0
UNMAP_ENTRY = 0xFFFFFFFF

# ftl should have meta datum for managing nand and mapping
# in this simulation, it has 3 meta datum.
#  1. map_table : (size of entry : 32bit)
#  2. valid_chunk_bitmap[way][block]
#  3. valid_chunk_count[way][block] : (size of entry : 32bit)
class ftl_meta :
	def __init__(self, num_lba) :
		self.map_table = None
		self.nand_info = None
		self.valid_bitmap = None
		self.valid_count = None
		self.valid_sum = None
		
	def config(self, num_lba, num_way, nand_info) :
		# meta data of ftl																				
		# so far, we use simple np, in order to support real capacity of ssd, we should change it by "memmap" of numpy		
		self.map_table = make_1d_array(num_lba, UNMAP_ENTRY)

		self.nand_info = nand_info
		blocks_per_way = nand_info.blocks_per_way

		self.CHUNKS_PER_PAGE = nand_info.chunks_per_page
		self.CHUNKS_PER_BLOCK = nand_info.chunks_per_block
		self.CHUNKS_PER_WAY = nand_info.chunks_per_way

		self.PAGE_MASK = (0x01 << self.CHUNKS_PER_PAGE) - 1
												
		# valid chunk bitmap
		self.size_of_bitmap = int((self.CHUNKS_PER_BLOCK + 31)/32)

		# valid chunk bitmap
		self.valid_bitmap = make_3d_array(num_way, blocks_per_way, self.size_of_bitmap)

		# valid chunk count data  : valid_count[way][block]
		self.valid_count = make_2d_array(num_way, blocks_per_way)
		self.valid_sum = make_1d_array(blocks_per_way)
																									
		self.print_meta_constants()

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
		#self.valid_bitmap[way][block] = np.zeros(self.size_of_bitmap)
		self.valid_bitmap[way][block] = make_1d_array(self.size_of_bitmap)
	
		self.valid_count[way][block] = 0
		self.valid_sum[block] = 0
	
	def set_valid_bitmap(self, way, block, chunk) :
		bmp = self.valid_bitmap[way][block]
		index = int(chunk / 32)
		mask = 0x01 << int(chunk % 32)
		try :
			bmp[index] = (bmp[index] | mask) & 0xFFFFFFFF
			self.valid_bitmap[way][block] = bmp
	
			self.valid_count[way][block] = self.valid_count[way][block] + 1
			self.valid_sum[block] = self.valid_sum[block] + 1
	
		except :
			print('way : %d, block : %d, chunk : %d, index : %d'%(way, block, chunk, index))		

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
		result = (bmp[index] >> int(chunk % 32)) & self.PAGE_MASK		
		return result

	def build_map_entry(self, way, block, page, chunk_offset) :
		address = way * self.CHUNKS_PER_WAY + block * self.CHUNKS_PER_BLOCK + page * self.CHUNKS_PER_PAGE + chunk_offset
	
		return address
	
	def build_map_entry2(self, way, nand_addr, chunk_offset) :
		address = way * self.CHUNKS_PER_WAY + nand_addr + chunk_offset
		
		return address
	
	def get_nand_addr(self, address) :
		return int(address % self.CHUNKS_PER_WAY)
	
	# CHUNKS_PER_PAGE is calculated in the MLC mode, we need to consider another cell mode
	def build_chunk_index(self, page, chunk_offset = 0) :
		return page * self.CHUNKS_PER_PAGE + chunk_offset
	
	# use to check adjacent address in same way, block, page (only difference is chunk offset)
	def check_same_physical_page(self, next_map_entry, map_entry) :
		if int(next_map_entry / self.CHUNKS_PER_PAGE) == int(map_entry / self.CHUNKS_PER_PAGE) :
			#log_print('To check adjecent is true between %x and %x'%(next_map_entry, map_entry))
			return True
		else :
			return False
	
	def parse_map_entry(self, address) :
		way = int(address / self.CHUNKS_PER_WAY) 
		block = int((address % self.CHUNKS_PER_WAY) / self.CHUNKS_PER_BLOCK) 
		page = int((address % self.CHUNKS_PER_BLOCK) / self.CHUNKS_PER_PAGE)
		chunk_offset = int((address % self.CHUNKS_PER_PAGE))
		
		return way, block, page, chunk_offset
	
	def get_num_chunks_for_page(self) :
		return self.CHUNKS_PER_PAGE

	def get_num_chunks_for_write(self, cell_mode) :
		if cell_mode == NAND_MODE_TLC :
		 	self.program_unit = self.CHUNKS_PER_PAGE *3		
		else :
		 	self.program_unit = self.CHUNKS_PER_PAGE
		
		return self.program_unit
																							
	def print_meta_constants(self) :
		print('%s : BYTES_PER_PAGE : %d, PAGES_PER_BLOCK : %d, BLOCKS_PER_WAY : %d'%(self.__class__.__name__, self.nand_info.bytes_per_page, self.nand_info.pages_per_block, self.nand_info.blocks_per_way))		
		print('%s : CHUNKS_PER_PAGE : %d, CHUNKS_PER_BLOCK : %d, CHUNKS_PER_WAY : %d\n'%(self.__class__.__name__, self.CHUNKS_PER_PAGE, self.CHUNKS_PER_BLOCK, self.CHUNKS_PER_WAY))		
	
	@report_print
	def print_map_table(self, lba, num_sectors) :		
		chunk_num = int(num_sectors / SECTORS_PER_CHUNK)
		chunk_start = int(lba / SECTORS_PER_CHUNK)
		chunk_end = chunk_start + chunk_num - 1

		unit = 4
		table = []
		for chunk_index in range(chunk_start, chunk_end+1, unit) :
			label = 'lba %08d'%(chunk_index * SECTORS_PER_CHUNK)
			table.append([label])	

		for chunk_index in range(chunk_start, chunk_end+1) :
			row = int((chunk_index-chunk_start) / unit)
			value = ' 0x%08x'%(self.map_table[chunk_index])
			table[row].append(value)

		report_title = 'map table - start lba : %d, end lba : %d'%(lba, chunk_end * SECTORS_PER_CHUNK)
		return report_title, table				
				
	@report_print																			
	def print_valid_data(self, way, block) :		
		unit = 8
		table = []
		chunk_index = 0
		for index in range(0, self.size_of_bitmap, unit) :
			value = 'chunk %04d'%(index * 32)
			table.append([value]) 
			
		for index in range(0, self.size_of_bitmap) :
			row = int(index / unit)
			value = '0x%08x'%(self.valid_bitmap[way][block][index])
			table[row].append(value)
							
		report_title = 'valid info[way %d, block %d], valid count[%d]'%(way, block, self.valid_count[way][block])
	
		return report_title, table
	
meta = ftl_meta(NUM_LBA) 				

build_map_entry = meta.build_map_entry
build_map_entry2 = meta.build_map_entry2
get_nand_addr = meta.get_nand_addr
build_chunk_index = meta.build_chunk_index
check_same_physical_page = meta.check_same_physical_page
parse_map_entry = meta.parse_map_entry
get_num_chunks_for_page = meta.get_num_chunks_for_page
get_num_chunks_for_write = meta.get_num_chunks_for_write
		 																																				 																																				
if __name__ == '__main__' :
	print ('module ftl (flash translation layer) common')
	
	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)
	meta.config(NUM_LBA, ssd_param.NUM_WAYS, ftl_nand)

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
	
																																						