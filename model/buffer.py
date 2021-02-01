#!/usr/bin/python

import os
import sys
import random

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from sim_event import *

BM_WRITE = 0
BM_READ = 1
	
def log_print(message) :
	print('[bm] ' + message)

# DDR bandwidth and bus width should be changed by controller specification
# it affects sustained performance because it requires more bus access
DDR_BUS_WIDTH = 32			# bit

DDR2_400_BW = 3200			# MB /s
DDR3_800_BW = 6400			# MB /s
DDR4_1600_BW = 12800		# MB /s

SRAM_LATENCY = 10

def calculate_chunk_latency(ddr_bandwidth, bus_width, show_info = False) :
	bandwidth = int(ddr_bandwidth * bus_width / 8)
	overhead = 40																							# DDR overhead (percentage)
	byte_latency = ((1 / bandwidth) * 1000)												# ns  
	chunk_latency = int((1 - overhead / 100) * 4096 * byte_latency)		# ns
	
	if show_info == True :
		print('ddr bandwidth : %d MB/s'%bandwidth)
		print('ddr overhead : %d %% '%overhead)
		print('byte latency : %f ns'%byte_latency)
		print('chunk latency with overhead : %f ns'%chunk_latency)
			
	return chunk_latency

class buffer_slot :
	def __init__(self, buffer_id) :
		self.buffer_id = buffer_id
		
		self.main_data = 0				# in the real system, it should be buffer which size is 4K or larger (it is changed by size of chunk or slice)
		self.extra_data = 0				# extra data has meta data which save to spare area of nand
		
		#self.lba = 0							# some hw controller has lba for checking data
		self.queue_id = 0
		self.cmd_tag = 0					# buffer has cmd_tag in order to distinguish who owns it	
	
		self.status = 0			
															
# buffer manager doesn't care the allocated buffer id
# allocated buffer id should be saved for release buffer id.								
class buffer_manager :
	def __init__(self, write_buffer_num, read_buffer_num) :
		self.bm_slots = []
		self.write_free = []
		self.read_free = []
		
		buffer_num = write_buffer_num + read_buffer_num
		
		for index in range(buffer_num) : 
			self.bm_slots.append(buffer_slot(index))
			
		for index in range(write_buffer_num) :
			self.write_free.append(index)
			
		for index in range(write_buffer_num, buffer_num) :
			self.read_free.append(index)
		
		self.max_write = write_buffer_num
		self.max_read = read_buffer_num
		self.max_num = buffer_num
		
		self.chunk_latency = 0
		
	def set_latency(self, ddr_bandwidth, bus_width) :
		self.chunk_latency = calculate_chunk_latency(ddr_bandwidth, bus_width)	
									
	def get_buffer(self, buffer_id, queue_id = 0, cmd_tag = 0, length = 1) :
		# allocate the one buffer id from free slots
		alloc_buffer_id = []

		if buffer_id == BM_WRITE :
			free = self.write_free
		elif buffer_id == BM_READ :
			free = self.read_free
						
		if len(free) >= length  :
			for index in range(length) :
				buffer_id = free.pop(0)
				self.bm_slots[buffer_id].queue_id = queue_id
				self.bm_slots[buffer_id].cmd_tag = cmd_tag
				self.bm_slots[buffer_id].main_data = 0
				self.bm_slots[buffer_id].extra_data = 0				
				alloc_buffer_id.append(buffer_id)		
													
			return alloc_buffer_id, True 			
		else :
			return alloc_buffer_id, False

	def release_buffer(self, buffer_id) :
		# log_print('release buffer slot %d'%(buffer_id)) 		
		
		if buffer_id < self.max_write :
			free = self.write_free
		elif buffer_id < self.max_num :
			free = self.read_free
		else :
			print('error release buffer [%d : %d] - buffer_id : %d', buffer_id)
				
		free.append(buffer_id)
								
	def get_num_free_slots(self, buffer_id) :
		if buffer_id == BM_WRITE :
			free = self.write_free
		elif buffer_id == BM_READ :
			free = self.read_free

		return len(free)
	
	def set_data(self, buffer_id, main_data, extra_data, event_callback = None) :
		self.bm_slots[buffer_id].main_data = main_data
		self.bm_slots[buffer_id].extra_data = extra_data											
		
		# Write Buffer is DRAM, Read Buffer is SRAM (we ignore SRAM latency') 
		if buffer_id == BM_WRITE :
			event_mgr.add_accel_time(self.chunk_latency)
		elif buffer_id == BM_READ :
			event_mgr.add_accel_time(SRAM_LATENCY)
																
	def get_data(self, buffer_id, event_callback = None) :
		# Write Buffer is DRAM, Read Buffer is SRAM (we ignore SRAM latency') 
		if buffer_id == BM_WRITE :
			event_mgr.add_accel_time(self.chunk_latency)
		elif buffer_id == BM_READ :
			event_mgr.add_accel_time(SRAM_LATENCY)
									
		return (self.bm_slots[buffer_id].main_data, self.bm_slots[buffer_id].extra_data)																											
	
	def get_meta_data(self, buffer_id) :
		return self.bm_slots[buffer_id].extra_data 
	
	def get_cmd_id(self, buffer_id) :
		queue_id = self.bm_slots[buffer_id].queue_id
		cmd_tag = self.bm_slots[buffer_id].cmd_tag
		return queue_id, cmd_tag
	
	def debug(self, name) :
		if name == 'free' :
			print('write free id : ')
			print(self.write_free)

			print('read free id : ')
			print(self.read_free)
				
def unit_test_bm() :	
	bm = buffer_manager(20, 10)	
		
	print('write free slot num : %d'%(bm.get_num_free_slots(BM_WRITE)))	
	print('read free slot num : %d'%(bm.get_num_free_slots(BM_READ)))	
				
	print('write allocate two')			
	buf_id1, ret_val = bm.get_buffer(BM_WRITE)
	buf_id2, ret_val = bm.get_buffer(BM_WRITE)

	bm.set_data(buf_id2[0], 5, 6)
	bm.set_data(buf_id1[0], 3, 2)

	print('read allocate one')	
	buf_id3, ret_val = bm.get_buffer(BM_READ)

	print('write free slot num : %d'%(bm.get_num_free_slots(BM_WRITE)))	
	print('read free slot num : %d'%(bm.get_num_free_slots(BM_READ)))	

	bm.debug('free')
			
	main_data, extra_data = bm.get_data(buf_id2[0])
	
	print('buf id : %d, main data : %d, extra data : %d'%(buf_id2[0], main_data, extra_data))	
	
	bm.release_buffer(buf_id2[0])
	print('write free slot num : %d'%(bm.get_num_free_slots(BM_WRITE)))
	bm.debug('free')

	print('write allocate 5')	
	buffer_id, ret_val = bm.get_buffer(BM_WRITE, 5)
	print('allocated buffer id :')
	print(buffer_id)
	print('write free slot num : %d'%(bm.get_num_free_slots(BM_WRITE)))
	bm.debug('free')
	
# define write and read buffer 
# buffer size is defined at ssd_parm.py

# life cycle of bm_write
# 1. hil allocated buffer and add it to rx_buffer_list(in hic)
# 2. hic request to send data with buffer id from rx_buffer_list(in hic)
# 3. after host transfer data, hic move buffer_id from rx_buffer_list to xxxxx of ftl
# 4. ftl add buffer_id to nandcmd_desc
# 5. 	

bm = buffer_manager(ssd_param.SSD_WRITE_BUFFER_NUM, ssd_param.SSD_READ_BUFFER_NUM)
bm.set_latency(DDR3_800_BW, DDR_BUS_WIDTH)
																	
if __name__ == '__main__' :
	log_print ('module buffer manager main')
	
	unit_test_bm()			
																			