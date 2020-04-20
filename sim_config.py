#!/usr/bin/python

import os
import sys

# define unit
class unit_context :
	def __init__(self) :
		self.scale_KB = 1000
		self.scale_MB = 1000*1000
		self.scale_GB = 1000*1000*1000
		self.scale_KiB = 1024
		self.scale_MiB = 1024*1024
		self.scale_GiB = 1024*1024*1024

# TLC NAND 256Gb
class nand_256gb_g3 :
	def __init__(self) :
		# nand basic information
		self.size = 256 						# Gb
		self.page_size = 8*1024		# byte
		self.spare_size = 1024
		self.page_num = 1152
		self.plane_num = 4		
		self.main_block_num = 1214
		self.add_block_num = 48
		self.ext_block_num = 10
		self.spare_block_num = self.add_block_num + self.ext_block_num
		
		self.MBB = 0.02
		self.GBB = 0.005
		self.BBR = self.MBB + self.GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)	
		# size
		self.extra_data_size = 4
		self.crc_size = 4*2
		self.ecc_size = 192*2
		
		# time (ns)
		self.nand_t_cna_w = 500	# tADL 300ns tcDQSH 100ns tWB 100ns 
		self.nand_t_cna_r = 500
		self.nand_t_cna_e = 500
		self.nand_t_chk = 300		# tCS 20ns tWHR 120ns tRPRE 15ns
		# NAND IF (533Mhz)
		self.nand_t_xfer = 10000			# change value by calculation (2.5ns/byte) # (BYTES_PER_CHUNK + EXT_DATA_SIZE + ECC_SIZE + CRC_SIZE) * 5/2 + 500
		
		self.nand_t_read_lsb = 0
		self.nand_t_read_msb = 0		
		self.nand_t_read_full = (70*1000)
		self.nand_t_read_half = (55*1000)
		self.nand_t_prog_lsb = 0
		self.nand_t_prog_msb = 0				
		self.nand_t_prog = (2100*1000)			# one shot time
		self.nand_t_prog_avg = self.nand_t_prog / 3
		self.nand_t_prog_slc = (300*1000)
		self.nand_t_bers = (10000*1000)
		
class nand_256gb_g4 :
	def __init__(self) :
		# nand basic information
		self.size = 256 						# Gb
		self.page_size = 8*1024		# byte
		self.page_num = 1728
		self.plane_num = 4		
		self.main_block_num = 1214
		self.add_block_num = 48
		self.ext_block_num = 10
		self.spare_block_num = self.add_block_num + self.ext_block_num
		
		self.MBB = 0.02
		self.GBB = 0.005
		self.BBR = self.MBB + self.GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)	
		# size
		self.extra_data_size = 4
		self.crc_size = 4*2
		self.ecc_size = 192*2
		
		# time (ns)
		self.nand_t_cna_w = 500	# tADL 300ns tcDQSH 100ns tWB 100ns 
		self.nand_t_cna_r = 500
		self.nand_t_cna_e = 500
		self.nand_t_chk = 300		# tCS 20ns tWHR 120ns tRPRE 15ns
		# NAND IF (667Mhz)
		self.nand_t_xfer = 10000			# change value by calculation (2.5ns/byte) # (BYTES_PER_CHUNK + EXT_DATA_SIZE + ECC_SIZE + CRC_SIZE) * 5/2 + 500
		
		self.nand_t_read_lsb = 0
		self.nand_t_read_msb = 0
		self.nand_t_read_full = (50*1000)
		self.nand_t_read_half = (45*1000)
		self.nand_t_prog_lsb = 0
		self.nand_t_prog_msb = 0		
		self.nand_t_prog = (1770*1000)			# one shot time	
		self.nand_t_prog_avg = self.nand_t_prog / 3
		self.nand_t_prog_slc = (320*1000)
		self.nand_t_bers = (10000*1000)		
			
# TLC NAND 512Gb
class nand_512gb :
	def __init__(self) :
		# nand basic information
		self.size = 512 						# Gb
		self.page_size = 8*1024		# byte
		self.page_num = 1728
		self.plane_num = 4		
		self.main_block_num = 1214
		self.add_block_num = 48
		self.ext_block_num = 10
		self.spare_block_num = self.add_block_num + self.ext_block_num
		
		self.MBB = 0.02
		self.GBB = 0.005
		self.BBR = self.MBB + self.GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)	
		# size
		self.extra_data_size = 4
		self.crc_size = 4*2
		self.ecc_size = 192*2
		
		# time (ns)
		self.nand_t_cna_w = 500	# tADL 300ns tcDQSH 100ns tWB 100ns 
		self.nand_t_cna_r = 500
		self.nand_t_cna_e = 500
		self.nand_t_chk = 300		# tCS 20ns tWHR 120ns tRPRE 15ns
		self.nand_t_xfer = 10000			# change value by calculation (2.5ns/byte) # (BYTES_PER_CHUNK + EXT_DATA_SIZE + ECC_SIZE + CRC_SIZE) * 5/2 + 500
		
		self.nand_t_read_lsb = (55*1000)
		self.nand_t_read_msb = (86*1000)
		self.nand_t_prog_lsb = (430*1000)
		self.nand_t_prog_msb = (1579*1000)
		self.nand_t_bers = (5181*1000)	
					
unit = unit_context()
nand_info = nand_256gb_g3()
#nand_info = nand_512gb()

if __name__ == '__main__' :
	print(nand_info)												