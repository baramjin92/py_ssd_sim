#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from sim_log import *

# in order to use host and hic at the same time, host interface param module is separted from host.py
# if we use new interface like sata, sas, ufs, new file will be added for each interface

# Basic Host Interface : SATA Gen3
				
class sata :
	def __init__(self) :
		self.gen = 3
		self.HOST_IF_SPEED = 6 					# Gbps		
		self.DATA_XFER_OVERHEAD = 200	# UI	
		self.WDATA_PACKET_SIZE = 16			# use to calculate minimum packet size 
						
	def cmd_packet_xfer_time(self) :
		transfer_time = 600 / self.HOST_IF_SPEED   # ns
		
		return transfer_time
	
	def rqt_packet_xfer_time(self) :
		transfer_time = 400 / self.HOST_IF_SPEED   # ns
		
		return transfer_time
		
	def calculate_xfer_time(self, num_sectors) :
		# in the sata, num_sectors should be always 1
		num_bytes = num_sectors * BYTES_PER_SECTOR		
		num_packets = 1
			
		total_transfer_bits = (num_bytes * 8 + (self.DATA_XFER_OVERHEAD * num_packets))
		transfer_time = total_transfer_bits * 10 / 8 / self.HOST_IF_SPEED # ns
	
		if ENABLE_NAND_EXERCISE_MODE == True :
			transfer_time = 1
	
		return num_packets, transfer_time					

	def min_packet_size(self, packet_size) :
		return min(self.WDATA_PACKET_SIZE, packet_size)
																										
	@report_print																								
	def info(self) :
		report_title = 'SATA Gen3'
		
		table = []		
		num_packets, transfer_time = self.calculate_xfer_time(8)
		table.append(['IF speed',  '%d Gbps'%(self.HOST_IF_SPEED)])
		table.append(['number of packets (4K byte)', num_packets])
		table.append(['data packet transfer time', '%d ns'%(transfer_time)]) 	
								
		transfer_time = self.cmd_packet_xfer_time()								
		table.append(['cmd packet transfter time', '%d ns'%(transfer_time)])
		
		return report_title, table							
																							
if __name__ == '__main__' :
	print ('module sata interface')			
	
	host_if = sata()
	host_if.info()																		