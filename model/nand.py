#!/usr/bin/python

import os
import sys
import random

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import *
from config.ssd_param import *

from sim_event import *
from sim_array import *

from progress.bar import Bar

USE_SMALL_MEMORY = True

# define state
NAND_STATE_IDLE = 0
NAND_STATE_SENSE = 1
NAND_STATE_XFER_W = 2
NAND_STATE_PROGRAM = 3
NAND_STATE_ERASE = 4

# define cell status
NAND_STATUS_ERASE = 0x00
NAND_STATUS_PROGRAM = 0x80

def log_print(message) :
	event_log_print('[nand]', message)

nand_cell_mode = [None, NAND_MODE_SLC, NAND_MODE_MLC, NAND_MODE_TLC, NAND_MODE_QLC]

# nand class represent one die of nand
# it manages data with nand_ctx
class nand_context :
	def __init__(self, nand_id, block_num, param) :
		self.nand_id = nand_id

		# nand information (it manages cell of nand)		
		# block = main_block + spare_block (additional block + extended block)
		self.block_num = block_num
		self.bits_per_cell = param.bits_per_cell
		self.page_num = param.page_num
		self.plane_num = param.plane_num
		self.bytes_per_page = int(param.page_size * param.plane_num)
		self.chunks_per_page = int(self.bytes_per_page / BYTES_PER_CHUNK)
		self.chunks_per_blk =  self.chunks_per_page * self.page_num
		self.chunks_per_way = self.chunks_per_blk * self.block_num
				
		# this code will be removed in future
		#if self.chunks_per_page != CHUNKS_PER_PAGE :
		#	print('.....error : self.chunks_per_page is not same with CHUNKS_PER_PAGE')
		
		# nand page buffer information (it manages operation of nand)
		self.state = NAND_STATE_IDLE
		self.nand_addr = 0
		self.nand_block = 0
		self.nand_page = 0
		self.chunk_offset = 0
		self.main_data = []
		self.meta_data = []
		self.chunks_num = 0
	
		# tR calculation will be changed
		self.mean_tR = [0, 0, 0, 0]
		self.mean_tR[NAND_MODE_MLC] = param.nand_t_read_full
		self.mean_tR[NAND_MODE_TLC] = param.nand_t_read_full
		self.mean_tR[NAND_MODE_SLC] = param.nand_t_read_slc
		self.mean_tR[NAND_MODE_QLC] = 120*1000
	
		self.mean_tProg = [0, 0, 0, 0]
		self.mean_tProg[NAND_MODE_MLC] = param.nand_t_prog_avg
		self.mean_tProg[NAND_MODE_TLC] = param.nand_t_prog
		self.mean_tProg[NAND_MODE_SLC] = param.nand_t_prog_slc
		self.mean_tProg[NAND_MODE_QLC] = 3000
		
		self.mean_tBERS = param.nand_t_bers
			
		self.mode = nand_cell_mode[self.bits_per_cell]
		
		self.set_latency_callback(True)
		
		# reserve area for nand
		# cell structure : cell[block][chunk]
		self.cell = make_2d_array(self.block_num, self.chunks_per_blk)
		self.spare = make_2d_array(self.block_num, self.chunks_per_blk)
		self.status = make_1d_array(self.block_num)
		#log_print(self.cell.shape)	

	def set_latency_callback(self, enable) :
		if enable == True :
			self.get_tR = self.calculate_tR
			self.get_tProg = self.calculate_tProg
			self.get_tBERS = self.calculate_tBERS
		else :
			self.get_tR = self.use_no_latency
			self.get_tProg = self.use_no_latency
			self.get_tBERS = self.use_no_latency
			
	def set_rawinfo(self, block, page, main_data = [], meta_data = []) :
		self.nand_block = block 
		self.nand_page = page
		self.chunk_offset = 0
		self.main_data = main_data
		self.meta_data = meta_data
		self.chunks_num = len(main_data)

	def set_rawinfo1(self, addr, main_data = [], meta_data = []) :
		self.set_address(addr) 
		self.main_data = main_data
		self.meta_data = meta_data
		self.chunks_num = len(main_data)
												
	def set_address(self, addr) :
		self.nand_addr = addr

		# nand address is composed by block, page, chunk offset
		# it can be separated by CHUNK_PER_WAY,  CHUNK_PER_BLOCK, CHUNK_PER_PAGE
		# get block and page address of nand
		self.nand_block = int(self.nand_addr / self.chunks_per_blk) 
		self.nand_page = int((self.nand_addr % self.chunks_per_blk) / self.chunks_per_page)
		self.chunk_offset = int((self.nand_addr % self.chunks_per_page))
				
	def get_data(self) :
		return self.main_data

	def read_page(self) :
		nand_block = self.nand_block 
		nand_page = self.nand_page
		chunk_offset = self.chunk_offset
				
		#log_print('die %d read block %x page %d'%(self.nand_id, nand_block, nand_page))
				
		# calculte chunk index in page
		chunk_addr = nand_page * self.chunks_per_page
	
		#for index in range(self.chunks_num) :
		for chunk_index in range(chunk_addr, chunk_addr+self.chunks_per_page) :
			# read data and meta from nand
			# set main data/extra data
			self.main_data.append(self.cell[nand_block][chunk_index])
			self.meta_data.append(self.spare[nand_block][chunk_index])
			
	def program_page(self) :
		nand_block = self.nand_block 
		nand_page = self.nand_page
		chunk_offset = self.chunk_offset
				
		#log_print('die %d program block %x page %s'%(self.nand_id, nand_block, nand_page))

		# check one shot mode
		#if int(self.chunks_num / self.chunks_per_page) > 1 :
		#	print('%s : way : %d, blk %d, page %d, offset %d, num : %d'%(self.__class__.__name__, self.nand_id, nand_block, nand_page, chunk_offset, self.chunks_num))

		self.status[nand_block] = self.status[nand_block] | NAND_STATUS_PROGRAM
										
		# calculte chunk index in page
		chunk_index = nand_page * self.chunks_per_page + chunk_offset
								
		# the data can distinguish with main data and extra data
		# main data means user data to save
		# extra data means data which is saved in spare area, for example meta data or CRC data, it can be generated by FW or HW(Controller)

		# In this simulator, main data is reduced to 4Byte (representative value) in order to saving memory for simulation
		for index in range(self.chunks_num) :			
			# get main data/extra data and save to nand
			self.cell[nand_block][chunk_index] = self.main_data[index]
			self.spare[nand_block][chunk_index] = self.meta_data[index]
			
			# increas chunk address
			chunk_index = chunk_index + 1

			#log_print('main data : %d, meta_data : %d'%(self.main_data[index], self.meta_data[index]))
									  
		return True
								
	def erase_block(self) :
		# get block address of nand
		nand_block = self.nand_block

		#log_print('die %d erase block %x'%(self.nand_id, nand_block)) 
				
		# calculate number of chunks for block
		self.status[nand_block] = 0
			
		# in order to optimize running time, we don't clear cell and spare
		'''
		self.cell[nand_block] = [0 for x in range(self.chunks_per_blk)]
		self.spare[nand_block] = [0 for x in range(self.chunks_per_blk)]
		'''
		
		return True		
		
	def calculate_tR(self) :
		# make tR (mean, max deviation) 
		
		# get mean time by the page num (LSB/MSB in MLC, LSB/CSB/MSB in TLC)
		mean = self.mean_tR[self.mode]
			
		# deviation is 3% from mean
		diviation = mean * 0.03
			
		# generate tR by randomize funtion
		tR = random.randrange(int(mean - diviation), int(mean + diviation))
								
		# unit (ns)
		return tR		
		
	def calculate_tProg(self) :
		# make tPROG (mean, max deviation) 
		
		# get mean time by the page num (LSB/MSB in MLC, LSB/CSB/MSB in TLC)		
		mean = self.mean_tProg[self.mode]				
																
		# deviation is 1% from mean (5% -> 1%)
		diviation = mean * 0.01
			
		# generate tProg by randomize funtion
		tPROG = random.randrange(int(mean - diviation), int(mean + diviation))

		# unit (ns)		
		return tPROG
		
	def calculate_tBERS(self) :
		# so far, we don't distinguish tBERS by mode 
		# it will be changed later

		mode = self.mode		

		# make tBERS (min, max)
		nand_t_bers = self.mean_tBERS
		
		# deviation is 10%
		min = int(nand_t_bers * 0.9)
		max = int(nand_t_bers * 1.1)
		# generate tBER by randomize funtion
		tBERS = random.randrange(min, max) 

		# unit (ns)		
		return tBERS
		
	def use_no_latency(self) :
		return 1	
		
	def set_mode(self, mode) :
		nand_block = self.nand_block
		
		value = self.status[nand_block] & ~0x03
		value = value | mode
		self.status[nand_block] = value
		self.mode = mode		
		
		#log_print('change mode - way : %d, block : %d, mode : %d'%(self.nand_id, nand_block, mode))

	def print_block_data(self, nand_block, start_page, end_page) :

		print('nand data - block : %d, start page : %d, end page : %d'%(nand_block, start_page, end_page))
		unit = 2
		str = ''		
		for nand_page in range(start_page, end_page) :
			# read data from nand
			for chunk in range(self.chunks_per_page) :
				if self.status[nand_block] == 0 :
					nand_data = 0xFFFF
					meta_data = 0xFF					
				else :
					chunk_index  = nand_page * self.chunks_per_page + chunk
					nand_data = self.cell[nand_block][chunk_index]
					meta_data = self.spare[nand_block][chunk_index]
												
				chunk_value = '%04x '%(nand_data)					
				str = str + chunk_value
					
			if nand_page % unit == (unit - 1) :
				print(str)
				str = ''
			else :	
				str = str + '/ '
																													
class nand_manager :
	def __init__(self, nand_num, nand_info) :
		# set nand basic information and ac parameter
		self.nand_info = nand_info
		
		# set nand context
		###bar = Bar('nand init', max=nand_num)
		
		#block_num = nand_info.main_block_num + nand_info.spare_block_num
		block_num = nand_info.main_block_num
		if USE_SMALL_MEMORY == True :
			block_num = int(block_num / 2)
		self.nand_ctx = []
		for index in range(nand_num) :
			self.nand_ctx.append(nand_context(index, block_num, nand_info))
			###bar.index = index
			###bar.next()
			
		print('\nnand init complete')
															
	def get_nand_info(self) :
		return self.nand_info																									
	
	def get_nand_ctx(self, nand_id = 0) :
		return self.nand_ctx[nand_id]
	
	def get_nand_dimension(self, nand_id = 0) :
		nand_ctx = self.nand_ctx[nand_id]
		return (nand_ctx.bits_per_cell, nand_ctx.bytes_per_page, nand_ctx.page_num, nand_ctx.block_num)
			
	def get_chunk_info(self, nand_id = 0) :
		nand_ctx = self.nand_ctx[nand_id]
		return (nand_ctx.chunks_per_page, nand_ctx.chunks_per_blk, nand_ctx.chunks_per_way)												
																																			
	def begin_new_command(self, nand, event) :
		# get nand command and address from event
		nand.set_address(event.nand_addr)
		nand.chunks_num = event.chunk_num
		nand.main_data.clear()
		nand.meta_data.clear()

		nand_cmd = event.cmd_code

		if nand.nand_addr == 0 :
			print('begin new cmd : %d, id : %d, addr : %x, chunks : %d'%(nand_cmd, nand.nand_id, nand.nand_addr, nand.chunks_num))
															
		# check nand cmd 
		if nand_cmd == NAND_CMD_READ:
			nand.state = NAND_STATE_SENSE

			# save option for NAND_CMD_READ

			# calculate tR and alloc next event			
			tR = nand.get_tR()
			next_event = event_mgr.alloc_new_event(tR)
			next_event.code = event_id.EVENT_NAND_SENSE_END
			next_event.dest = event_dst.MODEL_NAND | event_dst.MODEL_NFC
			next_event.nand_id = nand.nand_id								
												
		elif nand_cmd == NAND_CMD_PROGRAM :
			nand.state = NAND_STATE_XFER_W															
																																																
		elif nand_cmd == NAND_CMD_ERASE:
			nand.state = NAND_STATE_ERASE
			
			# calculate tBERS and alloc next event
			tBERS = nand.get_tBERS() 
			next_event = event_mgr.alloc_new_event(tBERS)
			next_event.code = event_id.EVENT_NAND_ERASE_END
			next_event.dest = event_dst.MODEL_NAND | event_dst.MODEL_NFC
			next_event.nand_id = nand.nand_id
			
		elif nand_cmd == NAND_CMD_MODE :
			nand.set_mode(int(event.chunk_num))								
												
	def event_handler(self, event) :
		# print('[nand_event_handler] %d' %(event.code))
		
		# from event, get nand_id and nand context
		nand = self.nand_ctx[event.nand_id]
		
		# from nand context, get current state of nand
		# nand is variable of nand context
		# nand.state is state variable for each nand 
		
		if event.code == event_id.EVENT_NAND_CNA_END :
			self.begin_new_command(nand, event)
					
		elif event.code == event_id.EVENT_NAND_SENSE_END :
			# check current state, it should be NAND_STATE_SENSE
			
			nand.read_page()
			nand.state = NAND_STATE_IDLE
				
		elif event.code == event_id.EVENT_NAND_ERASE_END :
			# check current state, it should be NAND_STATE_ERASE
			
			nand.erase_block()			
			nand.state = NAND_STATE_IDLE		
			
		elif event.code == event_id.EVENT_NAND_PROG_END :
			# check current state, it should be NAND_STATE_PROGRAM
			
			nand.program_page()		
			nand.state = NAND_STATE_IDLE		
			
		elif event.code == event_id.EVENT_NAND_DIN_END :
			# check current state, it should be NAND_STATE_XFER_W

			# move data from event to nand		

			nand.chunks_num = event.chunk_num
			#for index in range(nand.chunks_num) :
			#	nand.main_data.append(event.main_data[index])
			#	nand.meta_data.append(event.meta_data[index])
			nand.main_data = event.main_data
			nand.meta_data = event.meta_data
			
			# todo : option = event.option
			
			nand.state = NAND_STATE_PROGRAM

			# calculate tProg and alloc next event
			tPROG = nand.get_tProg()
			next_event = event_mgr.alloc_new_event(tPROG)
			next_event.code = event_id.EVENT_NAND_PROG_END
			next_event.dest = event_dst.MODEL_NAND | event_dst.MODEL_NFC
			next_event.nand_id = nand.nand_id								
			
		elif event.code == event_id.EVENT_NAND_DOUT_END :
			# check current state, it should be NAND_STATE_IDLE

			chunk_offset = event.chunk_offset
			
			event.main_data.clear()
			event.main_data.append(nand.main_data[chunk_offset])			
			event.meta_data.clear()
			event.meta_data.append(nand.meta_data[chunk_offset])
			
			if nand.meta_data[chunk_offset] == 0 and nand.main_data[chunk_offset] == 0 :
				print('nand id : %d, nand read page - address : %d, chunk_offset : %d, main_data : %d, meta_data : %d'%(nand.nand_id, nand.nand_addr, chunk_offset, nand.main_data[chunk_offset], nand.meta_data[chunk_offset]))
			
		elif event.code == event_id.EVENT_NAND_CHK_BEGIN :						
			# Because nand is idle, it requite to NFC checking nand state 

			# alloc next event with time (NAND_T_CHK)
			next_event = event_mgr.alloc_new_event(self.nand_info.nand_t_chk)
			next_event.code = event_id.EVENT_NAND_CHK_END
			next_event.dest = event_dst.MODEL_NFC
			next_event.nand_id = nand.nand_id								
		
		return True						
																																										
class nand_statistics :
	def __init__(self) :
		print('nand statstics init')
		
	def print(self) :
		print('nand statstics')
																		
def unit_test_nand() :	
	nand_info = nand_config(nand_256gb_g3)	
	nand_mgr = nand_manager(2, nand_info)	
	
	nand_mgr.nand_info.print_type()
	nand_mgr.nand_info.print_param()
	
	print('\n\n')
	nand = nand_mgr.nand_ctx[0]
	
	nand.nand_block = 0
	nand.erase_block()									
	nand.print_block_data(0, 0, 10)			
	
	nand.nand_block = 0 
	nand.nand_page = 0
	nand.chunk_offset = 0
	nand.main_data = [0x10, 0x20, 0x30, 0x40]
	nand.meta_data = [0, 8, 16, 24]
	nand.chunks_num = 4
	nand.program_page()
	
	nand.set_rawinfo(0, 1, [1,2], [16,24])
	nand.program_page()
				
	nand.print_block_data(0, 0, 10)			
	
	nand.nand_block = 0
	nand.erase_block()									
	nand.print_block_data(0, 0, 10)			
																												
if __name__ == '__main__' :
	print ('module nand main')			
			
	unit_test_nand()		
																	