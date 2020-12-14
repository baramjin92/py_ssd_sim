#!/usr/bin/python

import os
import sys

import re

import tabulate

import xml.etree.ElementTree as elemTree

ENABLE_NAND_EXERCISE_MODE = False
ENABLE_BUFFER_CACHE = False

# slice or chunk are mapping unit. we use 4K mapping usually. 
# instead of slice, I will use chunk

BYTES_PER_SECTOR = 512								
BYTES_PER_CHUNK = 4096
SECTORS_PER_CHUNK = (BYTES_PER_CHUNK / BYTES_PER_SECTOR)

# Host
#define command type
HOST_CMD_IDLE = 0
HOST_CMD_READ = 1
HOST_CMD_WRITE = 2
HOST_CMD_FLUSH = 3
HOST_CMD_TRIM = 4
HOST_CMD_CALM = 5
HOST_CMD_ZONE_SEND = 6
HOST_CMD_ZONE_RECV = 7

# ZSA(Zone Send Action)
HOST_ZSA_CLOSE = 1
HOST_ZSA_OPEN = 3
HOST_ZSA_RESET = 4

# define queue depth of host command
NUM_HOST_CMD_TABLE = 512	#128			#32

# Nand
# define command type
# it is simple mode of nand command
# it will be extend to simulate real nand model
NAND_CMD_READ = 1
NAND_CMD_PROGRAM = 2
NAND_CMD_ERASE = 3
NAND_CMD_MODE = 4

# define cell mode
NAND_MODE_MLC = 0x00				# default cell mode should be 0
NAND_MODE_TLC = 0x01			
NAND_MODE_SLC = 0x02
NAND_MODE_QLC = 0x03

# SSD controller parameter
# HIC (host interface controller)
# define queue depth of host command (it is same with NUM_HOST_CMD_TABLE, however it is changed by HIC architecture)
NUM_CMD_EXEC_TABLE = 512	#128			#64

# Global queue depth definition
# ftl cmd queue communication between ftl and fil
# there are two priority queue
FTL_CMD_QUEUE_DEPTH = 512

# BM (buffer managerment)
#Write Buffer : 1M Byte, Read Buffer : 3M Byte
SSD_WRITE_BUFFER_SIZE = 4 * 1024 * 1024
SSD_READ_BUFFER_SIZE = 32 * 1024 * 1024
SSD_BUFFER_SIZE = (SSD_WRITE_BUFFER_SIZE + SSD_READ_BUFFER_SIZE) 

SSD_WRITE_BUFFER_NUM = int(SSD_WRITE_BUFFER_SIZE / BYTES_PER_CHUNK)
SSD_READ_BUFFER_NUM = int(SSD_READ_BUFFER_SIZE / BYTES_PER_CHUNK)

SSD_BUFFER_NUM = (SSD_WRITE_BUFFER_NUM + SSD_READ_BUFFER_NUM)

SSD_BUFFER_CACHE_NUM = int(SSD_READ_BUFFER_NUM / 2)

# SSD capacity unit is GB (advertised capacity)
SSD_CAPACITY = 15
NUM_LBA = 97696368 + (1953504 * (SSD_CAPACITY - 50))

# SSD_CAPACITY = int((NUM_LBA - 97696368) / 1953504 + 50)

# OP 7% capacity
#SSD_CAPACITY_ACTUAL = SSD_CAPACITY * 1953125 / 2097152

def convert_speed(host_speed) :
	speed = re.findall('\d+', host_speed)
	if len(speed) == 1 :
		speed.append('1')
		
	return int(speed[0]), int(speed[1])
	
class ssd_param_desc :
	def __init__(self) :
		self.ENABLE_RAMDISK_MODE = True
		
		self.HOST_IF = 'PCIE'					# 'SATA', 'UFS'
		self.HOST_SPEED = 'GEN3X4'		# 'GEN4x4''		
		self.HOST_GEN, self.HOST_LANE = convert_speed(self.HOST_SPEED)
		self.HOST_MPS = 256
									
		# define number of queue
		self.NUM_HOST_QUEUE = 1
	
		# NFC (nand flash controller)
		# The nfc has channels, each channel can handle several dies of nand (using ce, lun adderss)
		# way is same term with nand die
		# if we use 32 dies of nand and nfc has 8 channels, the number of ways is 32, ways per channel is 4
		# if channle is own by one way,  the other way can not use channel. (?)	 
		self.NUM_CHANNELS = 8
		self.WAYS_PER_CHANNELS = 4
		self.NUM_WAYS = (self.NUM_CHANNELS * self.WAYS_PER_CHANNELS)
		
		 # NAND 
		self.NAND_MODEL = None

		# DRAM
		self.DDR_BANDWIDTH = 3200
		self.DDR_BUSWIDTH = 32

		# Workload
		self.WORKLOAD_MODEL = None
		
		# BLK GROUP
		self.BLK_GRP_INFO = []

		# ZNS definition
		self.ZONE_SIZE = 32 * 1024 * 1024
		self.ZONE_NUM_WAYS = int(self.NUM_WAYS / 4)
		self.NUM_OPEN_ZONES = 3
		self.NUM_ZONES = int((NUM_LBA * BYTES_PER_SECTOR) / self.ZONE_SIZE)
		
		# Acceleration
		self.Acceleration = False
					
ssd_param = ssd_param_desc() 		
				
def load_ssd_config_xml(filename) :	
	tree = elemTree.parse(filename)
	ssd = tree.find('./ssd_configuration')

	ssd_param.HOST_IF = ssd.find('host_if').text.upper()
	ssd_param.HOST_SPEED = ssd.find('host_speed').text.upper()
	ssd_param.HOST_GEN, ssd_param.HOST_LANE = convert_speed(ssd_param.HOST_SPEED)
	ssd_param.HOST_MPS = int(ssd.find('max_payload_size').text)
		
	ssd_param.NUM_HOST_QUEUE = int(ssd.find('number_of_host_queue').text)
	ssd_param.NUM_CHANNELS = int(ssd.find('channel').text)
	ssd_param.WAYS_PER_CHANNELS = int(ssd.find('way_per_channel').text)
	ssd_param.NUM_WAYS = (ssd_param.NUM_CHANNELS * ssd_param.WAYS_PER_CHANNELS)

	blk_grp = []
	for node in ssd :
		if node.tag == 'nand' :
			ssd_param.NAND_MODEL = [node.find('file').text, node.find('name').text]			
		elif node.tag == 'dram' :
			bandwidth = re.findall('\d+', node.find('bandwidth').text)
			ssd_param.DDR_BANDWIDTH = int(bandwidth[0])
			ssd_param.DDR_BUSWIDTH = int(node.find('buswidth').text)
		elif node.tag == 'workload' :
			ssd_param.WORKLOAD_MODEL = [node.find('file').text, node.find('name').text]		
		elif node.tag == 'blk_grp' :
			for child in node.iter('blk_manager') :
				name = child.find('name').text
				num_way = child.find('number_of_way').text
				if num_way.upper() == 'ALL' :
					num_way = 'ALL'
				else :
					num_way = int(row[1])
					
				list_way = child.find('list_of_way').text
				if list_way.upper() == 'NONE' :
					list_way = None
				else :
					ways = list_way.split(',')
					list_way = [int(way) for way in ways]
				start_no = int(child.find('start_block_no').text)
				end_no = int(child.find('end_block_no').text)
				threshold_low = int(child.find('threshold_low').text)
				threshold_high = int(child.find('threshold_high').text)
				cell_mode = 'NAND_MODE_' + child.find('cell_mode').text
				blk = [name, num_way, list_way, start_no, end_no, threshold_low, threshold_high, cell_mode]
				blk_grp.append(blk)
				
	ssd_param.BLK_GRP_INFO = blk_grp
																									
def print_setting_info(report_title = 'default parameter value') :
	table = []

	table.append(['Host Interface', ssd_param.HOST_IF])
	table.append(['Host Speed', ssd_param.HOST_SPEED])
	table.append(['Max Payload Size', ssd_param.HOST_MPS])	
	table.append(['Number of Host Queue', ssd_param.NUM_HOST_QUEUE])
	table.append(['Number of Nand Channel', ssd_param.NUM_CHANNELS])
	table.append(['Number of Ways per Channel', ssd_param.WAYS_PER_CHANNELS])
	table.append(['Number of All Ways', ssd_param.NUM_WAYS])	
	table.append(['NAND Model', ssd_param.NAND_MODEL])
	table.append(['DRAM Bandwidth', ssd_param.DDR_BANDWIDTH])
	table.append(['DRAM Bus width', ssd_param.DDR_BUSWIDTH])			
	table.append(['Number of Host Cmd Table', NUM_HOST_CMD_TABLE])
	table.append(['Number of Cmd Execution Table', NUM_CMD_EXEC_TABLE])
	table.append(['FTL Cmd Queue Depth', FTL_CMD_QUEUE_DEPTH])
	table.append(['Number of Write Buffer', SSD_WRITE_BUFFER_NUM])
	table.append(['Number of Read Buffer', SSD_READ_BUFFER_NUM])
	table.append(['SSD Capacity', '%d GB'%SSD_CAPACITY])
#	table.append(['SSD Actual Capacity', '%d GB'%SSD_CAPACITY_ACTUAL])
	table.append(['Number of lba (512 byte sector)', NUM_LBA])
	table.append(['Number of Chunk (4K unit)', int(NUM_LBA/SECTORS_PER_CHUNK)])	
	table.append(['NAND Model', ssd_param.WORKLOAD_MODEL])
	
	print(report_title)
	print(tabulate.tabulate(table))	

if __name__ == '__main__' :
	
	print_setting_info()
	load_ssd_config_xml('ssd_config.xml')
	print_setting_info('xml parameter value')
	
	print(ssd_param.BLK_GRP_INFO)																						