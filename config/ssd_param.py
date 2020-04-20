#!/usr/bin/python

import os
import sys

ENABLE_RAMDISK_MODE = False
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

# define number of queue
NUM_HOST_QUEUE = 1

# define queue depth of host command
NUM_HOST_CMD_TABLE = 32

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
NAND_MODE_TLC = 0x00			
NAND_MODE_SLC = 0x01
NAND_MODE_QLC = 0x02

# define term of chunk
# size of chunk is 4K, chunk is minimum unit for saving data
# nand page has multiple chunks, if the size of nand page is 8k, nand page has 2 chunks 
# BYTES_PER_PAGE = single plane page size x plane number
BYTES_PER_PAGE = 8192 * 4
PAGES_PER_BLOCK = 256
BLOCKS_PER_WAY = 1024

CHUNKS_PER_PAGE = int(BYTES_PER_PAGE / BYTES_PER_CHUNK)
CHUNKS_PER_BLOCK = int(CHUNKS_PER_PAGE * PAGES_PER_BLOCK)
CHUNKS_PER_WAY = int(CHUNKS_PER_BLOCK * BLOCKS_PER_WAY)

# SSD controller parameter
# HIC (host interface controller)
# define queue depth of host command (it is same with NUM_HOST_CMD_TABLE, however it is changed by HIC architecture)
NUM_CMD_EXEC_TABLE = 64

# Global queue depth definition
# ftl cmd queue communication between ftl and fil
# there are two priority queue
FTL_CMD_QUEUE_DEPTH = 256


# NFC (nand flash controller)
# The nfc has channels, each channel can handle several dies of nand (using ce, lun adderss)
# way is same term with nand die
# if we use 32 dies of nand and nfc has 8 channels, the number of ways is 32, ways per channel is 4
# if channle is own by one way,  the other way can not use channel. (?)  
NUM_CHANNELS = 4
WAYS_PER_CHANNELS = 1
NUM_WAYS = (NUM_CHANNELS * WAYS_PER_CHANNELS) 

# BM (buffer managerment)
#Write Buffer : 1M Byte, Read Buffer : 3M Byte
SSD_WRITE_BUFFER_SIZE = 1 * 1024 * 1024
SSD_READ_BUFFER_SIZE = 16 * 1024 * 1024
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

def ssd_info(report = None) :
	print('ssd capacity : %d GB'%SSD_CAPACITY)
#	print('ssd actual capacity : %d'%SSD_CAPACITY_ACTUAL)
	print('num of lba (512 byte sector) : %d'%NUM_LBA)
	print('num of logical chunk (4K unit) : %d'%(NUM_LBA/SECTORS_PER_CHUNK))	

if __name__ == '__main__' :
	print('ssd param')
	
	ssd_info()												
