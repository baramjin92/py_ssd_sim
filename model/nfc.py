#!/usr/bin/python

import os
import sys
import random
import numpy as np
import pandas as pd

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.sim_config import nand_info
from config.ssd_param import *

from model.buffer import *
from model.queue import *
from model.nandcmd import *
from model.nand import *

from sim_event import *

# way definition
# way means each nand die. 
# ssd uses several nand dies. way is basic unit of nand die. 

MWAY_IDLE = 0

# read state variable for nfc
MWAY_R1_WAIT = 1
MWAY_R2_CNA = 2				# CNA means that nfc send command and address for operation
MWAY_R3_SENSE = 3			# SENSE means that nand try to read data from the cell 
MWAY_R4_WAIT = 4
MWAY_R5_XFER = 5				# XFER is transfer data from page buffer of nand to buffer of nfc

# write state variable for nfc
MWAY_W1_WAIT = 6
MWAY_W2_CNA = 7
MWAY_W3_XFER = 8
MWAY_W4_PROG = 9
MWAY_W5_WAIT = 10
MWAY_W6_CHK = 11

# erase state variable for nfc
MWAY_E1_WAIT = 12
MWAY_E2_CNA = 13
MWAY_E3_ERAS = 14
MWAY_E4_WAIT = 15
MWAY_E5_CHK = 16

# set mode state variable for nfc
MWAY_M1_WAIT = 17
MWAY_M2_CNA = 18

def log_print(message) :
	event_log_print('[nfc]', message)

nfc_seq_state = {
	# cell_busy, io_busy, wait
	MWAY_IDLE : (0, 0, 0),
	MWAY_R1_WAIT : (0, 0, 1),
	MWAY_R2_CNA : (0, 1, 0),
	MWAY_R3_SENSE : (1, 0, 0), 
	MWAY_R4_WAIT : (0, 0, 1),
	MWAY_R5_XFER : (0, 1, 0),

	MWAY_W1_WAIT : (0, 0, 1),
	MWAY_W2_CNA : (0, 1, 0),
	MWAY_W3_XFER : (0, 1, 0),
	MWAY_W4_PROG : (1, 0, 0),
	MWAY_W5_WAIT : (0, 0, 1),
	MWAY_W6_CHK : (0, 1, 0),
	
	MWAY_E1_WAIT : (0, 0, 1),
	MWAY_E2_CNA : (0, 1, 0),
	MWAY_E3_ERAS : (1, 0, 0),
	MWAY_E4_WAIT : (0, 0, 1),
	MWAY_E5_CHK : (0, 1, 0),
	
	MWAY_M1_WAIT : (0, 0, 1),
	MWAY_M2_CNA : (0, 1, 0),
}

class way_context :
	def __init__(self) :
		self.state = MWAY_IDLE
		
		# nandcmd index & descriptor (they are required for management cmd operation, it is copied context)
		self.nandcmd_index = 0
		self.nandcmd_desc = nfc_desc()
		self.nandcmd_count = 0

# nand flash controller
class nfc :
	def __init__(self, channel_num, ways_per_channel) :
		way_num = channel_num * ways_per_channel
				
		self.way_num = way_num
		self.way_ctx = []
		self.way_stat = []
		for index in range(way_num) :
			# initialize way state
			self.way_ctx.append(way_context())
			# initialize way statistics	
			self.way_stat.append(way_statistics())
		
		#channel configuration		
		self.channel_num = channel_num																				
		self.channel_owner = []
		self.high_queue = []
		self.low_queue = []
		self.channel_stat = []
		self.debug = []
		for channel in range(channel_num) :
			# initialize channel owner
			self.channel_owner.append(0xFFFFFFFF)
			# initialize request queue for channel
			self.high_queue.append(queue(0))
			self.low_queue.append(queue(0))
			# initialize channel statistics
			self.channel_stat.append(ch_statistics())
			
			self.debug.append(0)
					
		# ac parameter for nand			
		self.nand_t_cna_w = nand_info.nand_t_cna_w 
		self.nand_t_cna_r = nand_info.nand_t_cna_r
		self.nand_t_cna_e = nand_info.nand_t_cna_e
		self.nand_t_chk = nand_info.nand_t_chk
		self.nand_t_xfer = nand_info.nand_t_xfer
					
		# initialize fil2nfc queue
		# each way has a separated queue for transfering command form fil to nfc
		self.fil2nfc_queue = []
		for index in range(way_num) :		
			self.fil2nfc_queue.append(queue(0))
																																		
	def request_channel(self, channel, way, high_priority) :
		"""
		There is two type of queues. one is high prioriy and another is low priority
		
		The channel has several ways. 
		The channel has request queue. queue depth is number of ways per channel
		 
		in order to use channel, we add way number to request queue of channel.
		 
		the grant_channel() funnction will check these queue, and occupy the channel by the way number
		Finally command can send to NAND by the channel
		 
		channel can be calculated by way 
		channel = way % self.channel_num		 
		"""
				
		if high_priority == True :
			#log_print('request high priority - way : %d'%(way))
			self.high_queue[channel].push(way)
		else :
			#log_print('request low priority - way : %d'%(way))
			self.low_queue[channel].push(way)
			
		###if channel == 0 :
		###	print('request channel : %d, %d'%(channel, way))
			
			
	def begin_io(self, way) :
		#log_print('begin io - way : %d'%(way))
		
		old_state = self.way_ctx[way].state
		seq_num = self.way_ctx[way].nandcmd_desc.seq_num
		nand_addr = self.way_ctx[way].nandcmd_desc.nand_addr
		
		if old_state == MWAY_R1_WAIT :
			self.way_ctx[way].state = MWAY_R2_CNA
			
			# alloc next event with time (NAND_T_CNA_R)
			next_event = event_mgr.alloc_new_event(self.nand_t_cna_r)
			next_event.code = event_id.EVENT_NAND_CNA_END
			next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way
			next_event.cmd_code = NAND_CMD_READ
			next_event.nand_addr = nand_addr						# block/page address
			next_event.chunk_num = self.way_ctx[way].nandcmd_desc.chunk_num
			# 'option'(not need)
			# set sequence number for tracing
			next_event.seq_num = seq_num

		elif old_state == MWAY_R4_WAIT :
			self.way_ctx[way].state = MWAY_R5_XFER
			
			# the unit of data transfer from nand is chunk (4K byte)
			
			# allocate buffer_id
			queue_id = self.way_ctx[way].nandcmd_desc.queue_id
			cmd_tag = self.way_ctx[way].nandcmd_desc.cmd_tag
			
			buffer_id, ret_val = bm.get_buffer(BM_READ, queue_id, cmd_tag)
			self.way_ctx[way].nandcmd_desc.buffer_ids.append(buffer_id[0])
			
			# alloc next event with time (NAND_T_XFER)
			next_event = event_mgr.alloc_new_event(self.nand_t_xfer)
			next_event.code = event_id.EVENT_NAND_DOUT_END
			next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way 
			next_event.chunk_offset = self.way_ctx[way].nandcmd_desc.chunk_offset
			next_event.buf_id = buffer_id[0]
			# set sequence number for tracing
			next_event.seq_num = seq_num
			
		elif old_state == MWAY_W1_WAIT :
			self.way_ctx[way].state = MWAY_W2_CNA

			# get buffer_id from HIL 
			#for index in range(self.way_ctx[way].nandcmd_desc.chunk_num) :
			#	log_print('write buffer %d'%(self.way_ctx[way].nandcmd_desc.buffer_ids[index]))
									
			# alloc next event with time (NAND_T_CNA_W)
			next_event = event_mgr.alloc_new_event(self.nand_t_cna_w)
			next_event.code = event_id.EVENT_NAND_CNA_END
			next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way
			next_event.cmd_code = NAND_CMD_PROGRAM
			next_event.nand_addr = nand_addr							# block / page address
			#next_event.buf_id = self.way_ctx[way].nandcmd_desc.buffer_ids[0]
			# set sequence number for tracing
			next_event.seq_num = seq_num
			
		elif old_state == MWAY_W5_WAIT : 
			self.way_ctx[way].state = MWAY_W6_CHK
			
			# alloc next event with time (0)
			next_event = event_mgr.alloc_new_event(0)
			next_event.code = event_id.EVENT_NAND_CHK_BEGIN
			next_event.dest = event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way
			# set sequence number for tracing
			next_event.seq_num = seq_num
		
		elif old_state == MWAY_E4_WAIT :
			self.way_ctx[way].state = MWAY_E5_CHK
			
			# alloc next event with time (0)
			next_event = event_mgr.alloc_new_event(0)
			next_event.code = event_id.EVENT_NAND_CHK_BEGIN
			next_event.dest = event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way
			# set sequence number for tracing
			next_event.seq_num = seq_num
			
		elif old_state == MWAY_E1_WAIT :
			self.way_ctx[way].state = MWAY_E2_CNA
						
			# alloc next event with time (NAND_T_CNA_E)
			next_event = event_mgr.alloc_new_event(self.nand_t_cna_e)
			next_event.code = event_id.EVENT_NAND_CNA_END
			next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way
			next_event.cmd_code = NAND_CMD_ERASE
			next_event.nand_addr = nand_addr							# block address
			# set sequence number for tracing
			next_event.seq_num = seq_num
			
		elif old_state == MWAY_M1_WAIT :
			self.way_ctx[way].state = MWAY_M2_CNA
						
			# alloc next event with time (NAND_T_CNA_E)
			next_event = event_mgr.alloc_new_event(self.nand_t_cna_e)
			next_event.code = event_id.EVENT_NAND_CNA_END
			next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
			# set nand command and argument
			next_event.nand_id = way
			next_event.cmd_code = NAND_CMD_MODE
			next_event.nand_addr = nand_addr							# block address
			# use chunk_num for sending value
			next_event.chunk_num = self.way_ctx[way].nandcmd_desc.option		
			# set sequence number for tracing
			next_event.seq_num = seq_num
								
	def grant_channel(self, channel) :
		#log_print('grant channel')
		
		# get current time
		current_time = event_mgr.get_current_time()
		
		# get queue info from channel (channel has two queues, high priority queue / low priority queue)
		if self.high_queue[channel].length() > 0 : 
			queue  = self.high_queue[channel]
		else :
			queue = self.low_queue[channel]
		
		# get way info from queue, it means which way try to own the channel
		way = queue.pop()
				
		# statistics
		cstat = self.channel_stat[channel]		
		bstat = self.way_stat[way]
				
		# calculate channel idle time
		cstat.idle_time = cstat.idle_time + (current_time - cstat.release_time)
		# calculate way wait time
		bstat.wait_time = bstat.wait_time + (current_time - bstat.prev_time)
		bstat.prev_time = current_time
				
		# register channel owner by way
		self.channel_owner[channel] = way
		
		#if channel == 0 :
		#	print('grant channel %d way %d, idle time %f us'%(channel, way, cstat.idle_time / 1000))
		
		# start io operation
		self.begin_io(way)
		
		#ssd_vcd_set_nfc_busy(channel, 1)
		
		return way
		
	def release_channel(self, channel, way) :
		#log_print('%s : way %d'%(self.__class__.__name__, way))
				
		# check current channel owner and invalidate owner
		if self.channel_owner[channel] == way :
			self.channel_owner[channel] = 0xFFFFFFFF
			
			###if channel == 0 :
			###	print('release channel : %d, %d'%(channel, way))
		#else :
		#	log_print('error : mismatch current channel owner')

		# statistics		
		# get current time
		current_time = event_mgr.get_current_time()
		# set channel release time with current time
		cstat = self.channel_stat[channel]
		cstat.release_time = current_time
		
		#ssd_vcd_set_nfc_busy(channel, 0)
		
	def release_channel_condition(self, channel, way) :
		#log_print('%s'%self.__class__.__name__)

		release = True
		
		if self.fil2nfc_queue[way].length() > 0  :
			# check queue status, if next command is read, it doesn't release channel
			# get next command from FIL queue
			next_command = self.fil2nfc_queue[way].array[0]
		
			if next_command == NFC_CMD_READ :
				release = False 
		
		if release == True :
			self.release_channel(channel, way)
			
	def begin_new_command(self, channel, way) :
		#log_print('begin new command')
		
		# check fil queue by way
		table_index = self.fil2nfc_queue[way].pop()
		
		# save nandcmd index and descriptor (descriptor is a copy of nfc_desc_table)
		self.way_ctx[way].nandcmd_index = table_index
		self.way_ctx[way].nandcmd_desc = nandcmd_table.table[table_index]
		self.way_ctx[way].nandcmd_count = 0
		cmd_code = self.way_ctx[way].nandcmd_desc.code
								
		already_have = False
		
		if cmd_code == NFC_CMD_READ :
			# check channel own state by way
			if self.channel_owner[channel] == way :
				already_have = True
			
			self.way_ctx[way].state = MWAY_R1_WAIT
			priority = True
				
		elif cmd_code == NFC_CMD_WRITE :
			self.way_ctx[way].state = MWAY_W1_WAIT
			priority = False
			
		elif cmd_code == NFC_CMD_ERASE :
			self.way_ctx[way].state = MWAY_E1_WAIT
			priority = False				# True/False after checking operation
			
		elif cmd_code == NFC_CMD_MODE :
			self.way_ctx[way].state = MWAY_M1_WAIT
			priority = False
		
		###if channel == 0 :
		###	print('begin new command : %d, %d'%(channel, way))
								
		# depend on channel own state, call start io operation or request channel grant	
		if already_have == True :
			self.begin_io(way)
		else :
			self.request_channel(channel, way, priority)				
					
	def end_command(self, way, result) :
		#log_print('end command')
		
		# push the result to report queue
		report = report_desc()
		# table_index get form way_context with way number
		report.table_index = self.way_ctx[way].nandcmd_index
		report.result = result
		report_queue.push(report)
	
	def end_command_without_report(self, way) :
		#log_print('end command without report')
		
		nandcmd_table.release_slot(self.way_ctx[way].nandcmd_index)
	
	def event_handler(self, event) :	
		# get current time from time tick
		current_time = event_mgr.get_current_time()
	
		# get way number form event
		way = event.nand_id
		channel = way % self.channel_num
		
		current_state = self.way_ctx[way].state
		bstat = self.way_stat[way]
	
		elapsed_time = current_time - bstat.prev_time
	
		if current_state == MWAY_R2_CNA :
			if event.code == event_id.EVENT_NAND_CNA_END :		
				bstat.io_time = bstat.io_time + elapsed_time
				self.way_ctx[way].state = MWAY_R3_SENSE
				self.release_channel(channel, way)
						
		elif current_state == MWAY_R3_SENSE :
			if event.code == event_id.EVENT_NAND_SENSE_END :		
				bstat.cell_time = bstat.cell_time + elapsed_time
				bstat.read_count = bstat.read_count + 1
				
				self.way_ctx[way].state = MWAY_R4_WAIT
				self.request_channel(channel, way, False)
				
		elif current_state == MWAY_R5_XFER :
			if event.code == event_id.EVENT_NAND_DOUT_END :
				seq_num = self.way_ctx[way].nandcmd_desc.seq_num
				
				#if event.meta_data[0] == 0 and event.main_data[0] == 0 :
				#log_print('..........................................................................offset %d, num %d, meta %d, main %d'%(self.way_ctx[way].nandcmd_desc.chunk_offset, self.way_ctx[way].nandcmd_desc.chunk_num, event.meta_data[0], event.main_data[0]))
	
				# start memory write 
				# we need to consider this api usage
				# in order to simulate performance of memory bandwidth, it should work asynchronous method (event driven)
				
				buffer_id = event.buf_id
				bm.set_data(buffer_id, event.main_data[0], event.meta_data[0])				
				
				# end memory write
				
				self.way_ctx[way].nandcmd_desc.chunk_offset = self.way_ctx[way].nandcmd_desc.chunk_offset + 1
				self.way_ctx[way].nandcmd_count = self.way_ctx[way].nandcmd_count + 1
													
				bstat.io_time = bstat.io_time + elapsed_time
				
				# get current command option by way
	
				# NFC_OPT_AUTO_SEND try to ready event to hic automatically.
				# it improves performance in real controller, because it reduce fw overhead.
				# in this simulation, there is no difference in the performance.
				if NFC_OPT_AUTO_SEND == True :					
					# alloc next event with time (0)
					next_event = event_mgr.alloc_new_event(0)
					next_event.code = event_id.EVENT_USER_DATA_READY
					next_event.dest = event_dst.MODEL_HIC
					next_event.seq_num = seq_num
					
					# add buffer to bm list to send to user
					self.hic_model.tx_buffer_list.append(buffer_id)
		
				# if there is no additional data to transfer (check compare condition later in odd offset)
				if self.way_ctx[way].nandcmd_count >= self.way_ctx[way].nandcmd_desc.chunk_num :
					self.way_ctx[way].state = MWAY_IDLE
					self.release_channel_condition(channel, way)
					self.end_command(way, True)
				else :
					# allocate buffer_id and get data from nand
					queue_id = self.way_ctx[way].nandcmd_desc.queue_id
					cmd_tag = self.way_ctx[way].nandcmd_desc.cmd_tag
					buffer_id, ret_val = bm.get_buffer(BM_READ, queue_id, cmd_tag)										
					self.way_ctx[way].nandcmd_desc.buffer_ids.append(buffer_id[0]) 
										
					# alloc next event with time (NAND_T_XFER)
					next_event = event_mgr.alloc_new_event(self.nand_t_xfer)
					next_event.code = event_id.EVENT_NAND_DOUT_END
					next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
					# set nand command and argument
					next_event.nand_id = way 
					next_event.chunk_offset = self.way_ctx[way].nandcmd_desc.chunk_offset
					next_event.buf_id = buffer_id[0]
					# set sequence number for tracing
					next_event.seq_num = seq_num
																																																											
		elif current_state == MWAY_W2_CNA :
			if event.code == event_id.EVENT_NAND_CNA_END :			
				bstat.io_time = bstat.io_time + elapsed_time
				
				self.way_ctx[way].state = MWAY_W3_XFER
				
				# calculate transfer time by number of chunk (it is changed by single plane/multi plane write)
				chunk_num = self.way_ctx[way].nandcmd_desc.chunk_num
				xfer_time = chunk_num * self.nand_t_xfer
	
				# alloc next event with time (xfer_time)
				next_event = event_mgr.alloc_new_event(xfer_time)
				next_event.code = event_id.EVENT_NAND_DIN_END
				next_event.dest = event_dst.MODEL_NFC | event_dst.MODEL_NAND
				# set nand command and argument	
				next_event.nand_id = way					
				next_event.chunk_num = chunk_num
				
				for index in range(chunk_num) :
					main_data, extra_data = bm.get_data(self.way_ctx[way].nandcmd_desc.buffer_ids[index])
					next_event.main_data.append(main_data)
					next_event.meta_data.append(extra_data)
													
		elif current_state == MWAY_W3_XFER :
			if event.code == event_id.EVENT_NAND_DIN_END :
				bstat.io_time = bstat.io_time + elapsed_time
				
				self.way_ctx[way].state = MWAY_W4_PROG
				self.release_channel(channel, way)
				
		elif current_state == MWAY_W4_PROG :
			if event.code == event_id.EVENT_NAND_PROG_END :						
				bstat.cell_time = bstat.cell_time + elapsed_time
				bstat.write_count = bstat.write_count + 1
				
				###if channel == 0:
				###	print('NAND PROG END %d %d'%(channel, way))
				
				self.way_ctx[way].state  = MWAY_W5_WAIT
				self.request_channel(channel, way, False)
					
		elif current_state == MWAY_W6_CHK or current_state == MWAY_E5_CHK :
			if event.code == event_id.EVENT_NAND_CHK_END :			
				#log_print('debug write end or erase end')
				
				bstat.io_time = bstat.io_time + elapsed_time
				self.way_ctx[way].state = MWAY_IDLE
				
				self.release_channel(channel, way)
				self.end_command(way, True)
				
		elif current_state == MWAY_E2_CNA :
			if event.code == event_id.EVENT_NAND_CNA_END :	
				bstat.io_time = bstat.io_time + elapsed_time
				self.way_ctx[way].state = MWAY_E3_ERAS
				
				self.release_channel(channel, way)
				
		elif current_state == MWAY_E3_ERAS :
			if event.code == event_id.EVENT_NAND_ERASE_END :			
				bstat.cell_time = bstat.cell_time + elapsed_time
				bstat.erase_count = bstat.erase_count + 1
				
				self.way_ctx[way].state = MWAY_E4_WAIT
				
				self.request_channel(channel, way, False)

		elif current_state == MWAY_M2_CNA :
			if event.code == event_id.EVENT_NAND_CNA_END :		
				bstat.io_time = bstat.io_time + elapsed_time
				self.way_ctx[way].state = MWAY_IDLE

				self.release_channel(channel, way)
				self.end_command_without_report(way)
			
		bstat.prev_time = current_time
		
		# check idle state and start another new command
		if self.way_ctx[way].state == MWAY_IDLE and self.fil2nfc_queue[way].length() > 0 :
			#log_print('........................')
			bstat.idle_time = bstat.idle_time + (current_time - bstat.prev_time)
			bstat.prev_time = current_time
			
			self.begin_new_command(channel, way)
		
		'''		
		if self.way_ctx[way].state != current_state :
			cell, io, wait, = nfc_seq_state[self.way_ctx[way].state]
			ssd_vcd_set_nfc_state(way, self.way_ctx[way].state, cell, io, wait)
		'''
		
		# check channel owner and grant channel
		if self.channel_owner[channel] == 0xFFFFFFFF :
			self.debug[channel] = self.debug[channel] +1
			# check high and low queue entries
			if self.high_queue[channel].length() > 0 or self.low_queue[channel].length() >0 :
				#print('....................................................%d'%(self.debug[channel]))
				self.debug[channel] = 0
				granted_way = self.grant_channel(channel)
					
				'''
				cell, io, wait, = nfc_seq_state[self.way_ctx[granted_way].state]
				ssd_vcd_set_nfc_state(granted_way, self.way_ctx[granted_way].state, cell, io, wait)			
				'''
									
	def print_cmd_descriptor(self, report = None) :
		print('command descriptor')

		cmd_desc = nfc_desc()

		desc_name = {'name' : ['queue_id', 'cmd_tag', 'way', 'op_code', 'seq_num', 'nand_addr', 'code', 'option', 'chunk_offset', 'chunk_num', 'buffer_ids']}										
		cmd_desc_pd = pd.DataFrame(desc_name)				
						
		desc_columns = []
		desc_columns.append(cmd_desc.queue_id)
		desc_columns.append(cmd_desc.cmd_tag)
		desc_columns.append(cmd_desc.way)
		desc_columns.append(cmd_desc.op_code)
		desc_columns.append(cmd_desc.seq_num)
		desc_columns.append(cmd_desc.nand_addr)
		desc_columns.append(cmd_desc.code)
		desc_columns.append(cmd_desc.option)
		desc_columns.append(cmd_desc.chunk_offset)
		desc_columns.append(cmd_desc.chunk_num)
		desc_columns.append(cmd_desc.buffer_ids)				
						
		cmd_desc_pd['value'] = pd.Series(desc_columns, index=cmd_desc_pd.index)
		
		if report == None :
			print(cmd_desc_pd)
		else :
			report(cmd_desc_pd)						
												
	def print_ch_statistics(self, report = None) :
		print('channel statistics')

		ch_statistics_name = {'name' : ['idle_time', 'release_time']}
	
		ch_statistics_pd= pd.DataFrame(ch_statistics_name)

		for index in range(self.channel_num) :
			ch_columns = []
			ch_columns.append(self.channel_stat[index].idle_time)
			ch_columns.append(self.channel_stat[index].release_time)
			ch_statistics_pd['ch'+str(index)] = pd.Series(ch_columns, index=ch_statistics_pd.index)

		if report == None :
			print(ch_statistics_pd)
		else :
			report(ch_statistics_pd)
				
	def print_way_statistics(self, report = None) : 
		print('way statistics')
		way_statistics_name = {'name' : ['idle_time', 'wait_time', 'io_time', 'cell_time', 'read_count', 'write_count', 'erase_count']}
	
		way_statistics_pd= pd.DataFrame(way_statistics_name)

		for index in range(self.way_num) :
			way_columns = []
			way_columns.append(self.way_stat[index].idle_time)
			way_columns.append(self.way_stat[index].wait_time)
			way_columns.append(self.way_stat[index].io_time)
			way_columns.append(self.way_stat[index].cell_time)
			way_columns.append(self.way_stat[index].read_count)
			way_columns.append(self.way_stat[index].write_count)
			way_columns.append(self.way_stat[index].erase_count)
			way_statistics_pd['way'+str(index)] = pd.Series(way_columns, index=way_statistics_pd.index)

		if report == None :																								
			print(way_statistics_pd)
		else :
			report(way_statistics_pd)
	
	def clear_statistics(self) :
		for ch_stat in self.channel_stat :
			ch_stat.clear()
		 
		for way_stat in self.way_stat :
			way_stat.clear()
																																																																									
class ch_statistics :
	def __init__(self) :
		self.clear()
				
	def clear(self) :	
		self.idle_time = 0
		self.release_time = 0
				
class way_statistics :
	def __init__(self) :
		self.clear()
		
	def clear(self) :
		self.idle_time = 0		
		self.wait_time = 0
		self.io_time = 0
		self.cell_time = 0
		self.prev_time = 0

		self.read_count = 0
		self.write_count = 0
		self.erase_count = 0
																																																		
if __name__ == '__main__' :
	print ('module nfc(nand flash controller) main')
	
	nfc_model = nfc(NUM_CHANNELS, WAYS_PER_CHANNELS)
				
	print('nand parameter for nfc event')
	print('write command and address time : %d ns'%(nfc_model.nand_t_cna_w))
	print('read command and address time : %d ns'%(nfc_model.nand_t_cna_r))
	print('erase command and address time : %d ns'%(nfc_model.nand_t_cna_e))
	print('check status time  : %d ns'%(nfc_model.nand_t_chk))
	print('data transfer time for chunk : %d ns'%(nfc_model.nand_t_xfer))
										
								