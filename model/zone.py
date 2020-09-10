#!/usr/bin/python

import os
import sys
import random

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

def log_print(message) :
	print('[host zone] ' + message)

ZONE_STATE_EMPTY = 0
ZONE_STATE_OPEN = 1
ZONE_STATE_FULL = 2
ZONE_STATE_WAIT = 3
ZONE_STATE_CLOSE = 4

class zone_desc :
	def __init__(self, no, slba, elba) :
		self.no = no
		self.slba = slba
		self.elba = elba
		self.write_pointer = 0
		self.state = ZONE_STATE_EMPTY
		
		self.issue_cmds = 0
					
	def set_state(self, state) :
		self.state = state	
		
	def reset(self) :
		self.write_pointer = 0
		self.issue_cmds = 0
		
	def update(self, sectors) :
		self.write_pointer = self.write_pointer + sectors
		
		if self.slba + self.write_pointer >= self.elba :
			self.state = ZONE_STATE_FULL
					
class zone :
	def __init__(self, zone_size, num_zones) :
		self.zones = []
		self.empty_zones = []
		self.open_zones = []
		self.close_zones = []
		
		for index in range(num_zones) :
			slba = int(index * zone_size / BYTES_PER_SECTOR)
			elba = int((index + 1) * zone_size / BYTES_PER_SECTOR) - 1
			self.zones.append(zone_desc(index, slba, elba)) 
			self.empty_zones.append(index)	
		
		self.zone_size = zone_size
		self.zone_range = None
		self.max_zone = num_zones - 1 				
											
	def open(self, index) :
		if index in self.empty_zones : 
			self.empty_zones.remove(index)
			self.open_zones.append(index)
			
			zone = self.zones[index]
			
			zone.reset()
			zone.set_state(ZONE_STATE_OPEN)
			
			log_print('open  : %d'%index)
	
	def issue_cmd(self, lba) :
		index = int((lba * BYTES_PER_SECTOR) / self.zone_size)
		
		zone = self.zones[index]
		zone.issue_cmds = zone.issue_cmds + 1
	
	def done_cmd(self, lba) :
		index = int((lba * BYTES_PER_SECTOR) / self.zone_size)

		zone = self.zones[index]
		zone.issue_cmds = zone.issue_cmds - 1
		
	def close_by_lba(self, lba) :
		index = int((lba * BYTES_PER_SECTOR) / self.zone_size)
		
		zone = self.zones[index]
		if zone.issue_cmds > 0 :
			log_print('zone issued cmd is remained : %d'%zone.issue_cmds)
			zone.set_state(ZONE_STATE_WAIT)
		else :
			self.close(index)
	
	def close(self, index) : 
		if index in self.open_zones :
			self.open_zones.remove(index)
			self.close_zones.append(index)		

			self.zones[index].set_state(ZONE_STATE_CLOSE)
			log_print('close  : %d'%index)
	
	def set_range(self, start_zone, end_zone) :
		self.zone_range = [start_zone, end_zone]						
																			
	def get_open_num(self) :
		return len(self.open_zones)
		
	def get_zone_for_write(self) :
		if len(self.open_zones) < NUM_OPEN_ZONES :
			# open new zone and return it 
			if self.zone_range != None :
				range = self.zone_range
			else :
				range = [0, self.max_zone]
				
			count = range[1] - range[0] + 1
			while count > 0 :
				index = random.choice(self.empty_zones)
									
				if index >= range[0] and index <= range[1] :
						break						
				count  = count - 1
				
			self.open(index)
			
			zone = self.zones[index]
			zone_open_state = 0				# open now			
		else :
			# return opend zone 
			index = random.choice(self.open_zones)
				
			zone = self.zones[index]
			zone_open_state = 1		# run
															
		return zone, zone_open_state

	def get_zone_for_read(self) :
		select_zones = random.randrange(0, 2)
		
		if select_zones == 1 and len(self.close_zones) == 0 :
			select_zones = 0
		
		if select_zones == 0 :
			# get zone info from open zone
			open_index = random.randrange(0, len(self.open_zones))
			index = self.open_zones[open_index]
		elif select_zones  == 1 :
			# get zone info from close zone
			close_index = random.randrange(0, len(self.close_zones))
			index = self.close_zones[close_index]
	
		return self.zones[index]		
	
	def print_open_zone(self) :
		print('\nopen zones')
		for index in self.open_zones :
			zone = self.zones[index]
			print('zone %d, slba : %d, elba : %d, write point : %d'%(index, zone.slba, zone.elba, zone.write_pointer))																															

workload_zone = zone(ZONE_SIZE, NUM_ZONES)
																																											
if __name__ == '__main__' :
	print ('module zone main')			
	
	zn = zone(ZONE_SIZE, NUM_ZONES)
	
	for index in range(100) :
		zone, zone_state = zn.get_zone_for_write()
		
		sectors = random.randrange(1, 32)
		zone.update(sectors)
		
		if zone.state == ZONE_STATE_FULL :
			zn.close(zone.no)
		
	zn.print_open_zone()
	
	for index in range(2) :
		zone, zone_state = zn.get_zone_for_write()
		
		sectors = ZONE_SIZE / BYTES_PER_SECTOR - zone.write_pointer
		zone.update(sectors)
		
		if zone.state == ZONE_STATE_FULL :
			zn.close(zone.no)
		
	zn.print_open_zone()		
		
																			