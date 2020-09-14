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
#from model.buffer_cache import *
from model.queue import *
from model.hic import *
from model.ftl_common import *

from sim_event import *
from sim_eval import *

# hil fetches host command from hic and send it to ftl

def log_print(message) :
	event_log_print('[hil]', message)

class write_cmd :
	def __init__(self) :
		self.queue_id = 0
		self.cmd_tag = 0
		self.num_buffer_slots = 0
		self.offset = 0
														
class hil_manager :
	def __init__(self, hic) :
		# write_cmd_queue manage write buffer allocation
		self.write_cmd_queue = queue(NUM_HOST_CMD_TABLE)

		# register hic now in order to use interface queue				
		self.hic_model = hic
																																	
		self.hil_stat = hil_statistics()											

	def handle_new_host_cmd(self) :
		# get queue_id, cmd_tag from cmd_exec_queue of hic
		queue_id, cmd_tag = self.hic_model.cmd_exec_queue.pop()
		
		# make ftl command from host command
		# ftl has two prioirity queue (high/low)
		# read command uses high priority que
		# write/trim/flush command use low priority queue
		# if we have multiple ftl core, these queue policies should be changed
		cmd_desc = self.hic_model.get_cmd_desc(queue_id, cmd_tag)
		
		if cmd_desc.code == HOST_CMD_READ :
			ftl_cmd = ftl_cmd_desc()
			ftl_cmd.code = cmd_desc.code
			ftl_cmd.lba = cmd_desc.lba
			ftl_cmd.sector_count = cmd_desc.num_requested_sectors
			ftl_cmd.cmd_tag = cmd_tag
			ftl_cmd.qid = queue_id
			
			log_print('read command pass to ftl - qid : %d, cid : %d, lba : %d, sectors : %d'%(ftl_cmd.qid, ftl_cmd.cmd_tag, ftl_cmd.lba, ftl_cmd.sector_count))										
			# add ftl_cmd to ftl command queue (high priority)
			hil2ftl_high_queue.push(ftl_cmd)		
		else :
			log_print('write/trim/flush command pass to ftl directly')

			ftl_cmd = ftl_cmd_desc()
			ftl_cmd.code = cmd_desc.code
			ftl_cmd.lba = cmd_desc.lba
			ftl_cmd.sector_count = cmd_desc.num_requested_sectors
			ftl_cmd.cmd_tag = cmd_tag
			ftl_cmd.qid = queue_id
			
			if cmd_desc.code == HOST_CMD_WRITE :
				# set information for allocating write buffer
				# hil is charge on alloaction write buffer and get data in buffer
				write_cmd_desc = write_cmd()
				write_cmd_desc.queue_id  = queue_id
				write_cmd_desc.cmd_tag = cmd_tag
				write_cmd_desc.offset = 0
				write_cmd_desc.num_buffer_slots = cmd_desc.num_requested_sectors / SECTORS_PER_CHUNK
				
				self.write_cmd_queue.push(write_cmd_desc)	
			
			# add ftl_cmd to ftl command queue (low priority)
			hil2ftl_low_queue.push(ftl_cmd)
																									
		# save vcd file if option is activate
								
		return

	def alloc_write_buffer(self, num_free_slots) :
		# get write cmd info from write write_cmd_queue
		write_cmd_desc = self.write_cmd_queue.get_entry_1st()
		queue_id = write_cmd_desc.queue_id
		cmd_tag = write_cmd_desc.cmd_tag
		offset = write_cmd_desc.offset
		num_buffer_slots = min(write_cmd_desc.num_buffer_slots, num_free_slots)
						
		# allocate buffer
		buffer_ids, ret_val = bm.get_buffer(BM_WRITE, queue_id, cmd_tag, int(num_buffer_slots))
		log_print('alloc write buffer : %d, %d'%(num_free_slots, num_buffer_slots))
		#print(buffer_ids)
		
		# push buffer_ids to rx_buffer_prep of hic
		self.hic_model.add_rx_buffer(0, buffer_ids)

		# send event to hic
		next_event = event_mgr.alloc_new_event(0)
		next_event.dest = event_dst.MODEL_HIC
		next_event.code = event_id.EVENT_RX_BUFFER_READY

		# check completion of buffer allocation
		write_cmd_desc.offset = offset + num_buffer_slots
		write_cmd_desc.num_buffer_slots = write_cmd_desc.num_buffer_slots - num_buffer_slots
		
		if write_cmd_desc.num_buffer_slots == 0 :
			self.write_cmd_queue.pop()

		return

	@measure_hil_time
	def handler(self) :
		# hil doesn't have event handler.
		# it check cmd_exec_queue of hic, and fetch command and execute  
				
		# check command execution queue and ftl command queue 
		if self.hic_model.cmd_exec_queue.length() > 0 :
			self.handle_new_host_cmd()
			
		# check write buffer allocation queue		
		if self.write_cmd_queue.length() > 0 :
			# get number of free slots of write buffer
			num_free_slots = bm.get_num_free_slots(BM_WRITE)
			if num_free_slots > 0 :
				self.alloc_write_buffer(num_free_slots)
		return 								
																																		
class hil_statistics :
	def __init__(self) :
		print('hil statstics init')
																												
	def print(self) :
		print('statstics')
				
if __name__ == '__main__' :
	print ('module hil (host interface layer)')
	
	hil = hil_manager(None)
	
																			