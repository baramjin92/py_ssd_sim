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

def log_print(message) :
	event_log_print('[namespace]', message)

class namespace_desc :
	def __init__(self, nsid, slba, elba) :
		self.nsid = nsid
		self.slba = slba
		self.elba = elba
		self.blk_name = None
		self.logical_blk = None
									
		# write_cmd_queue try to gather write commands before programing data to nand
		self.write_cmd_queue = queue(32)
		self.num_chunks_to_write = 0
		self.min_chunks_for_page = CHUNKS_PER_PAGE
			
		self.write_buffer = []
	
		# read cmd
		self.num_chunks_to_read = 0
		self.read_start_chunk = 0
		self.read_cur_chunk = 0
		self.read_queue_id = 0
		self.read_cmd_tag = 0
		
		# gc context
		# change queue id by nsid
		self.gc_cmd_id = gc_id_context(32, 0x2000, GC_QUEUE_ID_BASE + nsid)
		self.gc_cmd_queue = queue(32)
		self.gc_issue_credit = 8
		self.num_chunks_to_gc_read = 0
		self.num_chunks_to_gc_write = 0

		self.gc_blk = None				
		self.gc_src_blk = None
										
	def set_blk_name(self, name) :
		self.blk_name = name
	
	def is_idle(self) :
		if self.num_chunks_to_write == 0 :
			return True
		else :
			return False
				
	def is_ready_to_write(self) :
		if self.num_chunks_to_write >= self.min_chunks_for_page and len(self.write_buffer) >= self.min_chunks_for_page :
			if self.write_cmd_queue.length() == 0 :
				print('error : is_ready_to_write')
				self.debug

			return True
		else :
			return False							
						
	def get_num_chunks_to_write(self) :					
		return self.logical_blk.get_num_chunks_to_write(self.num_chunks_to_write)																				
																																																
	def update_write_info(self, num_chunks) :
		self.num_chunks_to_write = self.num_chunks_to_write - num_chunks			
		
	def report_get_label(self) :
		return {'namespace' : ['id', 'slba', 'elba', 'meta range', 'blk_name', 'num_chunk_to_write', 'write_buffer']}
		
	def report_get_columns(self, meta_range) :
		columns = []
		columns.append(self.nsid)
		columns.append(self.slba)
		columns.append(self.elba)
		columns.append(meta_range)
		columns.append(self.blk_name)
		columns.append(self.num_chunks_to_write)			
		columns.append(str(self.write_buffer))
		
		return columns																				
		
	def debug(self) :
		# report form
		sb_info_label = self.report_get_label()
		sb_info_columns = self.report_get_columns(None)						
						
		sb_info_pd = pd.DataFrame(sb_info_label)				
		sb_info_pd['value'] = pd.Series(sb_info_columns, index=sb_info_pd.index)

		print('\n')
		print(sb_info_pd)
			
class namespace_manager :
	def __init__(self, ns_percent) :
		self.meta_range = []
		self.table = []
		self.num_namespace = 0
		
		self.config(ns_percent)
			
	def config(self, ns_percent) :
		self.meta_range.clear()
		self.table.clear()
		
		self.num_namespace = len(ns_percent)
						
		sum = 0							
		for index, p in enumerate(ns_percent) :
			lba_base = int(NUM_LBA * sum / 100)
			elba = int(NUM_LBA * p / 100) - 1

			self.meta_range.append([lba_base, lba_base + elba])
			self.table.append(namespace_desc(index, 0, elba))

			sum = sum + p

#	def set_num_way(self, num_way) :
#		self.num_way = num_way

	def get_num(self) :
		return self.num_namespace
																			
	def get(self, nsid) :		
		ns =  self.table[nsid]													
		return ns

	def get_by_qid(self, queue_id) :
		for ns in self.table :
			if ns.gc_cmd_id.queue_id == queue_id :
				return ns
		
		return None

	def get_range(self, nsid) :
		ns = self.table[nsid]																															
		return ns.slba, ns.elba 

	def lba2meta_addr(self, nsid, lba) :
		range = self.meta_range[nsid]
		return  int(range[0] + lba)
		
	def meta_addr2lba(self, meta_index) :
		for range in self.meta_range :
			if meta_addr >= range[0] and meta_addr <= range[1] :
				return int(meta_addr - range[0])		
						
	def debug(self) :																																																		
		print('\nnum of namespace : %d\n'%(self.num_namespace))
		
		ns = self.get(0)
		sb_info_label = ns.report_get_label()					
		sb_info_pd = pd.DataFrame(sb_info_label)				
		
		for index, range in enumerate(self.meta_range) :
			ns = self.get(index)			
			sb_info_columns = ns.report_get_columns(range)							
			sb_info_pd['ns %d'%index] = pd.Series(sb_info_columns, index=sb_info_pd.index)

		print(sb_info_pd)
																											
namespace_mgr = namespace_manager([10, 40, 50])
												
if __name__ == '__main__' :
	print ('module namespace')
	
	global NUM_CHANNELS
	global WAYS_PER_CHANNELS
	global NUM_WAYS	
		
	NUM_CHANNELS = 8
	WAYS_PER_CHANNELS = 1
	NUM_WAYS = (NUM_CHANNELS * WAYS_PER_CHANNELS) 
	
#	ftl = ftl_iod_manager(None)
			
	print('ssd capacity : %d GB'%SSD_CAPACITY)
#	print('ssd actual capacity : %d'%SSD_CAPACITY_ACTUAL)
	print('num of lba (512 byte sector) : %d'%NUM_LBA)
	print('num of logical chunk (4K unit) : %d'%(NUM_LBA/SECTORS_PER_CHUNK))	

	blk_name = ['user1', 'user2', 'user3']	
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 19, 1, 2))
	blk_grp.add(blk_name[0], block_manager(int(NUM_WAYS/2), [0, 1, 2, 3], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))
	blk_grp.add(blk_name[1], block_manager(int(NUM_WAYS/4), [4, 5], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))
	blk_grp.add(blk_name[2], block_manager(int(NUM_WAYS/4), [6, 7], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))

	for nsid in range(namespace_mgr.get_num()) :	
		ns = namespace_mgr.get(nsid)
		ns.set_blk_name(blk_name[nsid])
		
	namespace_mgr.debug()

	print('\ntest namespace operation')
																						