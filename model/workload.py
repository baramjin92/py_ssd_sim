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

from sim_event import event_mgr
from sim_event import event_dst
from sim_event import event_id

from model.zone import *

WL_SEQ_READ = 0
WL_SEQ_WRITE = 1
WL_RAND_READ = 2
WL_RAND_WRITE = 3
WL_RAND_RW = 4
#WL_JEDEC_ENTERPRISE = 5
#WL_JEDEC_CLIENT = 6
WL_ZNS_WRITE = 7

WL_SIZE_MB = 1
WL_SIZE_GB = 2
WL_SIZE_SEC = 3
WL_SIZE_COND = 4
WL_SIZE_FOREVET = 5

range_4MB = 4 * unit.scale_MiB / BYTES_PER_SECTOR
range_16MB = 16 * unit.scale_MiB / BYTES_PER_SECTOR
range_64MB = 64 * unit.scale_MiB / BYTES_PER_SECTOR
range_256MB = 256 * unit.scale_MiB / BYTES_PER_SECTOR
range_1GB = 1 * unit.scale_GiB / BYTES_PER_SECTOR
range_16GB = 16 * unit.scale_GiB / BYTES_PER_SECTOR

def log_print(message) :
	print('[workload] ' + message)
	
class workload :
	def __init__(self, type, lba, range, kb_min, kb_max, amount, amount_type, read_ratio, align, gc = False) :
		
		self.workload_type = type
		# starting LBA of test range
		self.lba_base = lba				
		# size of test range	
		self.range = range
		# minimum size of command					
		self.kb_min = kb_min
		# maximum size of command in conventional ssd or size of zone in zns 			
		self.kb_max = kb_max
		# ratio of read/write commands			
		self.read_ratio = read_ratio
		# align at 4KB boundary	
		self.align = align
		# force gc operation or number of zone 
		self.gc = gc

		# total size of command
		self.amount = amount
		self.amount_type = amount_type				

		if amount_type == WL_SIZE_MB :
			self.amount_size = amount * unit.scale_MiB / unit.scale_KiB
			self.amount_time = 0
		elif amount_type == WL_SIZE_GB :
			self.amount_size = amount * unit.scale_GiB / unit.scale_KiB
			self.amount_time = 0
		elif amount_type == WL_SIZE_SEC :
			self.amount_size = 0
			self.amount_time = amount		
																		
		self.cur_code = 0
		self.cur_lba = self.lba_base
		self.sectors_min = self.kb_min * unit.scale_KiB / BYTES_PER_SECTOR
		self.sectors_max = self.kb_max * unit.scale_KiB / BYTES_PER_SECTOR
		self.cur_amount_count = 0												
		
		self.run_time = 0
		self.previous_time = 0
		
		self.progress_size = 0
		self.progress_time = 0
		self.progress = 0		
		self.workload_done = False
	
		if type == WL_ZNS_WRITE :
			self.zone_start = int((self.lba_base * BYTES_PER_SECTOR) / ZONE_SIZE)
			self.zone_end = int(((self.lba_base + self.range) * BYTES_PER_SECTOR - 1) / ZONE_SIZE)

			self.zn = zone(ZONE_SIZE, NUM_ZONES)
			self.zn.set_range(self.zone_start, self.zone_end)
				
	def check_workload_done(self, submit_time) :
		# check end of workload by size 
		if self.amount_type == WL_SIZE_MB or self.amount_type == WL_SIZE_GB :
			self.progress = int(self.cur_amount_count / self.amount_size * 100) 
			#print('%d %d %d'%(self.cur_amount_count, self.amount_size, self.progress_size))
			if self.cur_amount_count >= self.amount_size :
		 		self.progress = 99
		 		self.workload_done = True
		 	
		 # check end of workload by time
		elapsed_time = submit_time - self.previous_time
		self.previous_Time = submit_time
		 		 
		self.run_time = self.run_time + elapsed_time
		if self.amount_type == WL_SIZE_SEC :
			self.progress = int(self.run_time / self.amount_time * 100)				
			if self.run_time >= self.amount_time :
				self.progress_time = 100
				self.workload_done = True	

		if self.progress >= 99 :
			self.progress = 99
	
	def is_run(self) :
		return not(self.workload_done)

	def get_progress(self) :
		return self.progress
																																				
	def generate_seq_workload(self, submit_time) : 		
		lba = self.cur_lba
		sectors = self.sectors_min
		 
		# increase lba for next generation
		self.cur_lba = self.cur_lba + sectors
		if self.cur_lba >= self.range :
			self.cur_lba = self.lba_base
		
		# increase total size of workload (unit is kb)
		self.cur_amount_count = self.cur_amount_count + self.kb_min

		# check workload done
		self.check_workload_done(submit_time)		 	
				 					 					 			 
		return lba, sectors
				
	def generate_rnd_workload(self, submit_time) :		
		# get lba
		if self.align == True :
			end = self.range - SECTORS_PER_CHUNK
			lba = random.randrange(0, end, SECTORS_PER_CHUNK)
		else :
			end = self.range - 1
			lba = random.randrange(0, end)
		
		if lba + self.sectors_min >= self.range :
			lba = self.range - self.sectors_min
				
		lba = lba + self.lba_base
		# check align
		
		sectors = self.sectors_min
		 		
		# increase total size of workload (unit is kb)
		self.cur_amount_count = self.cur_amount_count + self.kb_min
		
		# check workload done
		self.check_workload_done(submit_time)		 	
		 			 
		return lba, sectors

	def generate_zns_workload(self, submit_time) : 		
		zone_no, zone, is_open = self.zn.get_zone()	
	
		# check explicit open
		if is_open == True :
			is_explicit = random.randrange(0, 2)
			if is_explicit == 1 :
				return zone.slba, 0
				
		# do implicit open or main operation		
		lba = zone.slba + zone.write_pointer
		sectors = self.sectors_min
		 
		# increase write_pointer for next generation
		if zone.update(sectors) == True : 
			print('zone close')
			zn.close(zone_no)		
		
		# increase total size of workload (unit is kb)
		self.cur_amount_count = self.cur_amount_count + self.kb_min

		# check workload done
		self.check_workload_done(submit_time)		 	
				 					 					 			 
		return lba, sectors
		
	def generate(self, submit_time) : 
		if self.workload_type == WL_SEQ_READ :
			lba, sectors = self.generate_seq_workload(submit_time)
			return HOST_CMD_READ, lba, sectors
		elif self.workload_type == WL_SEQ_WRITE : 
			lba, sectors = self.generate_seq_workload(submit_time)
			return HOST_CMD_WRITE, lba, sectors
		if self.workload_type == WL_RAND_READ :
			lba, sectors = self.generate_rnd_workload(submit_time)
			return HOST_CMD_READ, lba, sectors
		elif self.workload_type == WL_RAND_WRITE : 
			lba, sectors = self.generate_rnd_workload(submit_time)
			return HOST_CMD_WRITE, lba, sectors
		elif self.workload_type == WL_ZNS_WRITE : 
			lba, sectors = self.generate_zns_workload(submit_time)
			
			if sectors == 0 :
				return HOST_CMD_ZONE_SEND, lba, HOST_ZSA_OPEN
			else :	
				return HOST_CMD_WRITE, lba, sectors												
		else :
			print('it will be implemented later')
			return HOST_CMD_READ, 0, 0				
			
class workload_group() :
	def __init__(self) :
		self.wl = []
		self.index = 0

class workload_manager() :
	def __init__(self, capacity = 0) : 
		self.ssd_capacity = capacity
		self.group = []
		self.group.append(workload_group())
		self.group_active = 1			# default group 0 is always active
								
	def set_capacity(self, capacity) :	
		self.ssd_capacity = capacity
		
	def add_group(self, group_num = 1) :
		for index in range(group_num) :
			self.group.append(workload_group())				
	
	def set_group_active(self, group_num) :
		if group_num >= 1 :
			self.group_active = group_num
		else :
			self.group_active = 1		# default group 0 is always active 		
							
	def get_group_num(self) :
		return len(self.group)							
																		
	def set_workload(self, wl, group_id = 0) :
		if group_id >= len(self.group) :
			group_id = len(self.group) - 1
		
		wl_group = self.group[group_id]
		wl_group.wl.append(wl)
			
	def goto_next_workload(self, group_id = 0, async_group = True) :
		if async_group == False and self.group_active > 1:
			ret_val = False
			for group_id in range(self.group_active) :
				wl_group = self.group[group_id]
								
				if wl_group.index < len(wl_group.wl) - 1 :
					wl_group.index = wl_group.index + 1	
					ret_val = True
					
			return ret_val
		else :
			wl_group = self.group[group_id]
						
			if wl_group.index < len(wl_group.wl) - 1 :
				wl_group.index = wl_group.index + 1
				return True
			else :
				return False
											
	def generate_workload(self, submit_time, group_id = 0) :
		wl_group = self.group[group_id]
		workload = wl_group.wl[wl_group.index]
				
		if workload.workload_done == False :
			return workload.generate(submit_time)
		else :
			return HOST_CMD_IDLE, 0, 0

	def get_info(self) :
		workload_index = []
		workload_num = []
		for group_id in range(self.group_active) :
			wl_group = self.group[group_id]
			workload_index.append(wl_group.index)
			workload_num.append(len(wl_group.wl))

		return max(workload_index), max(workload_num)

	def get_force_gc(self) :
		for group_id in range(self.group_active) :
			wl_group = self.group[group_id]
			workload = wl_group.wl[wl_group.index]
			if workload.gc == True :
				return True			

		return False										
																																
	def get_progress(self, group_id = 0, async_group = True) :
		if async_group == False and self.group_active > 1:
			progress = []
			for group_id in range(self.group_active) :
				wl_group = self.group[group_id]
				workload = wl_group.wl[wl_group.index]
								
				if workload.is_run() == True :
					progress.append(workload.get_progress())
					
			if len(progress) > 0 :
				return min(progress)
			else :
				return 99
		else :
			wl_group = self.group[group_id]
			workload = wl_group.wl[wl_group.index]								
			
			return workload.get_progress()

	def print_current(self, wl_index, report = None) :
		wl_type = {
			WL_SEQ_READ : 'Sequential Read',
			WL_SEQ_WRITE : 'Sequential Write',
			WL_RAND_READ : 'Random Read',
			WL_RAND_WRITE : 'Random Write',
			WL_RAND_RW : 'Random Mixed',
			#WL_JEDEC_ENTERPRISE : 'Jedec enterprise',
			#WL_JEDEC_CLIENT : 'Jedec client',
			WL_ZNS_WRITE : 'ZNS Write'
		}		
		
		amount_type = {
			WL_SIZE_MB : 'MB',
			WL_SIZE_GB : 'GB',
			WL_SIZE_SEC : 'sec',
			WL_SIZE_COND : 'continuous',
			WL_SIZE_FOREVET : 'forever'
		}
		
		if report == None :
			report_print = print
		else :
			report_print = report
		
		wl_name = {'name' : ['type', 'start lba', 'range', 'min kb', 'max kb', 'total size', 'unit', 'read ratio', 'align', 'force gc']}								
		wl_name_zone = {'name' : ['type', 'start zone', 'end zone', 'min kb', 'max kb', 'total size', 'unit', 'read ratio', 'align', 'force gc']}

		# only check first group
		if self.group[0].wl[wl_index].workload_type != WL_ZNS_WRITE :
			wl_pd = pd.DataFrame(wl_name)				
		else :
			wl_pd = pd.DataFrame(wl_name_zone)
			
		for group_id, wl_group in enumerate(self.group) :																																		
		
			grp_workloads = wl_group.wl
			
			if wl_index >= len(grp_workloads) :
				continue							

			workload = grp_workloads[wl_index]
					
			wl_columns = []
			wl_columns.append(wl_type[workload.workload_type])
			if workload.workload_type != WL_ZNS_WRITE :
				wl_columns.append(workload.lba_base)
				wl_columns.append(int(workload.range))
			else :
				wl_columns.append(workload.zone_start)
				wl_columns.append(workload.zone_end)				
			wl_columns.append(workload.kb_min)
			wl_columns.append(workload.kb_max)
			wl_columns.append(workload.amount)
			wl_columns.append(amount_type[workload.amount_type])
			wl_columns.append(workload.read_ratio)
			wl_columns.append(workload.align)
			wl_columns.append(workload.gc)
																				
			wl_pd['group id(queue) : %d'%(group_id)] = pd.Series(wl_columns, index=wl_pd.index)
				
		report_print(wl_pd)
			
		print('\n\n')					
																			
	def print_all(self, report = None) :
		wl_type = {
			WL_SEQ_READ : 'Sequential Read',
			WL_SEQ_WRITE : 'Sequential Write',
			WL_RAND_READ : 'Random Read',
			WL_RAND_WRITE : 'Random Write',
			WL_RAND_RW : 'Random Mixed',
			#WL_JEDEC_ENTERPRISE : 'Jedec enterprise',
			#WL_JEDEC_CLIENT : 'Jedec client',
			WL_ZNS_WRITE : 'ZNS Write'
		}		
		
		amount_type = {
			WL_SIZE_MB : 'MB',
			WL_SIZE_GB : 'GB',
			WL_SIZE_SEC : 'sec',
			WL_SIZE_COND : 'continuous',
			WL_SIZE_FOREVET : 'forever'
		}
		
		if report == None :
			report_print = print
		else :
			report_print = report
		
		wl_name = {'name' : ['type', 'start lba', 'range', 'min kb', 'max kb', 'total size', 'unit', 'read ratio', 'align', 'force gc']}
		wl_name_zone = {'name' : ['type', 'start zone', 'end zone', 'min kb', 'max kb', 'total size', 'unit', 'read ratio', 'align', 'force gc']}
																
		for group_id, wl_group in enumerate(self.group) :		
			# only check first workload in group
			if wl_group.wl[0].workload_type != WL_ZNS_WRITE :
				wl_pd = pd.DataFrame(wl_name)				
			else :
				wl_pd = pd.DataFrame(wl_name_zone)
								
			grp_workloads = wl_group.wl							
	
			print('\n\nworkload : group %d'%(group_id))
	
			for index, workload in enumerate(grp_workloads) :						
				wl_columns = []
				wl_columns.append(wl_type[workload.workload_type])
				if workload.workload_type != WL_ZNS_WRITE :
					wl_columns.append(workload.lba_base)
					wl_columns.append(int(workload.range))
				else :
					wl_columns.append(workload.zone_start)
					wl_columns.append(workload.zone_end)				
				wl_columns.append(workload.kb_min)
				wl_columns.append(workload.kb_max)
				wl_columns.append(workload.amount)
				wl_columns.append(amount_type[workload.amount_type])
				wl_columns.append(workload.read_ratio)
				wl_columns.append(workload.align)
				wl_columns.append(workload.gc)
																				
				wl_pd['%d'%(index)] = pd.Series(wl_columns, index=wl_pd.index)
				
			report_print(wl_pd)
			
		print('\n\n')					
			
wlm = workload_manager()
																																						
if __name__ == '__main__' :
	log_print ('module workload main')			
	
	wlm.set_capacity(range_16GB)
	wlm.add_group(2)
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, range_16GB, 128, 128, 16, WL_SIZE_GB, 0, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, range_16GB, 128, 128, 16, WL_SIZE_GB, 0, True))
	wlm.set_workload(workload(WL_RAND_WRITE, 0, range_16GB, 4, 4, 60, WL_SIZE_SEC, 0, True), 1)
	wlm.set_workload(workload(WL_RAND_READ, 0, range_16GB, 4, 4, 60, WL_SIZE_SEC, 0, True), 1)
	wlm.set_workload(workload(WL_ZNS_WRITE, 0, range_16GB, 128, 128, 16, WL_SIZE_GB, 0, True), 2)

	wlm.print_all()

	index, total_num = wlm.get_info()
	group = 1
	print('test group %d'%group)
	for loop in range(total_num) :
		print('workload test %d'%loop)
		wlm.print_current(loop)

		for index in range(5) :
			cmd_code, lba, sectors = wlm.generate_workload(index, group)
			print('workload : %d, %d, %d'%(cmd_code, lba, sectors))
			
		wlm.goto_next_workload(group)
		
	group = 2
	print('test group %d'%group)
	for loop in range(20) :
		cmd_code, lba, sectors = wlm.generate_workload(index, group)
		
		if cmd_code == HOST_CMD_ZONE_SEND :
			print('workload : explicit open slba %d'%(lba))	
		else :
			print('workload : %d, %d, %d'%(cmd_code, lba, sectors))
			
																			