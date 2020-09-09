#!/usr/bin/python

import os
import sys

import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.ssd_param import *

# define unit
class unit_context :
	def __init__(self) :
		self.scale_KB = 1000
		self.scale_MB = 1000*1000
		self.scale_GB = 1000*1000*1000
		self.scale_KiB = 1024
		self.scale_MiB = 1024*1024
		self.scale_GiB = 1024*1024*1024

unit = unit_context()

nand_256gb_mlc = {
		'bits_per_cell' : 2,
		'size' : 128, 									# Gb
		'page_size' : 16384,					# byte
		'spare_size' : 1024,					# byte
		'page_num' : 256,
		'plane_num' : 2,	
		'main_block_num' : 1024,
		'add_block_num' : 0,
		'ext_block_num' : 0,
		'spare_block_num' : 0, 				# add_block_num + ext_block_num
		
		'MBB' : 0.02,
		'GBB' : 0.005,
		'BBR' : 0,										# MBB + GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size (byte)
		'extra_data_size' : 4,
		'crc_size' : 4*2,
		'ecc_size' : 192*2,
		
		# NAND IF (Mhz)				
		'nand_if' : 400,
				
		# time (ns)
		'nand_t_cna_w' : 500,				# tADL 300ns tcDQSH 100ns tWB 100ns 
		'nand_t_cna_r' : 500,
		'nand_t_cna_e' : 500,
		'nand_t_chk' : 300,					# tCS 20ns tWHR 120ns tRPRE 15ns
		
		'nand_t_read_lsb' : 0,
		'nand_t_read_msb' : 0,		
		'nand_t_read_full' : 70*1000,
		'nand_t_read_half' : 48*1000,
		'nand_t_read_slc' : 30*1000,
		'nand_t_prog_lsb' : 498*1000,
		'nand_t_prog_msb' : 1691*1000,		
		'nand_t_prog' : (498+169)*1000,
		'nand_t_prog_avg' : (498+169)*1000/2,
		'nand_t_prog_slc' : 398*1000,
		'nand_t_bers' : 6500*1000
}

nand_256gb_g3 = {
		'bits_per_cell' : 3,
		'size' : 256, 									# Gb
		'page_size' : 8192,					# byte
		'spare_size' : 1024,					# byte
		'page_num' : 1152,
		'plane_num' : 4,	
		'main_block_num' : 1214,
		'add_block_num' : 48,
		'ext_block_num' : 10,
		'spare_block_num' : 0, 				# add_block_num + ext_block_num
		
		'MBB' : 0.02,
		'GBB' : 0.005,
		'BBR' : 0,										# MBB + GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size (byte)
		'extra_data_size' : 4,
		'crc_size' : 4*2,
		'ecc_size' : 192*2,

		# NAND IF (Mhz)				
		'nand_if' : 533,
								
		# time (ns)
		'nand_t_cna_w' : 500,				# tADL 300ns tcDQSH 100ns tWB 100ns 
		'nand_t_cna_r' : 500,
		'nand_t_cna_e' : 500,
		'nand_t_chk' : 300,					# tCS 20ns tWHR 120ns tRPRE 15ns
		
		'nand_t_read_lsb' : 0,
		'nand_t_read_msb' : 0,		
		'nand_t_read_full' : 70*1000,
		'nand_t_read_half' : 55*1000,
		'nand_t_read_slc' : 30*1000,
		'nand_t_prog_lsb' : 0,
		'nand_t_prog_msb' : 0,		
		'nand_t_prog' : 2100*1000,
		'nand_t_prog_avg' : 2100*1000/3,
		'nand_t_prog_slc' : 300*1000,
		'nand_t_bers' : 10000*1000
}

nand_256gb_g4 = {
		'bits_per_cell' : 3,
		'size' : 256, 									# Gb
		'page_size' : 8192,					# byte
		'spare_size' : 1024,					# byte
		'page_num' : 1278,
		'plane_num' : 4,	
		'main_block_num' : 1214,
		'add_block_num' : 48,
		'ext_block_num' : 10,
		'spare_block_num' : 0, 				# add_block_num + ext_block_num
		
		'MBB' : 0.02,
		'GBB' : 0.005,
		'BBR' : 0,										# MBB + GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size (byte)
		'extra_data_size' : 4,
		'crc_size' : 4*2,
		'ecc_size' : 192*2,

		# NAND IF (Mhz)				
		'nand_if' : 667,
								
		# time (ns)
		'nand_t_cna_w' : 500,				# tADL 300ns tcDQSH 100ns tWB 100ns 
		'nand_t_cna_r' : 500,
		'nand_t_cna_e' : 500,
		'nand_t_chk' : 300,					# tCS 20ns tWHR 120ns tRPRE 15ns
		
		'nand_t_read_lsb' : 0,
		'nand_t_read_msb' : 0,		
		'nand_t_read_full' : 50*1000,
		'nand_t_read_half' : 45*1000,
		'nand_t_read_slc' : 30*1000,
		'nand_t_prog_lsb' : 0,
		'nand_t_prog_msb' : 0,		
		'nand_t_prog' : 1770*1000,
		'nand_t_prog_avg' : 1770*1000/3,
		'nand_t_prog_slc' : 320*1000,
		'nand_t_bers' : 10000*1000
}

nand_512gb_g5 = {
		'bits_per_cell' : 3,
		'size' : 512, 									# Gb
		'page_size' : 16*1024,					# byte
		'spare_size' : 1024,					# byte
		'page_num' : 1152,
		'plane_num' : 4,	
		'main_block_num' : 910,
		'add_block_num' : 48,
		'ext_block_num' : 10,
		'spare_block_num' : 0, 				# add_block_num + ext_block_num
		
		'MBB' : 0.02,
		'GBB' : 0.005,
		'BBR' : 0,										# MBB + GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size (byte)
		'extra_data_size' : 4,
		'crc_size' : 4*2,
		'ecc_size' : 192*2,

		# NAND IF (Mhz)				
		'nand_if' : 800,
				
		# time (ns)
		'nand_t_cna_w' : 500,				# tADL 300ns tcDQSH 100ns tWB 100ns 
		'nand_t_cna_r' : 500,
		'nand_t_cna_e' : 500,
		'nand_t_chk' : 300,					# tCS 20ns tWHR 120ns tRPRE 15ns
		
		'nand_t_read_lsb' : 0,
		'nand_t_read_msb' : 0,		
		'nand_t_read_full' : 61*1000,
		'nand_t_read_half' : 45*1000,
		'nand_t_read_slc' : 30*1000,
		'nand_t_prog_lsb' : 0,
		'nand_t_prog_msb' : 0,		
		'nand_t_prog' : 1650*1000,
		'nand_t_prog_avg' : 1650*1000/3,
		'nand_t_prog_slc' : 300*1000,
		'nand_t_bers' : 10000*1000
}

class nand_config :
	def __init__(self, nand_param) :
		# nand basic information
		self.bits_per_cell = nand_param['bits_per_cell']
		self.size = nand_param['size'] 								# Gb
		self.page_size = nand_param['page_size']					# byte
		self.spare_size = nand_param['spare_size']					# byte
		self.page_num = nand_param['page_num']
		self.plane_num = nand_param['plane_num']
		self.main_block_num = nand_param['main_block_num']
		self.add_block_num = nand_param['add_block_num']
		self.ext_block_num = nand_param['ext_block_num']
		self.spare_block_num = self.add_block_num + self.ext_block_num
		
		self.MBB = nand_param['MBB']
		self.GBB = nand_param['GBB']
		self.BBR = self.MBB + self.GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size
		self.extra_data_size = nand_param['extra_data_size']
		self.crc_size = nand_param['crc_size']
		self.ecc_size = nand_param['ecc_size']

		# NAND IF
		self.nand_if = nand_param['nand_if']			
		# change value by calculation when nand if is 400MHz (2.5ns/byte) # (5/2) *(BYTES_PER_CHUNK + EXT_DATA_SIZE + ECC_SIZE + CRC_SIZE)  + 500
		self.nand_t_xfer = (1/self.nand_if*1000) * (BYTES_PER_CHUNK + self.extra_data_size + self.ecc_size + self.crc_size) + 500
				
		# time (ns)
		self.nand_t_cna_w = nand_param['nand_t_cna_w']	# tADL 300ns tcDQSH 100ns tWB 100ns 
		self.nand_t_cna_r = nand_param['nand_t_cna_r']
		self.nand_t_cna_e = nand_param['nand_t_cna_e']
		self.nand_t_chk = nand_param['nand_t_chk']		# tCS 20ns tWHR 120ns tRPRE 15ns
						
		self.nand_t_read_lsb = nand_param['nand_t_read_lsb']
		self.nand_t_read_msb = nand_param['nand_t_read_msb']
		self.nand_t_read_full = nand_param['nand_t_read_full']
		self.nand_t_read_half = nand_param['nand_t_read_half']
		self.nand_t_read_slc = nand_param['nand_t_read_slc']
		self.nand_t_prog_lsb = nand_param['nand_t_prog_lsb']
		self.nand_t_prog_msb = nand_param['nand_t_prog_msb']
		if self.bits_per_cell == 2 :
			self.nand_t_prog = (self.nand_t_prog_lsb + self.nand_t_prog_msb)
		else :
			self.nand_t_prog = nand_param['nand_t_prog']
		self.nand_t_prog_avg = int(self.nand_t_prog / self.bits_per_cell)
		self.nand_t_prog_slc = nand_param['nand_t_prog_slc']
		self.nand_t_bers = nand_param['nand_t_bers']
										
	def load_excel(self, filename) :
		data = pd.read_excel(filename)
		
		data.columns = ['item', 'value']
		data = data.set_index('item')
		
		#print(data.columns)
		#print(data.index)																									

		nand_param = data.loc
		
		self.bits_per_cell = int(nand_param['bits_per_cell'])
		self.size = int(nand_param['size']) 										# Gb
		self.page_size = int(nand_param['page_size'])					# byte
		self.spare_size = int(nand_param['spare_size'])					# byte
		self.page_num = int(nand_param['page_num'])
		self.plane_num = int(nand_param['plane_num'])
		self.main_block_num = int(nand_param['main_block_num'])
		self.add_block_num = int(nand_param['add_block_num'])
		self.ext_block_num = int(nand_param['ext_block_num'])
		self.spare_block_num = self.add_block_num + self.ext_block_num
		
		self.MBB = float(nand_param['MBB'])
		self.GBB = float(nand_param['GBB'])
		self.BBR = self.MBB + self.GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size
		self.extra_data_size = int(nand_param['extra_data_size'])
		self.crc_size = int(nand_param['crc_size'])
		self.ecc_size = int(nand_param['ecc_size'])

		# NAND IF
		self.nand_if = int(nand_param['nand_if'])			
		# change value by calculation when nand if is 400MHz (2.5ns/byte) # (5/2) *(BYTES_PER_CHUNK + EXT_DATA_SIZE + ECC_SIZE + CRC_SIZE)  + 500
		self.nand_t_xfer = (1/self.nand_if*1000) * (BYTES_PER_CHUNK + self.extra_data_size + self.ecc_size + self.crc_size) + 500
				
		# time (ns)
		self.nand_t_cna_w = int(nand_param['nand_t_cna_w'])
		self.nand_t_cna_r = int(nand_param['nand_t_cna_r'])
		self.nand_t_cna_e = int(nand_param['nand_t_cna_e'])
		self.nand_t_chk = int(nand_param['nand_t_chk'])		
						
		self.nand_t_read_lsb = int(nand_param['nand_t_read_lsb'])
		self.nand_t_read_msb = int(nand_param['nand_t_read_msb'])
		self.nand_t_read_full = int(nand_param['nand_t_read_full'])
		self.nand_t_read_half = int(nand_param['nand_t_read_half'])
		self.nand_t_read_slc = int(nand_param['nand_t_read_slc'])
		self.nand_t_prog_lsb = int(nand_param['nand_t_prog_lsb'])
		self.nand_t_prog_msb = int(nand_param['nand_t_prog_msb'])
		if self.bits_per_cell == 2 :
			self.nand_t_prog = (self.nand_t_prog_lsb + self.nand_t_prog_msb)
		else :
			self.nand_t_prog = int(nand_param['nand_t_prog'])
		self.nand_t_prog_avg = int(self.nand_t_prog / self.bits_per_cell)
		self.nand_t_prog_slc = int(nand_param['nand_t_prog_slc'])
		self.nand_t_bers = int(nand_param['nand_t_bers'])
																													
	def get_type_label(self) :
		return {'name' : ['bits per cell', 'capacity[Gb]', 'page size[KB]', 'page num', 'plane num', 'wordline num', 'block num', 'small block size[MB]', 'big block size[MB]', 'extra_data_size', 'crc_size', 'ecc_size']}				
	
	def get_type_value(self) :
		# calculate ssd information
		small_block_size = self.page_size * self.page_num
		big_block_size = small_block_size * self.plane_num
													
		info_columns = []
		info_columns.append(self.bits_per_cell)
		info_columns.append(self.size)
		info_columns.append(int(self.page_size / unit.scale_KB))
		info_columns.append(self.page_num)
		info_columns.append(self.plane_num)
		info_columns.append(int(self.page_num / self.bits_per_cell))
		info_columns.append(self.main_block_num)
		info_columns.append(int(small_block_size / unit.scale_MB))
		info_columns.append(int(big_block_size / unit.scale_MB))
		info_columns.append(self.extra_data_size)
		info_columns.append(self.crc_size)
		info_columns.append(self.ecc_size)

		return info_columns

	def get_param_lable(self) :
		return {'name' : ['interface speed', 'nand_t_xfer(us/4KB)', 'nand_t_xfer(us/multi-plane)', 'nand_t_cna_w', 'nand_t_cna_r', 'nand_t_cna_e', 'nand_t_chk', 'nand_t_read_full [us]', 'nand_t_read_half [us]', 'nand_t_read_slc [us]', 'nand_t_prog [us]', 'nand_t_prog_avg [us]', 'nand_t_prog_slc [us]', 'nand_t_bers [ms]']}
		
	def get_param_value(self) :
		param_columns = []

		param_columns.append(self.nand_if)
		param_columns.append(int(self.nand_t_xfer/1000))
		
		num_chunks = self.page_size / BYTES_PER_CHUNK * self.plane_num		
		param_columns.append(int(self.nand_t_xfer * num_chunks /1000))
				
		param_columns.append(self.nand_t_cna_w)
		param_columns.append(self.nand_t_cna_r)
		param_columns.append(self.nand_t_cna_e)
		param_columns.append(self.nand_t_chk)

		param_columns.append(int(self.nand_t_read_full/1000))
		param_columns.append(int(self.nand_t_read_half/1000))
		param_columns.append(int(self.nand_t_read_slc/1000))
				
		param_columns.append(int(self.nand_t_prog/1000))
		param_columns.append(int(self.nand_t_prog_avg/1000))
		param_columns.append(int(self.nand_t_prog_slc/1000))
		param_columns.append(int(self.nand_t_bers/1000000))

		return param_columns
																				
	def print_type(self) :
		print('\nnand type')
							
		info_pd = pd.DataFrame(self.get_type_label())																																	
		info_pd['value'] = pd.Series(self.get_type_value(), index=info_pd.index)

		print(info_pd)											

	def print_param(self) :
		print('\nnand parameter')
														
		param_pd = pd.DataFrame(self.get_param_lable())																																																																																												
		param_pd['value'] = pd.Series(self.get_param_value(), index=param_pd.index)
		
		print(param_pd)								
													
if __name__ == '__main__' :
	print('nand configuration')				

	# read list test	
	nand1 = nand_config(nand_256gb_g3)
	print('\n\nnand_256gb_g3 configuration')
	nand1.print_type()
	nand1.print_param()
	
	# read excel file test
	nand1.load_excel('nand_128gb_mlc.xlsx')
	print('\n\nnand_128gb_mlc.xlsx configuration')
	nand1.print_type()
	nand1.print_param()
																	