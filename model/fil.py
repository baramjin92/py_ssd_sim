#!/usr/bin/python

import os
import sys
import time

import random

import tabulate

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.buffer import *
from model.queue import *
from model.nandcmd import *
from model.ftl_common import *

from sim_event import *
from sim_system import *
from sim_eval import *

def log_print(message) :
	event_log_print('[fil]', message)
																								
class fil_manager :
	def __init__(self) :
		self.fil_stat = fil_statistics()											
																																	
	def send_command_to_nfc(self) :
		nfc = get_ctrl('nfc')
		
		# check ftl2fil queue 
		while ftl2fil_queue.length() > 0 :
			#log_print('send command')
			
			table_index = ftl2fil_queue.pop()
			
			cmd_desc = nandcmd_table.table[table_index]
			
			# depending FOP command, we set the code of nfc
			if cmd_desc.op_code == FOP_USER_READ :
				#log_print('FOP_USER_READ - way : %d, addr : %x'%(cmd_desc.way, cmd_desc.nand_addr))
				cmd_desc.code = NFC_CMD_READ
				cmd_desc.option = NFC_OPT_AUTO_SEND
				
			elif cmd_desc.op_code == FOP_GC_READ :
				#log_print('FOP_GC_READ')
				cmd_desc.code = NFC_CMD_READ
				
			elif cmd_desc.op_code == FOP_USER_WRITE or cmd_desc.op_code == FOP_GC_WRITE :
				#log_print('FOP_USER_WRITE or FOP_GC_WRITE')
				cmd_desc.code = NFC_CMD_WRITE
				
			elif cmd_desc.op_code == FOP_ERASE :
				#log_print('FOP_ERASE')
				cmd_desc.code = NFC_CMD_ERASE
			
			elif cmd_desc.op_code == FOP_SET_MODE :
				#log_print('FOP_SET_MODE')
				cmd_desc.code = NFC_CMD_MODE	
						
			# send table_index via fil2nfc queue 
			way = cmd_desc.way
			nfc.fil2nfc_queue[way].push(table_index)
			
			# send new event to nfc if lengh of fil2nfc queue is 1
			if nfc.fil2nfc_queue[way].length() >= 1 :
				# this code make undefined event to NFC, it should be change later
				next_event = event_mgr.alloc_new_event(1)
				next_event.dest = event_dst.MODEL_NFC
				next_event.nand_id = way
				
	def handle_completed_nand_ops(self) :
		hic = get_ctrl('hic')
		# get information from report queue by nfc		
		while report_queue.length() > 0 :
			#log_print('handle completed nand ops')
			
			report = report_queue.pop()
			
			cmd_desc = nandcmd_table.table[report.table_index]
			if cmd_desc.op_code == FOP_USER_READ :
				#log_print('FOP_USER_READ')
						
				# NFC_OPT_AUTO_SEND is defined in nandcmd.py	
				# check NFC_OPT_AUTO_SEND option and send new event to hic if it is False
				# it means hic doesn't support auto sending response from nfc to hic
				# it affects the performance in real hardware, however this simulator has no difference so far.
				if NFC_OPT_AUTO_SEND == False :
					next_event = event_mgr.alloc_new_event(0)
					next_event.code = event_id.EVENT_USER_DATA_READY
					next_event.dest = event_dst.MODEL_HIC
					next_event.seq_num = cmd_desc.seq_num
										
					# add buffer to bm list to send to user
					for buffer_id in cmd_desc.buffer_ids :
						hic.add_tx_buffer(cmd_desc.queue_id, buffer_id)
				
				# update statistics
				self.fil_stat.num_user_read_pages = self.fil_stat.num_user_read_pages + 1
				self.fil_stat.num_user_read_chunks = self.fil_stat.num_user_read_chunks + cmd_desc.chunk_num
				
			elif cmd_desc.op_code == FOP_GC_READ :													
				#log_print('\nFOP_GC_READ - cmd id : %d'%(cmd_desc.cmd_tag))
																
				# send cmd id and buffer ids to ftl
				fil2ftl_queue.push([cmd_desc.queue_id, cmd_desc.cmd_tag, cmd_desc.buffer_ids, cmd_desc.gc_meta])	

				# update statistics
				self.fil_stat.num_gc_read_pages = self.fil_stat.num_gc_read_pages + 1
				self.fil_stat.num_gc_read_chunks = self.fil_stat.num_gc_read_chunks + cmd_desc.chunk_num			
			elif cmd_desc.op_code == FOP_USER_WRITE :
				#log_print('FOP_USER_WRITE : release write buffer')				
				
				# release buffer because write is done.
				# 1. hil : get buffer id
				# 2. hic : rx_buffer_prep -> rx_buffer_req -> rx_buffer_done
				# 3. ftl : move to buffer_ids of nand_cmd_table by do_write()
				# 4. fil : release buffer id by handle_completed_nand_ops()
				for buffer_id in cmd_desc.buffer_ids :
					bm.release_buffer(buffer_id)
				
				# update statistics
				self.fil_stat.num_user_written_pages = self.fil_stat.num_user_written_pages + 1
				self.fil_stat.num_user_written_chunks = self.fil_stat.num_user_written_chunks + cmd_desc.chunk_num
			
			elif cmd_desc.op_code == FOP_GC_WRITE :
				#log_print('FOP_GC_WRITE : release write buffer')
				
				# release buffer because write is done
				for buffer_id in cmd_desc.buffer_ids :
					bm.release_buffer(buffer_id)

				# update statistics
				self.fil_stat.num_gc_written_pages = self.fil_stat.num_gc_written_pages + 1
				self.fil_stat.num_gc_written_chunks = self.fil_stat.num_gc_written_chunks + cmd_desc.chunk_num
																
			elif cmd_desc.op_code == FOP_ERASE :
				#log_print('FOP_ERASE')
				
				# update statistics
				self.fil_stat.num_erased_blocks = self.fil_stat.num_erased_blocks + 1
		
			nandcmd_table.release_slot(report.table_index)		 																																																
		return True		
		
	@measure_fil_time	
	def handler(self) :
		self.send_command_to_nfc()
		self.handle_completed_nand_ops()																																			
																										
class fil_statistics :
	def __init__(self) :
		self.num_user_read_pages = 0
		self.num_user_read_chunks = 0
		
		self.num_user_written_pages = 0
		self.num_user_written_chunks = 0

		self.num_gc_read_pages = 0
		self.num_gc_read_chunks = 0
		
		self.num_gc_written_pages = 0
		self.num_gc_written_chunks = 0
								
		self.num_erased_blocks = 0

	def print(self) :
		print('fil statstics')
																																							
		fil_stat = []
		fil_stat.append(['num_user_read_pages', self.num_user_read_pages])
		fil_stat.append(['num_user_read_chunks', self.num_user_read_chunks])
		fil_stat.append(['num_user_written_pages', self.num_user_written_pages])
		fil_stat.append(['num_user_written_chunks', self.num_user_written_chunks])

		fil_stat.append(['num_gc_read_pages', self.num_gc_read_pages])
		fil_stat.append(['num_gc_read_chunks', self.num_gc_read_chunks])
		fil_stat.append(['num_gc_written_pages', self.num_gc_written_pages])
		fil_stat.append(['num_gc_written_chunks', self.num_gc_written_chunks])

		fil_stat.append(['num_erased_blocks', self.num_erased_blocks])
																						
		print(tabulate.tabulate(fil_stat))						
																																																						
if __name__ == '__main__' :
	print ('module fil')
	
	fil = fil_manager()
	
	fil.fil_stat.print()
	
	queue_id = 2000
	cmd_id = 1
	buffer_ids = [1, 2]
	fil2ftl_queue.push([queue_id, cmd_id, buffer_ids])
	
	queue_id, cmd_id, buffer_ids = fil2ftl_queue.pop()
	
	print('\n\nqueue : %d, cmd : %d, buffer : %s'%(queue_id, cmd_id, str(buffer_ids)))																			