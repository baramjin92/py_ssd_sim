#!/usr/bin/python

import os
import sys
import random
import numpy as np
import pandas as pd

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
#from config.sim_config import nand_param
#from config.sim_config import nand_info

from config.ssd_param import *

from sim_event import *

from model.workload import *
from model.pcie_if import *

# LBA is Logical Block Address 
# LCA is Logical Chunk Address (LSA is Logical Slice Address, it is same meaning)

DOWNLINK_IDLE = 0
DOWNLINK_CMD = 1
DOWNLINK_DATA = 2

UPLINK_IDLE = 0
UPLINK_DREQ = 1
UPLINK_DATA = 2

def log_print(message) :
	event_log_print('[host]',message)

class host_cmd :
	def __init__(self, cid) :
		self.cid = cid
		self.code = 0
		self.lba = 0
		self.num_sectors_requested = 0
		self.num_sectors_completed = 0
		self.submit_time = 0

class host_cmd_context :
	def __init__(self, host_num, queue_id = 0) :
		self.queue_id = queue_id												
		self.host_cmd_table = []
		self.host_cmd_free_slot = []
		for index in range(host_num) :
			self.host_cmd_table.append(host_cmd(index))
			self.host_cmd_free_slot.append(index)	
			
	def get_slot(self) :
		cmd_id = self.host_cmd_free_slot.pop(0)
		return cmd_id		
		
	def release_slot(self, cmd_id) :
		self.host_cmd_free_slot.append(cmd_id)	
		
	def get_host_cmd(self, cmd_id) :
		return self.host_cmd_table[cmd_id]			
								
	def get_num_free_slot(self) :
		return len(self.host_cmd_free_slot)																							
																																				
class host_manager :
	def __init__(self, host_num) :
		# set host context
		self.host_cmd_queue = []
		self.queue_ids = []
		for index in range(NUM_HOST_QUEUE) :
			self.host_cmd_queue.append(host_cmd_context(host_num, index))
			self.queue_ids.append(index)
		
		# link state 
		# these state values should be seperated when we use multi-queue option.
		# it will be changed later
		self.uplink_state = UPLINK_IDLE
		self.downlink_state = DOWNLINK_IDLE
		
		# contents of managing write data transfer
		self.tx_qid = 0xFFFFFFFF		
		self.tx_cid = 0xFFFFFFFF
		self.tx_count = 0
		#self.current_write_slot_id = 0
			
		# count number of issued host commands	
		self.num_pending_cmds = 0
		
		self.data_table = np.empty((NUM_LBA), np.int32)		
		
		self.host_stat = host_statistics(NUM_HOST_QUEUE)
	
	def generate_command(self) :
		for queue_id in self.queue_ids :
			
			# check host_cmd_free_slot	
			if self.host_cmd_queue[queue_id].get_num_free_slot() == 0 :
				#return queue_id, 0, False
				continue
									
			# set submit time to calculate latency after ending command
			submit_time = event_mgr.get_current_time()																																											
			# set code, lba, number of sector by workload type
			cmd_code, lba, sectors = wlm.generate_workload(submit_time, queue_id)
	
			# get free host cmd slot
			if cmd_code != HOST_CMD_IDLE :
				cmd_id = self.host_cmd_queue[queue_id].get_slot()
	
				log_print('generate command - queue id : %d, cmd id : %d, lba : %d, sectors : %d'%(queue_id, cmd_id, lba, sectors))
				
				host_cmd = self.host_cmd_queue[queue_id].get_host_cmd(cmd_id)
	
				host_cmd.submit_time = submit_time
				host_cmd.code = cmd_code
				host_cmd.lba = lba
				host_cmd.num_sectors_requested = sectors
				host_cmd.num_sectors_completed = 0
					
				self.num_pending_cmds = self.num_pending_cmds + 1
			
				# save to VCD file if option is activated
	
				# rotate qid for racing operation.
				qid = self.queue_ids.pop(0)
				self.queue_ids.append(qid)																																																																																											
				return queue_id, host_cmd, True
			else :
				#return queue_id, 0, False
				continue
		
		# there is no new command
		return queue_id, 0, False

	def send_command(self, queue_id, cmd) :
		log_print('send command[%d] : %d, %d, %d, %d'%(queue_id, cmd.cid, cmd.code, cmd.lba, cmd.num_sectors_requested))

		next_event = event_mgr.alloc_new_event(0)
		next_event.code = event_id.EVENT_COMMAND_START
		next_event.dest = event_dst.MODEL_HIC
		next_event.queue_id = queue_id								
												
		# calculate this value later										
		cmd_packet_delivery_time = 100										

		next_event = event_mgr.alloc_new_event(cmd_packet_delivery_time)
		next_event.code = event_id.EVENT_COMMAND_END
		next_event.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
		next_event.queue_id = queue_id
		next_event.host_id = cmd.cid
		next_event.host_code = cmd.code
		next_event.host_lba = cmd.lba
		next_event.num_sectors = cmd.num_sectors_requested												

	def command_done(self, event) :
		# get queue id and cmd id from event
		queue_id = event.queue_id
		cmd_id = event.host_id
		
		host_cmd = self.host_cmd_queue[queue_id].get_host_cmd(cmd_id)
		cmd_code = host_cmd.code
		
		# get current time from time tick and calculate latency
		current_time = event_mgr.get_current_time()	
		latency = current_time - host_cmd.submit_time
		num_sectors = host_cmd.num_sectors_requested		
				
		# move cmd_id to free_slot_link
		self.host_cmd_queue[queue_id].release_slot(cmd_id)
		
		self.num_pending_cmds = self.num_pending_cmds - 1		

		log_print('command done : pending(%d), free(%d), latency(%d)'%(self.num_pending_cmds, self.host_cmd_queue[queue_id].get_num_free_slot(), latency))
																																								
		# update statistics
		if cmd_code == HOST_CMD_READ :
			self.host_stat.perf[queue_id].update_read(num_sectors, latency)											
		elif cmd_code == HOST_CMD_WRITE :
			self.host_stat.perf[queue_id].update_write(num_sectors, latency)
						
		elif cmd_code == HOST_CMD_TRIM :																																																																																			
			log_print('trim cmd done and check operation result')
		
		# save to VCD file if option is activated
		
		return True																																					
		
	def generate_write_data(self, lba, num_sectors) :
		# the whole data is generated from first packet transfer time.
		# so this function is called just one time in start_write_transfer()
		
		lba_index = int(lba / SECTORS_PER_CHUNK) 
		length = int(num_sectors / SECTORS_PER_CHUNK)
		
		for index in range(length) :
			self.data_table[lba_index] = self.data_table[lba_index] + 1
			lba_index = lba_index + 1
		
		###if lba > 2048 :	
		###	log_print('[%08d] generate write data : lba %d %d : %d'%(event_mgr.timetick, lba, num_sectors, self.data_table[int(lba/SECTORS_PER_CHUNK)]))	
				
	def start_write_transfer(self) :
		log_print('start write transfer : %d, %d, %d'%(self.tx_qid, self.tx_cid, self.tx_count))
		
		queue_id = self.tx_qid
		
		next_event = event_mgr.alloc_new_event(0)
		next_event.code = event_id.EVENT_WRITE_DATA_START
		next_event.dest = event_dst.MODEL_HIC								
		next_event.queue_id = queue_id

		host_cmd = self.host_cmd_queue[queue_id].get_host_cmd(self.tx_cid)
		cur_lba = host_cmd.lba + host_cmd.num_sectors_completed
		self.generate_write_data(cur_lba, self.tx_count)

		num_sectors = min(WDATA_PACKET_SIZE, self.tx_count)

		# calcultae transfer time by number of sectors (transfer size)
		num_packets, transfer_time = calculate_xfer_time(num_sectors)										
		
		next_event = event_mgr.alloc_new_event(int(transfer_time))
		next_event.code = event_id.EVENT_WRITE_DATA
		next_event.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
		next_event.queue_id = queue_id
		next_event.host_id = self.tx_cid
		next_event.num_sectors = num_sectors
		
		# set data to transfer
		lba_index = int(cur_lba / SECTORS_PER_CHUNK)
		length = int(num_sectors / SECTORS_PER_CHUNK) 
		for index in range(length) :
			next_event.main_data.append(self.data_table[lba_index])
			lba_index = lba_index + 1			
						
	def continue_or_end_write_transfer(self, event) :
		# log_print('continue or end write transfer : %d, %d, %d'%(self.tx_qid, self.tx_cid, self.tx_count))

		queue_id = self.tx_qid
				
		end_of_transfer = False
		
		num_sectors_sent = event.num_sectors
				
		host_cmd = self.host_cmd_queue[queue_id].get_host_cmd(self.tx_cid)		
		host_cmd.num_sectors_completed = host_cmd.num_sectors_completed + num_sectors_sent
				
		self.tx_count = self.tx_count - num_sectors_sent
		if self.tx_count > 0 :
			num_sectors = min(WDATA_PACKET_SIZE, self.tx_count)

			# calcultae transfer time by number of sectors (transfer size)
			num_packets, transfer_time = calculate_xfer_time(num_sectors)										
		
			next_event = event_mgr.alloc_new_event(int(transfer_time))
			next_event.code = event_id.EVENT_WRITE_DATA
			next_event.dest = event_dst.MODEL_HOST | event_dst.MODEL_HIC
			next_event.queue_id = queue_id
			next_event.host_id = self.tx_cid
			next_event.num_sectors = num_sectors

			# set data to transfer
			cur_lba = host_cmd.lba + host_cmd.num_sectors_completed		
			lba_index = int(cur_lba / SECTORS_PER_CHUNK)
			length = int(num_sectors / SECTORS_PER_CHUNK) 
			for index in range(length) :
				next_event.main_data.append(self.data_table[lba_index])
				lba_index = lba_index + 1			
						
			end_of_transfer = False
		else :
			end_of_transfer = True
			
			self.tx_qid = 0xFFFFFFFF
			self.tx_cid = 0xFFFFFFFF		
				
		# update statistics
		self.host_stat.perf[queue_id].update_sum_of_sectors(num_sectors_sent)
		
		return end_of_transfer
		
	def end_read_transfer(self, event) :
		queue_id = event.queue_id
		cmd_id = event.host_id

		host_cmd = self.host_cmd_queue[queue_id].get_host_cmd(cmd_id)
		
		num_sectors = event.num_sectors
		
		# calculated lba of transferred read data
		lba_index = int(event.host_lba / SECTORS_PER_CHUNK)
		
		# verify read data
		if ENABLE_RAMDISK_MODE == False :
			data = event.main_data.pop(0)
			
			if self.data_table[lba_index] != data : 
				print('..................................................error : verify data : lba %d : expect[%d] return[%d]'%(event.host_lba, self.data_table[lba_index], data))
				#input()
					
		# update completed sectors
		host_cmd.num_sectors_completed = host_cmd.num_sectors_completed + num_sectors

		# update statistics
		self.host_stat.perf[queue_id].update_sum_of_sectors(num_sectors)
								
		#log_print('end read transfer : %d'%(cmd_id))
		
	def check_cmd_time_out(self) :
		log_print('check command time out')
		
	def get_pending_cmd_num(self) :
		return self.num_pending_cmds	
		
	def event_handler(self, event) :
		# log_print('event_handler : '  + event_mgr.debug_info(event.code))
						
		current_uplink_state = self.uplink_state
		next_uplink_state = current_uplink_state
		
		current_downlink_state = self.downlink_state
		next_downlink_state = current_downlink_state		
				
		if event.code == event_id.EVENT_COMMAND_END :
			next_downlink_state = DOWNLINK_IDLE
				
		elif event.code == event_id.EVENT_READ_DATA_START or event.code == event_id.EVENT_REQ_DATA_START :
			if event.code == event_id.EVENT_REQ_DATA_START :
				next_uplink_state = UPLINK_DREQ
			else :
				next_uplink_state = UPLINK_DATA
				
		elif event.code == event_id.EVENT_READ_DATA_END :
			next_uplink_state = UPLINK_IDLE
			self.end_read_transfer(event)
			
		elif event.code == event_id.EVENT_REQ_DATA_END :
			next_uplink_state = UPLINK_IDLE
			
			# get argument from event and save to host context
			self.tx_qid = event.queue_id
			self.tx_cid = event.host_id
			self.tx_count = event.num_sectors 
			#self.current_write_slot_id = event.buf_slot_id
			 		 		
		elif event.code == event_id.EVENT_WRITE_DATA :
			if self.continue_or_end_write_transfer(event) == True :
				next_downlink_state = DOWNLINK_IDLE
				
		elif event.code == event_id.EVENT_COMPLETION :
			self.command_done(event)
			
		elif event.code == event_id.EVENT_SSD_READY :
			log_print('\nstart workload')
			# show workload information and initialize
			
		#elif event.code == event_id.EVENT_TICK :
			
		#elif event.code == event_id.EVENT_WRITE_CLIFF :
		
		try_to_send_something = False
		if next_downlink_state == DOWNLINK_IDLE :
			try_to_send_something = True
			
		if try_to_send_something == True :
			if self.tx_cid != 0xFFFFFFFF :
				# send data
				self.start_write_transfer()
				next_downlink_state = DOWNLINK_DATA
			else :
				# generate and send command by the workload type
				queue_id, cmd, ret_val = self.generate_command()
				
				if ret_val == True :
					self.send_command(queue_id, cmd)
					next_downlink_state = DOWNLINK_CMD	
	
		self.uplink_state = next_uplink_state
		self.downlink_state = next_downlink_state
		
		# update statistics
		host_stat = self.host_stat
		current_time = event_mgr.get_current_time()
		if current_uplink_state != UPLINK_IDLE and next_uplink_state == UPLINK_IDLE :
			host_stat.uplink_idle_begin = current_time
		elif current_uplink_state != UPLINK_IDLE and next_uplink_state != UPLINK_IDLE :
			host_stat.uplink_idle_time = host_stat.uplink_idle_time + (current_time - host_stat.uplink_idle_begin)
																	
		if current_downlink_state != DOWNLINK_IDLE and next_downlink_state == DOWNLINK_IDLE :
			host_stat.downlink_idle_begin = current_time
		elif current_downlink_state != DOWNLINK_IDLE and next_downlink_state != DOWNLINK_IDLE :
			host_stat.downlink_idle_time = host_stat.downlink_idle_time + (current_time - host_stat.downlink_idle_begin)
																										
		# save to VCD file if option is activated
										
		return True
		
	def debug(self) :
		print('\nhost command queue')
		for index in range(NUM_HOST_QUEUE) :
			host_cmd_queue = self.host_cmd_queue[index]
			
			print('queue %d - free slot num : %d'%(index, host_cmd_queue.get_num_free_slot()))
		print('link status - uplink : %d, downlink : %d'%(self.uplink_state, self.downlink_state))			
		
	def print_host_data(self, lba, num_sectors) :
		lba_index = int(lba / SECTORS_PER_CHUNK)
		length = int(num_sectors / SECTORS_PER_CHUNK) 
		for index in range(length) :
			log_print('lba %d : %d'%(lba_index *SECTORS_PER_CHUNK, self.data_table[lba_index]))
			lba_index = lba_index + 1																		

class host_stat_param :
	def __init__(self) :
		self.clear()
		
	def clear(self) :
		self.num_cmd = 0
		self.sum_sectors = 0
		
		self.num_read_cmd = 0
		self.num_read_sectors = 0
		self.sum_read_latency = 0
		self.max_read_latency = 0
		self.min_read_latency = 1000000000
		
		self.num_write_cmd = 0
		self.num_write_sectors = 0
		self.sum_write_latency = 0
		self.max_write_latency = 0
		self.min_write_latency = 1000000000

	def update_sum_of_sectors(self, num_sectors) :
		self.sum_sectors = self.sum_sectors + num_sectors

	def update_read(self, num_sectors, latency) :
		self.num_cmd = self.num_cmd + 1
		self.num_read_cmd = self.num_read_cmd + 1
		self.num_read_sectors = self.num_read_sectors + num_sectors
		self.sum_read_latency = self.sum_read_latency + latency
			
		if latency > self.max_read_latency :
			self.max_read_latency = latency
		if latency < self.min_read_latency :
			self.min_read_latency = latency
							
	def update_write(self, num_sectors, latency) :														
		self.num_cmd = self.num_cmd + 1
		self.num_write_cmd = self.num_write_cmd + 1
		self.num_write_sectors = self.num_write_sectors + num_sectors
		self.sum_write_latency = self.sum_write_latency + latency
			
		if latency > self.max_write_latency :
			self.max_write_latency = latency
		if latency < self.min_write_latency :
			self.min_write_latency = latency
																																																					
class host_statistics :
	def __init__(self, queue_num) :
		self.perf = []
		for index in range(queue_num) :
			self.perf.append(host_stat_param())
				
		self.link_stat_clear()
	
	def link_stat_clear(self) :							
		self.uplink_idle_begin = 0
		self.uplink_idle_time = 0
		self.downlink_idle_begin = 0
		self.downlink_idle_time = 0					
	
	def clear(self) :
		for index in range(len(self.perf)) :
			self.perf[index].clear()
		
		self.link_stat_clear()														

	def show_performance(self, time, report = None) :
		print('\nperformance')
		
		# time is ns
		time_seconds = time / 1000000000
				
		host_stat_name = {'performance' : ['read throughput [MB/s]', 'read iops [kiops]', 'write throughput [MB/s]', 'write iops [kiops]']}				
						
		host_stat_pd = pd.DataFrame(host_stat_name)				
		
		for index, perf_param in enumerate(self.perf) :									
			host_stat_columns = []
																								
			if time_seconds > 0 :	
				read_throughput = (perf_param.num_read_sectors * BYTES_PER_SECTOR / (1024*1024)) / time_seconds																				
				write_throughput = (perf_param.num_write_sectors * BYTES_PER_SECTOR / (1024*1024)) / time_seconds
				read_iops = perf_param.num_read_cmd / time_seconds
				write_iops = perf_param.num_write_cmd / time_seconds							
			else :
				read_throughput = 0
				write_throughput = 0
				read_iops = 0
				write_iops = 0

			host_stat_columns.append(read_throughput)
			host_stat_columns.append(read_iops)
			host_stat_columns.append(write_throughput)			
			host_stat_columns.append(write_iops)

			host_stat_pd['queue %d'%(index)] = pd.Series(host_stat_columns, index=host_stat_pd.index)
																																												
		if report == None :																																												
			report_print = print
		else :
			report_print = report
			
		report_print(host_stat_pd)
																																																																																								
	def print(self, time, report = None) :
		print('\nhost statstics')
		
		# time is ns
		time_seconds = time / 1000000000
		
		throughputs = []
		
		host_stat_name = {'name' : ['num_cmd', 'num_read_cmd', 'num_read_sectors', 'read_latency[avg]', 'read_latency[max]', 'read_latency[min]', 
														'num_write_cmd', 'num_write_sectors', 'write_latency[avg]', 'wrtie_latency[max]', 'write_latency[min]']}				
						
		host_stat_pd = pd.DataFrame(host_stat_name)				
		
		for index in range(len(self.perf)) :				
			perf_param = self.perf[index]				
							
			host_stat_columns = []
			host_stat_columns.append(int(perf_param.num_cmd))
			
			# read command statistics
			host_stat_columns.append(int(perf_param.num_read_cmd))
			host_stat_columns.append(int(perf_param.num_read_sectors))
			if perf_param.num_read_cmd > 0 :
				host_stat_columns.append(int(perf_param.sum_read_latency / perf_param.num_read_cmd))
			else :
				host_stat_columns.append(0)
			host_stat_columns.append(int(perf_param.max_read_latency))
			if perf_param.min_read_latency == 1000000000 :
				host_stat_columns.append(0)
			else :
				host_stat_columns.append(int(perf_param.min_read_latency))
			
			# write command statistics
			host_stat_columns.append(int(perf_param.num_write_cmd))
			host_stat_columns.append(int(perf_param.num_write_sectors))
			if perf_param.num_write_cmd > 0 :
				host_stat_columns.append(int(perf_param.sum_write_latency / perf_param.num_write_cmd))
			else :
				host_stat_columns.append(0)
			host_stat_columns.append(int(perf_param.max_write_latency))
			if perf_param.min_write_latency == 1000000000 :
				host_stat_columns.append(0)
			else :
				host_stat_columns.append(int(perf_param.min_write_latency))
																			
			host_stat_pd['queue %d'%(index)] = pd.Series(host_stat_columns, index=host_stat_pd.index)
		
			if time_seconds > 0 :	
				read_throughput = (perf_param.num_read_sectors * BYTES_PER_SECTOR / (1024*1024)) / time_seconds																				
				write_throughput = (perf_param.num_write_sectors * BYTES_PER_SECTOR / (1024*1024)) / time_seconds
				read_iops = perf_param.num_read_cmd / time_seconds
				write_iops = perf_param.num_write_cmd / time_seconds							
			else :
				read_throughput = 0
				write_throughput = 0
				read_iops = 0
				write_iops = 0
	
			throughputs.append([read_iops, read_throughput, write_iops, write_throughput])										
																					
		if report == None :																																												
			report_print = print
		else :
			report_print = report
			
		report_print(host_stat_pd)
		
		'''
		for index, rw_perf in enumerate(throughputs) :
			report_print('\nqueue %d'%(index))
			report_print('read iops : %f, read throughput : %f MB/s'%(rw_perf[0], rw_perf[1]))
			report_print('write iops : %f, write throughput : %f MB/s'%(rw_perf[2], rw_perf[3]))
			
		report_print('\n')
		'''									
																																																																									
if __name__ == '__main__' :
	print ('module host main')			
	
	# host info is defined in pcie_if.py
	# host main module use it temporay
	host_info()								
	
	host_model = host_manager(NUM_HOST_CMD_TABLE)
	
	host_model.generate_write_data(2048, 512)
	host_model.print_host_data(2048,512)
	
	host_model.host_stat.print(0)																				