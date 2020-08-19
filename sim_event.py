#!/usr/bin/python

import random
import numpy as np
import pandas as pd

from sim_log import *

def event_log_print(tag, message) :
	log.print(event_mgr.timetick, event_mgr.prev_time, tag, message)

def save_log_event(node_delete) :
	def save_log_event(*args, **kwargs) :
		result = node_delete(*args, **kwargs)
		message = '%s - %s' %(event_debug_dest(result.dest), event_debug_type(result.code))
		event_log_print('[event]', message)
		#print('[event]', message)			
		return result
	
	return save_log_event

# define event model name
class event_model :
	def __init__(self) :
		self.MODEL_HOST = 0x01
		self.MODEL_HIC = 0x02
		self.MODEL_NAND = 0x04
		self.MODEL_NFC = 0x08
		self.MODEL_MEM = 0x10
		self.MODEL_KERNEL = 0x20
	
# define event type
class event_type : 
	def __init__(self) :
		self.EVENT_TICK = 0x05
		self.EVENT_RESULT = 0x06
		
		self.EVENT_COMMAND_START = 0x10
		self.EVENT_COMMAND_END = 0x11
		self.EVENT_READ_DATA_START = 0x12
		self.EVENT_READ_DATA_END = 0x13
		self.EVENT_WRITE_DATA_START = 0x14
		self.EVENT_WRITE_DATA_END = 0x15
		self.EVENT_WRITE_DATA = 0x16
		self.EVENT_REQ_DATA_START = 0x17
		self.EVENT_REQ_DATA_END = 0x18
		self.EVENT_COMPLETION = 0x19
		
		self.EVENT_NAND_CNA_END = 0x20
		self.EVENT_NAND_DIN_END = 0x21
		self.EVENT_NAND_DOUT_END = 0x22
		self.EVENT_NAND_SENSE_END = 0x23
		self.EVENT_NAND_PROG_END = 0x24
		self.EVENT_NAND_ERASE_END = 0x25
		self.EVENT_NAND_CHK_BEGIN = 0x26
		self.EVENT_NAND_CHK_END = 0x27
		
		self.EVENT_ADD_COMPLETION = 0x30
		self.EVENT_USER_DATA_READY = 0x31
		self.EVENT_RX_BUFFER_READY = 0x32

		self.EVENT_MEMORY_ACCESS = 0x40

		self.EVENT_SSD_READY = 0x80

def event_debug_dest(dest) :
	model_name = {
		event_dst.MODEL_HOST : 'Host',
		event_dst.MODEL_HIC : 'HIC',
		event_dst.MODEL_NAND : 'Nand',
		event_dst.MODEL_NFC : 'NFC',
		event_dst.MODEL_MEM : 'Memory',
		event_dst.MODEL_KERNEL : 'Kernel'	
	}
	
	dest_str = ''
	for model in model_name :
		if dest & model :
			dest_str = dest_str + model_name[model] + '|'
			
	return dest_str
	
def event_debug_type(code) :
	code_name = {
		0 : 'event_not_defined',
			
		event_id.EVENT_TICK : 'kernel event tick',
		event_id.EVENT_RESULT : 'kernel event result',

		event_id.EVENT_COMMAND_START : 'event_command_start',
		event_id.EVENT_COMMAND_END : 'event_commnad_end',
		event_id.EVENT_READ_DATA_START : 'event_read_data_start',
		event_id.EVENT_READ_DATA_END : 'event_read_data_end',
		event_id.EVENT_WRITE_DATA_START : 'event_write_data_start',
		event_id.EVENT_WRITE_DATA_END : 'event_write_data_end',
		event_id.EVENT_WRITE_DATA : 'event_write_data',
		event_id.EVENT_REQ_DATA_START : 'event_req_data_start',
		event_id.EVENT_REQ_DATA_END : 'event_req_data_end',
		event_id.EVENT_COMPLETION : 'event_completion',
			
		event_id.EVENT_NAND_CNA_END : 'event_nand_cna_end',
		event_id.EVENT_NAND_DIN_END : 'event_nand_din_end',
		event_id.EVENT_NAND_DOUT_END : 'event_nand_dout_end',
		event_id.EVENT_NAND_SENSE_END : 'event_nand_sense_end',
		event_id.EVENT_NAND_PROG_END : 'event_nand_prog_end',
		event_id.EVENT_NAND_ERASE_END : 'event_nand_erase_end',
		event_id.EVENT_NAND_CHK_BEGIN : 'event_nand_chk_begin',
		event_id.EVENT_NAND_CHK_END : 'event_nand_chk_end',

		event_id.EVENT_ADD_COMPLETION : 'event_add_completion',
		event_id.EVENT_USER_DATA_READY : 'event_user_data_ready',				
		event_id.EVENT_RX_BUFFER_READY : 'event_rx_buffer_ready',

		event_id.EVENT_MEMORY_ACCESS : 'event_memory_access',

		event_id.EVENT_SSD_READY :'event_ssd_ready'							
	}							
		
	return code_name[code]

class event_node :
	def __init__(self, time = 0, code = 0, dest = 0, seq_num = 0) :
		self.time = time
		self.code = code
		self.dest = dest
		self.seq_num = seq_num

		# arguments of event are distinguished with host and nand 
		# so far, we didn't use common argument name, however we can change it later.' 

		# host command param
		self.queue_id = 0
		self.host_id = 0
		self.host_code = 0
		self.host_lba = 0
		self.num_sectors = 0																	
		
		# nand command param
		self.nand_id = 0
		self.cmd_code = 0
		self.nand_addr = 0
		self.chunk_offset = 0
		self.chunk_num = 0
		
		# common buffer param
		self.main_data = []
		self.meta_data = []
		self.buf_id = 0						# buf_id use internal operation of nfc only, it will be check later to change with main_data
				
		# linked list
		self.prev = None
		self.next = None
						
	def set_param(self, code, dest, seq_num = 0, arg = 0) :
		self.code = code
		self.dest = dest
		self.seq_num = seq_num
		self.arg = arg
													
	def debug() :
		log.print('[event]', 'debug event item')			
						
class event_manager :
	def __init__(self, event_num = 1) :
		self.head = None
		self.tail = None
		self.count = 0
		
		# unit of time is ns
		self.timetick = 0
		self.prev_time = 0				
		
		# debug
		self.max_count = 0
		
	def get_current_time(self) :
		return self.timetick

	def add_accel_time(self, time) :
		self.timetick = self.timetick + time
		
	def increase_time(self) :
		self.timetick = self.timetick + 1
																								
	def add_node(self, node) :
		if self.head is None :
			self.head = node	
			self.tail = node
		else :
			self.tail.next = node
			node.prev = self.tail
			self.tail = node
			
		self.count = self.count + 1		
		
	def insert_node(self, index, node) :
		if index > self.count :
			event_log_print('[event]', 'error index')
			return
		
		if self.head is None :
			self.add_node(node)
		else :
			# look for node by index
			next_node = self.head
			for i in range(index) :
				next_node = next_node.next
			
			if next_node is None :
				# add_node
				self.tail.next = node
				node.prev = self.tail
				self.tail = node
			else :	
				node.prev = next_node.prev
				node.next = next_node
								
				# check head
				if next_node == self.head :
					self.head = node 
				else :
					node.prev.next = node
				
				next_node.prev = node
				
		self.count = self.count + 1

	def insert_node_by_time(self, node) :		
		if self.head is None :
			self.add_node(node)
		else :
			next_node = self.head
			while next_node is not None :
				if next_node.time <= node.time :		
					next_node = next_node.next
				else :
					node.prev = next_node.prev
					node.next = next_node
									
					# check head
					if next_node == self.head :
						self.head = node 
					else :
						node.prev.next = node
					
					next_node.prev = node
					break
			
			# add last node								
			if next_node is None :
				# add_node
				self.tail.next = node
				node.prev = self.tail
				self.tail = node
				
		self.count = self.count + 1
		if self.count > self.max_count :
			self.max_count = self.count
	
	@save_log_event																																																		
	def delete_node(self, index) : 
		if index >= self.count :
			event_log_print('[event]', 'error index')
			return None
	
		node = self.head
		i = 0
		
		# look for node by index
		node = self.head
		for i in range(index) :
			node = node.next
		
		if node == self.head :
			self.head = node.next
		else :
			node.prev.next = node.next					
												
		if node == self.tail :
			self.tail = node.prev
		else :
			node.next.prev = node.prev
				
		node.prev = None
		node.next = None															

		self.count = self.count - 1

		#event_log_print('[event]', 'delete [%d, %d] remain %s'%(index, node.time, self.debug()))						
		return node			 					
	
	# unit of time is ns		 								 								 							 								 								 		
	def alloc_new_event(self, time) :		
		time = self.timetick + time
		
		'''																																																												
		index = 0
		node = self.head
		while node is not None :
			if node.time <= time :		
				index = index + 1
				node = node.next
			else :
				break
				
		node = event_node(time)
		self.insert_node(index, node)
		'''
		node = event_node(time)
		self.insert_node_by_time(node)
							
		#event_log_print('[event]', 'alloc index [%d, %d] remain %s'%(index, time, self.debug()))
		
		return node
																											
	def debug(self) :
		node = self.head
		link_result = ''
		while node is not None :
			link_result = link_result + str(node.time) + ' '		
			node = node.next
						
		return link_result
				
	def print_log_event(self, node, debug) :
		if debug == True :
			message = '%s - %s' %(event_debug_dest(node.dest), event_debug_type(node.code))
			event_log_print('[event]', message)
				
def test_event_manager() :

	node = event_mgr.alloc_new_event(10)
	node.dest = event_dst.MODEL_NFC
	node = event_mgr.alloc_new_event(15)
	node.dest = event_dst.MODEL_NFC
	node = event_mgr.alloc_new_event(50)
	node.dest = event_dst.MODEL_NFC
	node = event_mgr.alloc_new_event(20)
	node.dest = event_dst.MODEL_NAND | event_dst.MODEL_NFC
	node = event_mgr.alloc_new_event(5)
	node.dest = event_dst.MODEL_NFC
	node = event_mgr.alloc_new_event(60)
	node.dest = event_dst.MODEL_HOST
	node = event_mgr.alloc_new_event(15)
	node.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
			
	print(event_mgr.debug())
	
	exit = False

	while exit is False :
		event_mgr.timetick = event_mgr.timetick + 1
		
		if event_mgr.head is not None :
			node = event_mgr.head	
						
			if event_mgr.timetick >= node.time :
				#event_mgr. print_log_event(node, True)

				if node.dest & event_dst.MODEL_HOST :
					print('host : %d'%node.time)
				if node.dest & event_dst.MODEL_HIC :
					print('hic : %d'%node.time)
				if node.dest & event_dst.MODEL_NAND :
					print('nand : %d'%node.time)
				if node.dest & event_dst.MODEL_NFC :
					print('nfc : %d'%node.time)
				if node.dest & event_dst.MODEL_KERNEL :
					print('kernel : %d'%node.time)
					
				event_mgr.delete_node(0)								
		else :
			exit = True
									
	print('exit event manager')							
			
event_mgr = event_manager(0)					
event_dst = event_model()
event_id = event_type()
																														
if __name__ == '__main__' :
	print ('sim event init')
	
	test_event_manager()						