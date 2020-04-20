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
from model.pcie_if import *

from sim_event import *

CMD_FETCHED = 1
DATA_TRANSFER_DONE = 2

def log_print(message) :
	event_log_print('[hic]', message)

class cmd_exec_desc :
	def __init__(self) :
		# self.queue_id = 0
		self.cid = 0
		self.code = 0
		self.lba = 0
		self.num_requested_sectors = 0
		self.num_completed_sectors = 0
		self.flags = 0												

class cmd_queue_context :
	def __init__(self, cet_size) :
		self.cet_size = cet_size
		
		# cmd_exec_table manages command operation (update num_requested_sectors and num_completed_sectors)
		# in order to access cmd_exec_table, we need cmd_tag. it is same value of host_id from host command.
		# it means that size of host command table is same with depth of host command queue.
		
		# in order to support multi queue, multiple cmd_exec_tables which is distinguished by queue_id
		self.cmd_exec_table = []
		for index in range(cet_size) :
			self.cmd_exec_table.append(cmd_exec_desc())

		self.num_pending_commands = 0
				
	def increase_pending_cmd(self) :
		self.num_pending_commands = self.num_pending_commands + 1
	
	def decrease_pending_cmd(self) :
		self.num_pending_commands = self.num_pending_commands - 1
															
# hic means host interface controller
# it is model for hardware logic
# in order to communicate with Host via PCIe(or SATA), it has rx and tx sub logic.
# hic is controlled by hil/ftl/fil layer 																																				
class hic_manager :
	def __init__(self, cet_size) :

		self.cmd_queue = []
		for index in range(NUM_HOST_QUEUE) :
			self.cmd_queue.append(cmd_queue_context(cet_size))
						
		# cmd_exec_queue is used for sending host cmd to hil
		# cmd_exec_queue is global queue
		# queue entry is pair of queue id and cmd_tag(host_id) : [queue_id, cmd_tag]				
		self.cmd_exec_queue = queue(cet_size)
		
		# cmd_cmpl_queue is local queue in hic
		# queue entry is pair of queue id and cmd_tag(host_id) : [queue_id, cmd_tag]
		self.cmd_cmpl_queue = queue(cet_size)
					
		self.rx_count = 0
		self.rx_buffer_prep = []
		self.rx_buffer_req = []
		self.rx_buffer_done = []
		
		self.tx_buffer_list = []
		self.tx_buffer_req = []
		
		# downlink_busy and uplink_busy is variable for granting host interface
		# In the multi-queue architecture, there is racing condition between multi-queue
		# we use round robin mechanism.
		self.downlink_busy = 0
		self.uplink_busy = 0
		
		self.hic_stat = hic_statistics()											
	
	# api for hil and hic
	def get_cmd_desc(self, queue_id, cmd_tag) :	
		cmd_desc = self.cmd_queue[queue_id].cmd_exec_table[cmd_tag]
		
		return cmd_desc

	# api for hil
	def add_rx_buffer(self, queue_id, buffer_ids) :
		# push buffer_ids to rx_buffer_prep (use + opeartor of list)
		self.rx_buffer_prep = self.rx_buffer_prep + buffer_ids

	# api for fil
	def add_tx_buffer(self, queue_id, buffer_id) :
		self.tx_buffer_list.append(buffer_id)
																																																																					
	def receive_host_command(self, event) :
		log_print('receive_host_command : %d, %d, %d'%(event.host_id, event.host_lba, event.num_sectors))
							
		# get queue_id and cmd_tag from host command
		# cmd_tag is index of cmd_exec_table
		queue_id = event.queue_id
		cmd_tag = event.host_id
				
		# copy host command to command descriptor
		cmd_desc = self.get_cmd_desc(queue_id, cmd_tag)
		cmd_desc.cid = cmd_tag
		cmd_desc.code = event.host_code
		cmd_desc.lba = event.host_lba
		cmd_desc.num_requested_sectors = event.num_sectors
		cmd_desc.num_completed_sectors = 0
		cmd_desc.flags = 0
		
		# increase pending command number
		self.cmd_queue[queue_id].increase_pending_cmd()
				
		# send cmd_tag to (hil) command queue												
		self.cmd_exec_queue.push([queue_id, cmd_tag])
														
		return True
																																																											
	def start_read_transfer(self) :
		buffer_id = self.tx_buffer_list.pop(0)
		queue_id, cmd_tag = bm.get_cmd_id(buffer_id)
		data, meta = bm.get_data(buffer_id)
		
		# print('tx_buffer : %d, buffer id : %d............................................................................start read transfer : %d : %d'%(len(self.tx_buffer_list), buffer_id, meta, data))																																																																																																			
		next_event = event_mgr.alloc_new_event(0)
		next_event.dest = event_dst.MODEL_HOST
		next_event.code = event_id.EVENT_READ_DATA_START
		
		# calculate transfer time with data size and transfer speed (in pcie_if.py)
		num_packets, transfer_time = calculate_xfer_time(SECTORS_PER_CHUNK)
				
		next_event = event_mgr.alloc_new_event(transfer_time)
		next_event.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
		next_event.code = event_id.EVENT_READ_DATA_END
		next_event.queue_id = queue_id
		next_event.host_id =cmd_tag
		next_event.host_lba = int(meta * SECTORS_PER_CHUNK)
		next_event.num_sectors = SECTORS_PER_CHUNK		
		next_event.main_data.append(data)
		
		self.tx_buffer_req.append(buffer_id)
		
		return True
		
	def end_read_transfer(self) :		
		# cmd_tag is index of cmd_exec_table
		buffer_id = self.tx_buffer_req.pop(0)
		queue_id, cmd_tag = bm.get_cmd_id(buffer_id)
				
		# update num_completed_sectors
		cmd_desc = self.get_cmd_desc(queue_id, cmd_tag)
		cmd_desc.num_completed_sectors = cmd_desc.num_completed_sectors + SECTORS_PER_CHUNK
		
		# release buffer
		# if we use buffer cache, we will check or add buffer list to cache instead of releasing buffer
		if ENABLE_BUFFER_CACHE == True :
			lba_index = bm.get_meta_data(buffer_id)
			index, result = bm_cache.check_hit(lba_index)
			if result == False :
				bm_cache.add(lba_index, buffer_id)
		else :	
			bm.release_buffer(buffer_id)
				
		# check completion of host command
		if cmd_desc.num_completed_sectors == cmd_desc.num_requested_sectors :
			log_print('end_read_transfer - command done : %d'%(cmd_tag))

			cmd_desc.flags |= DATA_TRANSFER_DONE
			
			if cmd_desc.flags == (DATA_TRANSFER_DONE | CMD_FETCHED) :
				self.cmd_cmpl_queue.push([queue_id, cmd_tag])

		return True
		
	def send_data_request(self, num_rx_buffer_slots) :		
		# get cmd_tag from host command
		# cmd_tag is index of cmd_exec_table
		queue_id, cmd_tag = bm.get_cmd_id(self.rx_buffer_prep[0])
				
		# calculate remain sector number
		cmd_desc = self.get_cmd_desc(queue_id, cmd_tag)
		num_remain_sectors = cmd_desc.num_requested_sectors - cmd_desc.num_completed_sectors
		num_receive_sectors = min(num_rx_buffer_slots * SECTORS_PER_CHUNK, num_remain_sectors)
		
		# request wrtie data from host to hic via host interface like SATA and PCIe
		next_event = event_mgr.alloc_new_event(0)
		next_event.dest = event_dst.MODEL_HOST
		next_event.code = event_id.EVENT_REQ_DATA_START
		
		# calculate transfer time with data size and transfer speed 
		transfer_time = 1

		# in the actual system, we don't need to send buffer slot id to host.
		# in this sumulation, we share first id of buffer between host and hic in order to write data to buffer.
		# buffer is managed by linked list, so we know first id and number of slots, we can acess whole buffer which are allocated  		
		next_event = event_mgr.alloc_new_event(transfer_time)
		next_event.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
		next_event.code = event_id.EVENT_REQ_DATA_END
		next_event.queue_id = queue_id
		next_event.host_id = cmd_tag
		next_event.num_sectors = num_receive_sectors
		#next_event.buf_slot_id = buffer_slot_id																

		# move buffer_slot_id to next list
		num_buffer_slots = int(num_receive_sectors / SECTORS_PER_CHUNK)
		for index in range(num_buffer_slots) :
			buffer_id = self.rx_buffer_prep.pop(0)
			self.rx_buffer_req.append(buffer_id)
		
		self.rx_count = num_receive_sectors

		log_print('send data request - cmd_tag(%d), req_sector(%d), cmlp_sector(%d)'%(cmd_tag, cmd_desc.num_requested_sectors, cmd_desc.num_completed_sectors))
			
		return True
		
	def send_completion_signal(self) :
		queue_id, cmd_tag = self.cmd_cmpl_queue.pop()
		
		log_print('send completion signal - queue_id(%d), cmd_tag(%d)'%(queue_id, cmd_tag))
						
		cmd_desc = self.get_cmd_desc(queue_id, cmd_tag)

		next_event = event_mgr.alloc_new_event(0)
		next_event.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
		next_event.code = event_id.EVENT_COMPLETION
		next_event.queue_id = queue_id
		next_event.host_id = cmd_tag

		self.cmd_queue[queue_id].decrease_pending_cmd()
				
		return True
		
	def handle_incoming_data(self, event) :
		
		# get packet size from event
		packet_size = event.num_sectors
		
		self.rx_count = self.rx_count - packet_size
				
		queue_id = event.queue_id
		cmd_tag = event.host_id
		
		cmd_desc = self.get_cmd_desc(queue_id, cmd_tag)
		length = int(packet_size / SECTORS_PER_CHUNK)
		for index in range(length) :
			buffer_id = self.rx_buffer_req.pop(0)

			# save data and lca to buffer
			lca = int((cmd_desc.lba + cmd_desc.num_completed_sectors) / SECTORS_PER_CHUNK + index)
			data = event.main_data.pop(0)
			
			# start memory write 
			# we need to consider this api usage
			# in order to simulate performance of memory bandwidth, it should work asynchronous method (event driven)
			bm.set_data(buffer_id, data, lca)

			# move buffer id to data transfer done list
			self.rx_buffer_done.append(buffer_id)

			# end memory write 
								
		cmd_desc.num_completed_sectors = cmd_desc.num_completed_sectors + packet_size
				
		# check completion
		if cmd_desc.num_completed_sectors == cmd_desc.num_requested_sectors :
			cmd_desc.flags |= DATA_TRANSFER_DONE

			log_print('check completion :%d'%(cmd_desc.flags))
			if cmd_desc.flags == (DATA_TRANSFER_DONE | CMD_FETCHED) :
				self.cmd_cmpl_queue.push([queue_id, cmd_tag])
		
		# return remain rx_count, if it is 0, downlink should be false
		return self.rx_count
		
	def set_manual_completion(self, queue_id, cmd_tag) :
		self.cmd_cmpl_queue.push([queue_id, cmd_tag])
		
		next_event = event_mgr.alloc_new_event(0)
		next_event.dest = event_dst.MODEL_HIC
		next_event.code = event_id.EVENT_ADD_COMPLETION
				
		return True
		
	# api for ftl	
	def set_cmd_fetch_flag(self, queue_id, cmd_tag) :
		cmd_desc = self.get_cmd_desc(queue_id, cmd_tag)

		cmd_desc.flags |= CMD_FETCHED
		
		if cmd_desc.flags == (DATA_TRANSFER_DONE | CMD_FETCHED) :
			self.cmd_cmpl_queue.push([queue_id, cmd_tag])

			next_event = event_mgr.alloc_new_event(0)
			next_event.dest = event_dst.MODEL_HIC
			next_event.code = event_id.EVENT_ADD_COMPLETION
									
		return True
		
	def event_handler(self, event) :
		# log_print('event_handler : '  + event_mgr.debug_info(event.code))
		
		if event.code == event_id.EVENT_COMMAND_START or event.code == event_id.EVENT_WRITE_DATA_START :
			self.downlink_busy = True
		
		elif event.code == event_id.EVENT_REQ_DATA_END :
			self.uplink_busy = False
			
		elif event.code == event_id.EVENT_COMMAND_END :
			self.downlink_busy = False
			self.receive_host_command(event)
		
		elif event.code == event_id.EVENT_WRITE_DATA :
			if self.handle_incoming_data(event) == 0 :
				self.downlink_busy = False

		elif event.code == event_id.EVENT_READ_DATA_END :
			self.uplink_busy = False
			self.end_read_transfer()
		
		elif event.code == event_id.EVENT_USER_DATA_READY :
			log_print('event user data ready')
		elif event.code == event_id.EVENT_RX_BUFFER_READY :
			log_print('event rx buffer ready')
		elif event.code == event_id.EVENT_ADD_COMPLETION :
			log_print('event add completion')
		
		if self.uplink_busy == False and self.cmd_cmpl_queue.length() > 0 :
			self.send_completion_signal()
			
		# check write buffer allocation and reqeust write data transfer 
		num_rx_buffer_slots = len(self.rx_buffer_prep)
		if self.uplink_busy == False and num_rx_buffer_slots > 0 and self.rx_count == 0 :
			self.send_data_request(num_rx_buffer_slots)
			self.uplink_busy = True
			 											
		# check read buffer allocation and start read transfer
		num_tx_buffer_slots = len(self.tx_buffer_list)
		if self.uplink_busy == False and num_tx_buffer_slots > 0 :
			self.start_read_transfer()
			self.uplink_busy = True
			 															
		return True
																										
class hic_statistics :
	def __init__(self) :
		print('hic statstics init')
																												
	def print(self) :
		print('hic statstics')
				
if __name__ == '__main__' :
	print ('module hic(host interface controller)')

	hic = hic_manager(NUM_CMD_EXEC_TABLE)		
		
	hic.hic_stat.print()			
																			