#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

# in order to use host and hic at the same time, host interface param module is separted from host.py
# if we use new interface like sata, sas, ufs, new file will be added for each interface

WDATA_PACKET_SIZE = 8			# use to calculate minimum packet size 

# Basic Host Interface : PCIe Gen3x4 
HOST_IF_SPEED = 32 					# Gbps, Gen3x4		
#HOST_IF_SPEED = 64					# Gbps, Gen4x4

DATA_XFER_OVERHEAD = 224	# Header (16Bytes), Start + Sequence + End (4Bytes), ECRC+LCRC (8Bytes) = 28 Byte = 224Bit	
		
# PCIe devices don't use full payload in order to communicate several devices.
# Performance is changed by WDATA_MRD and READ_WDUNIT, because it change the number of packets. 		
WDATA_MRD = 512						# MRd size (Byte) 
REAL_WDUNIT = 256						# Real Write Data Size (Byte)
REAL_RDUNIT = 256						# Read Read Data Size (Byte)
DELAY_1 = 3									# Delay between data and next_data

PRPMRD = 4096
DOORBELL = 4									# Doorbell MWr Size (Byte)
CMD_MRD = 64								# Command MRd Size (Byte)
CPLD = 64										# Completion Data Size (Byte)

def cmd_packet_xfer_time() :
	transfer_time = (DOORBELL + CMD_MRD + CPLD) * 8 * 130 / 128 / HOST_IF_SPEED   # ns
	
	return transfer_time

def rqt_packet_xfer_time() :
	transfer_time = PRPMRD * 8 * 130 / 128 / HOST_IF_SPEED   # ns
	
	return transfer_time
	
def calculate_xfer_time(num_sectors) :
	num_bytes = num_sectors * BYTES_PER_SECTOR		
	num_packets = (num_bytes / WDATA_MRD) * (WDATA_MRD / REAL_WDUNIT)
	
	total_transfer_bits = (num_bytes * 8 + (DATA_XFER_OVERHEAD * num_packets))
	transfer_time = DELAY_1 * (num_packets - 1) + total_transfer_bits * 130 / 128 / HOST_IF_SPEED # ns

	if ENABLE_NAND_EXERCISE_MODE == True :
		transfer_time = 1

	return num_packets, transfer_time					
												
def host_info() :
	num_packets, transfer_time = calculate_xfer_time(8)
	
	print('PCIe Gen3x4 : %d Gbps'%(HOST_IF_SPEED))
	print('packets number per 4K byte : %d'%(num_packets))
	print('transfer time per data packet : %d ns'%(transfer_time)) 	
							
	transfer_time = cmd_packet_xfer_time()								
	print('transfter time per cmd packet : %d ns'%(transfer_time))							
								
if __name__ == '__main__' :
	print ('module pcie interface')			
	
	host_info()																		