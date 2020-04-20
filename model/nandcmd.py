#!/usr/bin/python

import os
import sys
import random
import numpy as np
import pandas as pd

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from model.queue import *

# define nfc descriptor table
NFC_TABLE_SIZE = 1024

# define flash operation command type for firmware (ftl and fil)
FOP_USER_READ = 0
FOP_GC_READ = 1
FOP_USER_WRITE = 2
FOP_GC_WRITE = 3
FOP_ERASE = 4
FOP_SET_MODE = 5

# define command type for NFC
# this command will be added when nand model support more command like one shot program and so on
NFC_CMD_READ = 1
NFC_CMD_WRITE = 2
NFC_CMD_ERASE = 3
NFC_CMD_MODE = 4

NFC_OPT_AUTO_SEND = False

def log_print(message) :
	print('[nandcmd] ' + message)

# nand flash command descriptor 
class nfc_desc :
	def __init__(self) :
		# top half (hil or ftl)
		#self.next_slot_idx = 0
		self.queue_id = 0
		self.cmd_tag = 0
		self.op_code = 0
		self.way = 0
		#self.offset = 0
		self.gc_issue_blk_cnt = 0
		self.seq_num = 0

		# bottom_half (nand)
		self.code = 0
		self.nand_addr = 0
		self.chunk_offset = 0
		self.chunk_num = 0
		self.buffer_ids = []				
		self.option = 0

# nand flash command descriptor table (size is NFC_TABLE_SIZE)
class nfc_desc_table :
	def __init__(self, size) :
		self.table = []
		self.free_slot = []
		for index in range(size) :
			self.table.append(nfc_desc())
			self.free_slot.append(index)
			
		self.num_free_slots = size
		self.free_index = 0								

	def get_free_slot_num(self) :
		return self.num_free_slots

	def get_free_slot(self) :
		index = self.free_slot.pop(0)
		self.table[index].buffer_ids.clear()
		self.num_free_slots = self.num_free_slots - 1
		return index
		
	def release_slot(self, index) :
		self.num_free_slots = self.num_free_slots + 1
		self.free_slot.append(index)

# report descriptor
class report_desc :
	def __init__(self) :
		self.table_index = 0
		self.result = 0

# initialize flash command descriptor table
nandcmd_table = nfc_desc_table(NFC_TABLE_SIZE)

# initialize report queue						
report_queue = queue(NFC_TABLE_SIZE)								
				
if __name__ == '__main__' :
	log_print ('module nandcmd data')			
																			