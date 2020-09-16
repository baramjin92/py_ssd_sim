 #!/usr/bin/python

import os
import sys
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

		# flush
		self.flush_req = False
																				
	def set_blk_name(self, name) :
		self.blk_name = name
	
	def is_idle(self) :
		if self.num_chunks_to_write == 0 :
			return True
		else :
			return False
				
	def is_ready_to_write(self, cell_mode) :
		program_unit = get_num_chunks_for_write(cell_mode)
		if self.num_chunks_to_write >= program_unit and len(self.write_buffer) >= program_unit :
			if self.write_cmd_queue.length() == 0 :
				print('error : is_ready_to_write')

			return True
		else :
			return False							
						
	def get_num_chunks_to_write(self) :					
		num_chunks, num_dummy = self.logical_blk.get_num_chunks_to_write(self.num_chunks_to_write)																				
		return num_chunks, num_dummy
																																																																																														
	def update_write_info(self, num_chunks) :
		self.num_chunks_to_write = self.num_chunks_to_write - num_chunks			

	def flush_request(self) :		
		if self.flush_req == False and self.num_chunks_to_write > 0 :			
			print('ns %d flush request remained chunks : %d'%(self.nsid, self.num_chunks_to_write))			
			self.flush_req = True	

	def is_flush(self) :
		if self.flush_req == True and self.num_chunks_to_write > 0 :			
			return True
		else :
			return False	
			
	def check_flush_done(self) :	
		if self.flush_req == True and self.num_chunks_to_write == 0 :				
			self.flush_req = False				
			print('ns %d flush done'%self.nsid)
								
	def get_label(self) :
		return ['id', 'slba', 'elba', 'meta range', 'blk name', 'num chunks to write', 'write buffer']
		
	def get_value(self, meta_range) :
		return [self.nsid, self.slba, self.elba, meta_range, self.blk_name, self.num_chunks_to_write, self.write_buffer] 																										
		
	def get_table(self) :
		label = self.get_label()
		table = []
		for index, name in enumerate(label) :
			table.append([name])
					
		return table																														
																										
class namespace_manager :
	def __init__(self, max_lba, ns_percent) :
		self.meta_range = []
		self.table = []
		self.num_namespace = 0
		
		self.config(max_lba, ns_percent)
			
	def config(self, max_lba, ns_percent) :
		self.meta_range.clear()
		self.table.clear()
		
		self.num_namespace = len(ns_percent)
						
		sum = 0							
		for index, p in enumerate(ns_percent) :
			lba_base = int(max_lba * sum / 100)
			elba = int(max_lba * p / 100) - 1

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
	
	@report_print																																																																																																			
	def debug(self) :																																																				
		ns = self.get(0)
		sb_info = ns.get_table()
		
		for index, range in enumerate(self.meta_range) :
			ns = self.get(index)			
			value = ns.get_value(self.meta_range[index])
			for i, info in enumerate(sb_info) :
				info.append(value[i])

		report_title = '\nnum of namespace : %d\n'%(self.num_namespace)
		return report_title, sb_info
																																							
if __name__ == '__main__' :
	print ('module namespace')
	
	global NUM_CHANNELS
	global WAYS_PER_CHANNELS
	global NUM_WAYS	
		
	NUM_CHANNELS = 8
	WAYS_PER_CHANNELS = 1
	NUM_WAYS = (NUM_CHANNELS * WAYS_PER_CHANNELS) 

	ftl_nand = ftl_nand_info(3, 8192*4, 256, 1024)
	meta.config(NUM_LBA, NUM_WAYS, ftl_nand)
		
#	ftl = ftl_iod_manager(None)
			
	print('ssd capacity : %d GB'%SSD_CAPACITY)
#	print('ssd actual capacity : %d'%SSD_CAPACITY_ACTUAL)
	print('num of lba (512 byte sector) : %d'%NUM_LBA)
	print('num of logical chunk (4K unit) : %d'%(NUM_LBA/SECTORS_PER_CHUNK))	

	blk_name = ['user1', 'user2', 'user3']	
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, None, 10, 19, 1, 2, NAND_MODE_SLC, ftl_nand))
	blk_grp.add(blk_name[0], block_manager(int(NUM_WAYS/2), [0, 1, 2, 3], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, NAND_MODE_MLC, ftl_nand))
	blk_grp.add(blk_name[1], block_manager(int(NUM_WAYS/4), [4, 5], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, NAND_MODE_MLC, ftl_nand))
	blk_grp.add(blk_name[2], block_manager(int(NUM_WAYS/4), [6, 7], 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH, NAND_MODE_MLC, ftl_nand))

	namespace_mgr = namespace_manager(NUM_LBA, [10, 40, 50])
	for nsid in range(namespace_mgr.get_num()) :	
		ns = namespace_mgr.get(nsid)
		ns.set_blk_name(blk_name[nsid])
			
	namespace_mgr.debug()

	print('\ntest namespace operation')
																						