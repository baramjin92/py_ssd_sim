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
		
# PCIe devices don't use full payload in order to communicate several devices.
# Performance is changed by WDATA_MRD and READ_WDUNIT, because it change the number of packets. 		
WDATA_MRD = 512						# MRd size (Byte)
#REAL_WDUNIT and REAL_RDUNIT is changed by HOST_MPS 
REAL_WDUNIT = 256						# Real Write Data Size (Byte)
REAL_RDUNIT = 256						# Read Read Data Size (Byte)
DELAY_1 = 3									# Delay between data and next_data

PRPMRD = 4096
DOORBELL = 4									# Doorbell MWr Size (Byte)
CMD_MRD = 64								# Command MRd Size (Byte)
CPLD = 64										# Completion Data Size (Byte)

class pcie :
	def __init__(self, gen, lane, mps=256) :
		self.set_config(gen, lane, mps)
	
		self.DATA_XFER_OVERHEAD = 224	# Header (16Bytes), Start + Sequence + End (4Bytes), ECRC+LCRC (8Bytes) = 28 Byte = 224Bit			
		self.WDATA_PACKET_SIZE = 8			# use to calculate minimum packet size 
	
	def set_config(self, gen, lane, mps) :
		self.gen = gen
		self.lane = lane
		
		if gen == 3 :
			self.HOST_IF_SPEED = 8 * lane
		elif gen == 4 :
			self.HOST_IF_SPEED = 16 * lane
		elif gen == 5 :
			self.HOST_IF_SPEED = 32 * lane			
		else :
			print('error : host if setting')
			
		self.HOST_MPS = mps
	
	def cmd_packet_xfer_time(self) :
		transfer_time = (DOORBELL + CMD_MRD + CPLD) * 8 * 130 / 128 / self.HOST_IF_SPEED   # ns
		
		return transfer_time
	
	def rqt_packet_xfer_time(self) :
		# we need to consider PRPMRD is correct value 
		# current value is 4096, it is not measured. it assume the maximum case
		# 512 is temporary value, it doesn't affect the simulation time'
		transfer_time = 512 * 8 * 130 / 128 / self.HOST_IF_SPEED   # ns
		#transfer_time = PRPMRD * 8 * 130 / 128 / self.HOST_IF_SPEED   # ns
		
		return transfer_time
		
	def calculate_xfer_time(self, num_sectors) :
		num_bytes = num_sectors * BYTES_PER_SECTOR		
		num_packets = (num_bytes / WDATA_MRD) * (WDATA_MRD / self.HOST_MPS)
		
		total_transfer_bits = (num_bytes * 8 + (self.DATA_XFER_OVERHEAD * num_packets))
		transfer_time = DELAY_1 * (num_packets - 1) + total_transfer_bits * 130 / 128 / self.HOST_IF_SPEED # ns
	
		if ssd_param.ENABLE_NAND_EXERCISE_MODE == True :
			transfer_time = 1
	
		return num_packets, transfer_time					
	
	def min_packet_size(self, packet_size) :
		return min(self.WDATA_PACKET_SIZE, packet_size)
	
	@report_print																								
	def info(self) :
		report_title = 'PCIe Gen%dx%d'%(self.gen, self.lane)
		
		table = []		
		num_packets, transfer_time = self.calculate_xfer_time(8)
		table.append(['IF speed',  '%d Gbps'%(self.HOST_IF_SPEED)])
		table.append(['MPS',  self.HOST_MPS])
		table.append(['number of packets (4K byte)', num_packets])
		table.append(['data packet transfer time', '%d ns'%(transfer_time)]) 	
								
		transfer_time = self.cmd_packet_xfer_time()								
		table.append(['cmd packet transfter time', '%d ns'%(transfer_time)])

		transfer_time = self.rqt_packet_xfer_time()								
		table.append(['rqt packet transfter time', '%d ns'%(transfer_time)])
				
		return report_title, table							
																																															
if __name__ == '__main__' :
	print ('module pcie interface')			

	host_if = pcie(4, 4, 512)										
	host_if.info()	
	
	host_if.set_config(3, 4, 256)										
	host_if.info()																	