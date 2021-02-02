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

'''				
# PCIe devices don't use full payload in order to communicate several devices.

PRPMRD = 4096
DOORBELL = 4									# Doorbell MWr Size (Byte)
CMD_MRD = 64								# Command MRd Size (Byte)
CPLD = 64										# Completion Data Size (Byte)
'''

DELAY_1 = 3									# Delay between data and next_data

# UniPro Segment within a Data Frame (Byte)
SDF = 2									
L3_SHORT_HEADER = 1
L4_SHORT_HEADER = 1
EDF = 2
CHECKSUM = 2

# UniPro Frame payload definition (Byte) 
# L2 Data Frame
MAX_FRAME_PAYLOAD = 288
MINIMUM_PACKET_SIZE = 2			# two or more of the 288 bytes are used by higher layer of the UniPro protocol

# L4 segment
MAX_SEGMENT_PAYLOAD = MAX_FRAME_PAYLOAD-(L3_SHORT_HEADER+L4_SHORT_HEADER)
MIN_SEGMENT_PAYLOAD = 256	# for UFS

# High Speed [Mbps] define
HS_RATE_A = [1248, 2496, 4992, 9984]
HS_RATE_B = [1457.6, 2915.2, 5830.4, 11660.8]

# UPIU(UFS Protocol Information Unit)
UPIU_SIZE = 16

class ufs :
	def __init__(self, gen, lane) :
		self.set_config(gen, lane)
	
		self.DATA_XFER_OVERHEAD = (SDF+L3_SHORT_HEADER+L4_SHORT_HEADER+EDF+CHECKSUM)*8	# 64Bit	
		self.WDATA_PACKET_SIZE = 8			# use to calculate minimum packet size 
	
	def set_config(self, gear, lane) :
		self.gear = gear
		self.lane = lane
		
		rate = HS_RATE_B
		
		# self.HOST_IF_SPEED [Gbps]
		if gear <= 4 :
			self.HOST_IF_SPEED = rate[gear-1] * lane / 1000
		else :
			print('error : host if setting')
				
	def cmd_packet_xfer_time(self) :
		# use SCSI 10 CDB(Command Description Block)
		# 10B/8B encoding
		# example of PCIe : transfer_time = (DOORBELL + CMD_MRD + CPLD) * 8 * 10 / 8 / self.HOST_IF_SPEED   # ns
		total_transfer_bits = UPIU_SIZE*8 + self.DATA_XFER_OVERHEAD 
		transfer_time = total_transfer_bits * 10 / 8 / self.HOST_IF_SPEED # ns
		
		return transfer_time
	
	def rqt_packet_xfer_time(self) :
		# use SCSI 10 CDB(Command Description Block)		
		# example of PCIe : transfer_time = PRPMRD * 8 * 10 / 8 / self.HOST_IF_SPEED   # ns
		total_transfer_bits = UPIU_SIZE*8 + self.DATA_XFER_OVERHEAD 
		transfer_time = total_transfer_bits * 10 / 8 / self.HOST_IF_SPEED # ns
		
		return transfer_time
		
	def calculate_xfer_time(self, num_sectors) :
		num_bytes = num_sectors * BYTES_PER_SECTOR		
		num_packets = (num_bytes / MIN_SEGMENT_PAYLOAD) 
		
		total_transfer_bits = (num_bytes*8 + (UPIU_SIZE*8 + self.DATA_XFER_OVERHEAD * num_packets))
		transfer_time = DELAY_1 * (num_packets - 1) + total_transfer_bits * 10 / 8 / self.HOST_IF_SPEED # ns
	
		if ssd_param.ENABLE_NAND_EXERCISE_MODE == True :
			transfer_time = 1
	
		return num_packets, transfer_time					
	
	def min_packet_size(self, packet_size) :
		return min(2048, packet_size)
	
	@report_print																								
	def info(self) :
		report_title = 'UFS gear%d, lane : %d'%(self.gear, self.lane)
		
		table = []		
		num_packets, transfer_time = self.calculate_xfer_time(8)
		table.append(['IF speed',  '%d Gbps'%(self.HOST_IF_SPEED)])
		table.append(['number of packets (4K byte)', num_packets])
		table.append(['data packet transfer time', '%d ns'%(transfer_time)]) 	
								
		transfer_time = self.cmd_packet_xfer_time()								
		table.append(['cmd packet transfter time', '%d ns'%(transfer_time)])
		
		transfer_time = self.rqt_packet_xfer_time()								
		table.append(['rqt packet transfter time', '%d ns'%(transfer_time)])
				
		return report_title, table							
																																															
if __name__ == '__main__' :
	print ('module ufs interface')			

	host_if = ufs(4, 2)										
	host_if.info()	
	
	host_if.set_config(2, 2)										
	host_if.info()																	