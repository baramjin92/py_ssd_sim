#!/usr/bin/python

import os
import sys
import random
import numpy as np
import pandas as pd

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import *
from config.ssd_param import *

from model.queue import *

from sim_event import *

def log_print(message) :
	event_log_print('[ftl]', message)

class ftl_nand_info :
	def __init__(self, bits_per_cell, page_size, page_num ,block_num) :
		self.bits_per_cell = bits_per_cell
		self.bytes_per_page = page_size			# page size is multi-plane page
		self.pages_per_block = page_num 
		self.blocks_per_way = block_num

		self.chunks_per_page = int(self.bytes_per_page / BYTES_PER_CHUNK)
		self.chunks_per_block = int(self.chunks_per_page * self.pages_per_block)
		self.chunks_per_way = int(self.chunks_per_block * self.blocks_per_way)

class gc_cmd_desc :
	def __init__(self, nsid, cmd_tag) :
		self.nsid = nsid
		self.cmd_id = cmd_tag
		self.lba_index = []
		self.buffer_ids = []
		self.gc_meta = []
		self.count = 0

GC_QUEUE_ID_BASE = 1000

class gc_id_context :
	def __init__(self, gc_id_num, id_base = 0x2000, queue_id = GC_QUEUE_ID_BASE) :
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

# initialize hil2ftl queue 
# hil2ftl_high/low_queue conveys ftl_cmd_desc
# ftl_cmd_desc is defined in the ftl.py
hil2ftl_high_queue = queue(FTL_CMD_QUEUE_DEPTH)
hil2ftl_low_queue = queue(FTL_CMD_QUEUE_DEPTH)

# initialize ftl2fil queue
# ftl2fil_queue conveys cmd_index of nandcmd_table
ftl2fil_queue = queue(64)

# initialize fil2ftl queue
# fil2ftl queue conveys gc contents
fil2ftl_queue = queue(64) 																
 																																				 																																				
if __name__ == '__main__' :
	print ('module ftl (flash translation layer) common')
																																							