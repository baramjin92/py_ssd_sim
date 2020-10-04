#!/usr/bin/python

import os
import sys
import random
import time

import csv
import re

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from sim_event import *
from sim_log import *

from model.zone import *

ENABLE_ZNS_CMD = True

WL_SEQ_READ = 0
WL_SEQ_WRITE = 1
WL_RAND_READ = 2
WL_RAND_WRITE = 3
WL_RAND_RW = 4
#WL_JEDEC_ENTERPRISE = 5
#WL_JEDEC_CLIENT = 6
WL_ZNS_WRITE = 7
WL_ZNS_READ = 8

WL_TYPE_SIZE = 1
WL_TYPE_TIME = 2
WL_TYPE_COND = 3
WL_TYPE_FOREVER = 4

'''
range_4MB = 4 * unit.scale_MiB
range_16MB = 16 * unit.scale_MiB
range_64MB = 64 * unit.scale_MiB
range_256MB = 256 * unit.scale_MiB
range_1GB = 1 * unit.scale_GiB
range_16GB = 16 * unit.scale_GiB
'''

wl_type_str = {
	WL_SEQ_READ : 'Sequential Read',
	WL_SEQ_WRITE : 'Sequential Write',
	WL_RAND_READ : 'Random Read',
	WL_RAND_WRITE : 'Random Write',
	WL_RAND_RW : 'Random Mixed',
	#WL_JEDEC_ENTERPRISE : 'Jedec enterprise',
	#WL_JEDEC_CLIENT : 'Jedec client',
	WL_ZNS_WRITE : 'ZNS Write',
	WL_ZNS_READ : 'ZNS Read'
}		
		
wl_type_conv = {
	'WL_SEQ_READ' : WL_SEQ_READ,
	'WL_SEQ_WRITE' : WL_SEQ_WRITE,
	'WL_RAND_READ' : WL_RAND_READ,
	'WL_RAND_WRITE' : WL_RAND_WRITE,
	'WL_RAND_RW' : WL_RAND_RW,
	#'WL_JEDEC_ENTERPRISE' : WL_JEDEC_ENTERPRISE,
	#'WL_JEDEC_CLIENT' : WL_JEDEC_CLIENT,
	'WL_ZNS_WRITE' : WL_ZNS_WRITE,
	'WL_ZNS_READ' : WL_ZNS_READ
}		
		
amount_type_str = {
	WL_TYPE_SIZE : 'capacity',
	WL_TYPE_TIME : 'time',
	WL_TYPE_COND : 'continuous',
	WL_TYPE_FOREVER : 'forever'
}

def log_print(message) :
	print('[workload] ' + message)	

size_units = {
	'TB' : 1000*1000*1000*1000,
	'GB' : 1000*1000*1000,
	'MB' : 1000*1000,
	'KB' : 1000,
	'TIB' : 1024*1024*1024*1024,
	'GIB' : 1024*1024*1024,
	'MIB' : 1024*1024,
	'KIB' : 1024,				
}		

time_units = {
	'SEC' : 1,
	'MIN' : 60,
	'HOUR' : 60*60,
}		
									
def convert_size(value_str) :
	value_str = value_str.upper()

	for unit in size_units :	
		if value_str.find(unit) != -1 :
			scale = size_units[unit]
			break 
		
	value = int(re.findall('\d+', value_str)[0])
	value = value * scale
	
	return value 		  			

def convert_time(value_str) :
	value_str = value_str.upper()
	
	scale = 0
	for unit in time_units :	
		if value_str.find(unit) != -1 :
			scale = time_units[unit]
			break 
	
	value = int(re.findall('\d+', value_str)[0])
	value = value * scale
	
	return value 		  			
									
class workload :
	def __init__(self, type, lba, range, kb_min, kb_max, amount, amount_type, read_ratio, align, gc = False) :
		
		self.workload_type = type
		# starting LBA of test range
		self.lba_base = lba				
		# size of test range	
		self.range = convert_size(range) / BYTES_PER_SECTOR 
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

		if amount_type == WL_TYPE_SIZE :
			self.amount_size = int(convert_size(self.amount) / unit.scale_KiB)
			self.amount_time = 0
		elif amount_type == WL_TYPE_TIME :
			self.amount_size = 0
			self.amount_time = convert_time(self.amount)	
																		
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
	
		if type == WL_ZNS_WRITE or type == WL_ZNS_READ :
			self.zone_start = int((self.lba_base * BYTES_PER_SECTOR) / ssd_param.ZONE_SIZE)
			self.zone_end = int(((self.lba_base + self.range) * BYTES_PER_SECTOR - 1) / ssd_param.ZONE_SIZE)

			workload_zone.set_range(self.zone_start, self.zone_end)
				
	def check_workload_done(self, submit_time) :
		# check end of workload by size 
		if self.amount_type == WL_TYPE_SIZE :
			self.progress = int(self.cur_amount_count / self.amount_size * 100) 
			#print('%d %d %d'%(self.cur_amount_count, self.amount_size, self.progress_size))
			if self.cur_amount_count >= self.amount_size :
		 		self.progress = 99
		 		self.workload_done = True
		 	
		# check end of workload by time
		elapsed_time = submit_time - self.previous_time
		self.previous_time = submit_time
		 		 
		self.run_time = self.run_time + elapsed_time
		if self.amount_type == WL_TYPE_TIME :
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

	def generate_zns_write_workload(self, submit_time) : 		
		zone, zone_open_state = workload_zone.get_zone_for_write()	
		
		if ENABLE_ZNS_CMD == True :
			# check explicit open
			if zone_open_state == 0 :
				is_explicit = random.randrange(0, 2)
				if is_explicit == 1 :
					# if we return sector count 0 in the zone workload, it translate with explicit open  
					return zone.slba, 0
			
		if zone.state == ZONE_STATE_OPEN :				
			# do implicit open or main operation		
			lba = zone.slba + zone.write_pointer
			sectors = self.sectors_min
			 
			# increase write_pointer for next generation
			zone.update(sectors) 
			
			# increase total size of workload (unit is kb)
			self.cur_amount_count = self.cur_amount_count + self.kb_min
		elif zone.state == ZONE_STATE_FULL :
			if zone.issue_cmds == 0 and ENABLE_ZNS_CMD == True :
				# if sectors is -1, it translate with ZONE_HSA_CLOSE
				lba = zone.slba
				sectors = -1
			else :
				lba = -1
				sectors = -1
								
		# check workload done
		self.check_workload_done(submit_time)		 	
				 					 					 			 
		return lba, sectors

	def generate_zns_read_workload(self, submit_time) : 		
		zone = workload_zone.get_zone_for_read()	
	
		sectors = self.sectors_min
		if zone.state == ZONE_STATE_CLOSE or zone.state == ZONE_STATE_FULL :
			lba = random.randrange(zone.slba, zone.elba, sectors)
		elif zone.state == ZONE_STATE_OPEN :
			lba = random.randrange(zone.slba, zone.slba+zone.write_pointer, sectors)
												 		
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
			lba, sectors = self.generate_zns_write_workload(submit_time)
			
			if lba == -1 :
				return HOST_CMD_IDLE, 0, 0
			if sectors == 0 :
				return HOST_CMD_ZONE_SEND, lba, HOST_ZSA_OPEN
			elif sectors == -1 :
				return HOST_CMD_ZONE_SEND, lba, HOST_ZSA_CLOSE
			else :	
				return HOST_CMD_WRITE, lba, sectors
		elif self.workload_type == WL_ZNS_READ :
			lba, sectors = self.generate_zns_read_workload(submit_time)
			return HOST_CMD_READ, lba, sectors												
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
		self.reset()
			
	def reset(self) :
		self.group = []
		self.group.append(workload_group())
		self.group_active = 1			# default group 0 is always active
															
	def set_capacity(self, capacity) :	
		self.ssd_capacity = convert_size(capacity)
		
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

	def load_csv(self, filename) :
		fp = open(filename, 'r')
		rows = csv.reader(fp)
				
		wlm.reset()
		for row in rows :
			if row[0].find('#') != 0 :
				group = int(row[0])
				row[1] = row[1].strip()
				type = wl_type_conv[row[1]]
				slba = int(row[2])
				range = row[3]
				min_kb = int(convert_size(row[4]) / unit.scale_KiB)
				max_kb = int(convert_size(row[5]) / unit.scale_KiB)
				total_size = row[6]
				read_ratio = int(re.findall('\d+', row[7])[0])
				row[8] = row[8].strip()
				if row[8].upper() == 'TRUE' :
					align = True
				else :
					align = False
				
				if group >= self.get_group_num() : 
					wlm.add_group(group - self.get_group_num() + 1)
				
				wl = workload(type, slba, range, min_kb, max_kb, total_size, WL_TYPE_SIZE, read_ratio, align, False)
				wlm.set_workload(wl, group)
																																																																																		
		fp.close()
				
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

	def get_label(self, zone = False) :
		if zone == False :
			return ['type', 'start lba', 'range', 'min kb', 'max kb', 'total size', 'unit', 'read ratio', 'align', 'force gc']
		else :							
			return ['type', 'start zone', 'end zone', 'min kb', 'max kb', 'total size', 'unit', 'read ratio', 'align', 'force gc']

	def get_value(self, workload, table) :
			table[0].append(wl_type_str[workload.workload_type])
			if workload.workload_type == WL_ZNS_WRITE or workload.workload_type == WL_ZNS_READ :
				table[1].append(workload.zone_start)
				table[2].append(workload.zone_end)
			else :
				table[1].append(workload.lba_base)
				table[2].append(int(workload.range))								
			table[3].append(workload.kb_min)
			table[4].append(workload.kb_max)
			table[5].append(workload.amount)
			table[6].append(amount_type_str[workload.amount_type])
			table[7].append(workload.read_ratio)
			table[8].append(workload.align)
			table[9].append(workload.gc)
		
	def get_table(self, label) :
		table = []
		for index, name in enumerate(label) :
			table.append([name])
					
		return table																														

	@report_print	 		 		 		 
	def print_current(self, wl_index, report_title = 'workload current') :		
		# only check first group
		type = self.group[0].wl[wl_index].workload_type
		if type == WL_ZNS_WRITE or type == WL_ZNS_READ:
			table = self.get_table(self.get_label(True)) 				
		else :
			table = self.get_table(self.get_label(False))

		row = []
		row.append('group id')				
		for group_id, wl_group in enumerate(self.group) :		
			grp_workloads = wl_group.wl
			
			if wl_index >= len(grp_workloads) :
				continue							

			row.append('group %d'%group_id)
			workload = grp_workloads[wl_index]
			self.get_value(workload, table)

		table.insert(0, row)																																						
		return report_title, table

	@report_print	 		 		 		 		
	def print_group(self, group_id, wl_group, report_title = 'workload group') :
		type = wl_group.wl[0].workload_type
		if type == WL_ZNS_WRITE or type == WL_ZNS_READ:
			table = self.get_table(self.get_label(True))				
		else :
			table = self.get_table(self.get_label(False))
								
		workloads = wl_group.wl								
		for index, workload in enumerate(workloads) :
			self.get_value(workload, table)

		report_title= 'workload group %d'%group_id
		return report_title, table

	def print_all(self, report = None) :		
		if report == None :
			report_print = print
		else :
			report_print = report
																		
		for group_id, wl_group in enumerate(self.group) :		
			# only check first workload in group
			self.print_group(group_id, wl_group)				
						
wlm = workload_manager()

def unit_test() :																																						
	wlm.set_capacity('16GiB')
	wlm.add_group(2)
	wlm.set_workload(workload(WL_SEQ_WRITE, 0, '16GiB', 128, 128, '16GiB', WL_TYPE_SIZE, 0, True))
	wlm.set_workload(workload(WL_SEQ_READ, 0, '16GiB', 128, 128, '16GiB', WL_TYPE_SIZE, 100, True))
	wlm.set_workload(workload(WL_RAND_WRITE, 0, '16GiB', 4, 4, '60sec', WL_TYPE_TIME, 0, True), 1)
	wlm.set_workload(workload(WL_RAND_READ, 0, '16GiB', 4, 4, '60sec', WL_TYPE_TIME, 100, True), 1)
	wlm.set_workload(workload(WL_ZNS_WRITE, 0, '16GiB', 128, 128, '16GiB', WL_TYPE_SIZE, 0, True), 2)
	wlm.set_workload(workload(WL_ZNS_READ, 0, '16GiB', 128, 128, '16GiB', WL_TYPE_SIZE, 100, True), 2)

	wlm.print_all()

	index, total_num = wlm.get_info()
	print('wlm get info - index : %d, total_num : %d'%(index, total_num))
	
	group = 1
	print('\ntest group %d'%group)
	for wl_index in range(total_num) :
		print('workload test %d'%wl_index)
		wlm.print_current(wl_index)

		for index in range(5) :
			cmd_code, lba, sectors = wlm.generate_workload(index, group)
			print('workload : %d, %d, %d'%(cmd_code, lba, sectors))
			
		wlm.goto_next_workload(group)
		
	group = 2
	print('\ntest group %d'%group)
	for wl_index in range(total_num) :
		print('workload test %d'%wl_index)

		for index in range(20) :
			cmd_code, lba, sectors = wlm.generate_workload(index, group)
			
			if cmd_code == HOST_CMD_ZONE_SEND :
				print('workload : explicit open slba %d'%(lba))	
			else :
				print('workload : %d, %d, %d'%(cmd_code, lba, sectors))
				
		wlm.goto_next_workload(group)
																																						
if __name__ == '__main__' :
	print ('module workload main')			

	print(convert_size('4 GiB'))
	print(convert_size('8 MiB'))
	print(convert_size('64 kiB'))

	print(convert_time('4sec'))
	print(convert_time('8 min'))
	print(convert_time('6 hour'))

	start_time = time.time()

	unit_test()	
	
	print('\nrun time : %f'%(time.time()-start_time))
		
	wlm.load_csv('test_workload1.csv')
	wlm.print_all()
																			