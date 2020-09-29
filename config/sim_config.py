#!/usr/bin/python

import os
import sys

import csv
import re

# pd is required for open excel file. it is temporary disable for pypy
#import pandas as pd

import xml.etree.ElementTree as elemTree

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from sim_log import *

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

nand_time_units = {
	'ms' : 1000*1000,
	'us' : 1000,
	'ns' : 1,	
}		

def convert_nand_time(value_str) :
	value_str = value_str.lower()
	
	scale = 0
	for unit in nand_time_units :	
		if value_str.find(unit) != -1 :
			scale = nand_time_units[unit]
			break 
	
	value = int(re.findall('\d+', value_str)[0])
	value = value * scale
	
	return value 		  			

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
		'nand_t_prog' : (498+1691)*1000,
		'nand_t_prog_avg' : (498+1691)*1000/2,
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
		if nand_param == None :
			print('use default nand information')
			self.set_data(nand_256gb_mlc)
		else :
			self.set_data(nand_param)
												
	def load_csv(self, filename) :
		fp = open(filename, 'r')
		rows = csv.reader(fp)
		
		nand_param = {}
		for row in rows :
			if row[0] != '' :
				nand_param[row[0]] = row[1]									
																																							
		fp.close()
		
		self.set_data(nand_param)																																		
										
	def load_excel(self, filename) :
		data = pd.read_excel(filename)
		
		data.columns = ['item', 'value']
		data = data.set_index('item')
		
		#print(data.columns)
		#print(data.index)																									

		nand_param = data.loc
		self.set_data(nand_param)
		
	def load_xml(self, filename, name) :
		tree = elemTree.parse(filename)
		#nand = tree.find('./nand')
		nand = tree.find('./nand[@name=\'%s\']'%name)
		
		print(nand.get('name'))		
		self.set_data_from_xml(nand)
		
	def set_data(self, nand_param) :
		# nand basic information			
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
						
	def set_data_from_xml(self, nand) :
		# nand basic information			
		self.bits_per_cell = int(nand.find('bits_per_cell').text)
		self.size = int(nand.find('size').text)										# Gb
		self.page_size = int(nand.find('page_size').text)					# byte
		self.spare_size = int(nand.find('spare_size').text)				# byte
		self.page_num = int(nand.find('page_num').text)
		self.plane_num = int(nand.find('plane_num').text)
		self.main_block_num = int(nand.find('main_block_num').text)
		self.add_block_num = int(nand.find('add_block_num').text)
		self.ext_block_num = int(nand.find('ext_block_num').text)
		self.spare_block_num = self.add_block_num + self.ext_block_num
		
		self.MBB = float(nand.find('manufacture_badblock').text)
		self.GBB = float(nand.find('grown_badblock').text)
		self.BBR = self.MBB + self.GBB
		
		# nand ac paramter (size unit is byte, time unit is ns)			
		# size
		self.extra_data_size = int(nand.find('extra_data_size').text)
		self.crc_size = int(nand.find('crc_size').text)
		self.ecc_size = int(nand.find('ecc_size').text)

		# NAND IF
		self.nand_if = int(nand.find('nand_if').text)			
		# change value by calculation when nand if is 400MHz (2.5ns/byte) # (5/2) *(BYTES_PER_CHUNK + EXT_DATA_SIZE + ECC_SIZE + CRC_SIZE)  + 500
		self.nand_t_xfer = (1/self.nand_if*1000) * (BYTES_PER_CHUNK + self.extra_data_size + self.ecc_size + self.crc_size) + 500
				
		# time (ns)
		self.nand_t_cna_w = convert_nand_time(nand.find('t_cna_w').text)
		self.nand_t_cna_r = convert_nand_time(nand.find('t_cna_r').text)
		self.nand_t_cna_e = convert_nand_time(nand.find('t_cna_e').text)
		self.nand_t_chk = convert_nand_time(nand.find('t_chk').text)
						
		self.nand_t_read_lsb = convert_nand_time(nand.find('t_read_lsb').text)
		self.nand_t_read_msb = convert_nand_time(nand.find('t_read_msb').text)
		self.nand_t_read_full = convert_nand_time(nand.find('t_read_full').text)
		self.nand_t_read_half = convert_nand_time(nand.find('t_read_half').text)
		self.nand_t_read_slc = convert_nand_time(nand.find('t_read_slc').text)
		self.nand_t_prog_lsb = convert_nand_time(nand.find('t_prog_lsb').text)
		self.nand_t_prog_msb = convert_nand_time(nand.find('t_prog_msb').text)
		if self.bits_per_cell == 2 :
			self.nand_t_prog = (self.nand_t_prog_lsb + self.nand_t_prog_msb)
		else :
			self.nand_t_prog = convert_nand_time(nand.find('t_prog').text)
		self.nand_t_prog_avg = int(self.nand_t_prog / self.bits_per_cell)
		self.nand_t_prog_slc = convert_nand_time(nand.find('t_prog_slc').text)
		self.nand_t_bers = convert_nand_time(nand.find('t_bers').text)
																																																																																																											
	def get_type_value(self) :
		# calculate ssd information
		small_block_size = self.page_size * self.page_num
		big_block_size = small_block_size * self.plane_num
													
		bits_per_cell = ['bits_per_cell', self.bits_per_cell]
		capacity = ['capacity[Gb]', self.size]
		page_size = ['page size[KB]', int(self.page_size / unit.scale_KB)]
		page_num = ['page_num', self.page_num]
		plane_num = ['plane_num', self.plane_num]
		wordline_num = ['wordline_num', int(self.page_num / self.bits_per_cell)]
		block_num = ['block_num', self.main_block_num]
		small_block = ['small block size[MB]', int(small_block_size / unit.scale_MB)]
		big_block = ['big block size[MB]', int(big_block_size / unit.scale_MB)]

		extra_data = ['extra data size', self.extra_data_size]
		crc = ['crc size', self.crc_size]
		ecc = ['ecc size', self.ecc_size]

		nand_type = [bits_per_cell, capacity, page_size, page_num, plane_num, wordline_num, block_num, small_block, big_block, extra_data, crc, ecc]
		return nand_type
		
	def get_param_value(self) :
		interface_speed = ['interface speed [MHz]', self.nand_if]
		t_xfer1 = ['nand_t_xfer(us/4KB)', int(self.nand_t_xfer/1000)]
		
		num_chunks = self.page_size / BYTES_PER_CHUNK * self.plane_num		
		t_xfer2 = ['nand_t_xfer(us/multi-plane)', int(self.nand_t_xfer * num_chunks/1000)]
				
		t_cna_w = ['nand_t_cna_w [us]', self.nand_t_cna_w]
		t_cna_r = ['nand_t_cna_r [us]', self.nand_t_cna_r]
		t_cna_e = ['nand_t_cna_e [us]', self.nand_t_cna_e]
		t_chk = ['nand_t_chk [us]', self.nand_t_chk]

		t_read_f = ['nand_t_read_full [us]' , int(self.nand_t_read_full/1000)]
		t_read_h = ['nand_t_read_half [us]', int(self.nand_t_read_half/1000)]
		t_read_slc = ['nand_t_read_slc [us]', int(self.nand_t_read_slc/1000)]
				
		t_prog = ['nand_t_prog [us]', int(self.nand_t_prog/1000)]
		t_prog_avg = ['nand_t_prog_avg [us]',  int(self.nand_t_prog_avg/1000)]
		t_prog_slc = ['nand_t_prog_slc [us]', int(self.nand_t_prog_slc/1000)]
		
		t_bers = ['nand_t_bers [ms]', int(self.nand_t_bers/1000000)]

		nand_param = [interface_speed, t_xfer1, t_xfer2, t_cna_w, t_cna_r, t_cna_e, t_chk, t_read_f, t_read_h, t_read_slc, t_prog, t_prog_avg, t_prog_slc, t_bers]
		return nand_param																																																																																																							
		
	@report_print																								
	def print_type(self, report_title = 'nand type') :		
		table = self.get_type_value()						
		return report_title, table
		
	@report_print																								
	def print_param(self, report_title = 'nand parameter') :
		table = self.get_param_value()
		return report_title, table
															
if __name__ == '__main__' :
	print('nand configuration')				

	# read list test	
	nand1 = nand_config(nand_256gb_g3)
	print('\n\nnand_256gb_g3 configuration')
	nand1.print_type()
	nand1.print_param()
	
	# read csv file test
	nand1.load_csv('nand_128gb_mlc.csv')
	print('\n\nnand_128gb_mlc.csv configuration')
	nand1.print_type(report_title = 'csv nand type[mlc]')
	nand1.print_param(report_title = 'csv nand parameter[mlc]')	
	
	'''
	# read excel file test
	nand1.load_excel('nand_128gb_mlc.xlsx')
	print('\n\nnand_128gb_mlc.xlsx configuration')
	nand1.print_type(report_title = 'excel nand type[mlc]')
	nand1.print_param(report_title = 'excel nand parameter[mlc]')
	'''
	
	nand1.load_xml('nand_config.xml', '256gb_g3')		
	nand1.print_type(report_title = 'xml nand type[mlc]')
	nand1.print_param(report_title = 'xml nand parameter[mlc]')	
															