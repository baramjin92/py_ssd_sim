#!/usr/bin/python

import os
import sys
import datetime

def vcd_print(message) :
	print(message)

class vcd_variable :
	def __init__(self, type, size, symbol, name, init_value, module) :
		self.type = type
		self.size = size
		self.symbol = symbol
		self.name = name
		self.init_val = init_value
		self.module = module

class vcd_manager :
	def __init__(self) :
		self.fp = None
		self.csv_wr = None

		self.date = datetime.datetime.today()
		self.version = 'python vcd tool'
		self.comment = 'developed by yong jin'
		self.time_scale = '1us'		

		self.modules = []
		self.variables = []
		
		self.time = -1						
																		
	def set_date(self) :
		self.date = datetime.datetime.today()	
		
	def set_version(self, version) :
		self.version = version	
		
	def set_comment(self, comment) :
		self.comment = comment	
		
	def set_time_scale(self, time_scale) :
		# 1ps, 1ns, 1us, ...
		self.time_scale = time_scale	
		
	def open(self, filename) :
		if filename == None :
			return
			
		# prepare the csv file for recoding workload
		if os.path.isfile(filename) :
			os.remove(filename)
			
		self.fp = open(filename, 'w', encoding='utf-8')
		self.csv_wr = csv.writer(self.fp)
		self.csv_wr.writerow(['time', 'time gap', 'tag', 'log'])
	
	def close(self) :
		if self.fp == None :
			self.fp.close()

	def add_module(self, module) :
		self.modules.append(module)

	def add_variable(self, var) :
		self.variables.append(var)

	def make_header(self) :
		vcd_print('$date')
		vcd_print('\t' + self.date.strftime('%c'))
		vcd_print('$end')													

		vcd_print('$version')
		vcd_print('\t' + self.version)
		vcd_print('$end')													
																														
		vcd_print('$comment')
		vcd_print('\t' + self.comment)
		vcd_print('$end')													

		vcd_print('$timescale %s $end'%(self.time_scale))
		
	def make_variable(self, module) :
		
		if len(self.modules) == 0 :
			return
		
		if module in self.modules :		
			vcd_print('$scope module %s $end'%module)
							
			for var in self.variables :
				if var.module == module:
					vcd_print('$var %s %d %s %s $end'%(var.type, var.size, var.symbol, var.name))	
	
			vcd_print('$upscope $end')
	
	def make_init_state(self) :
		vcd_print('$enddefinitions $end')
		vcd_print('$dumpvars')																																												
		
		for index in range(len(self.variables)) :
			var = self.variables[index]
			if len(var.init_val) > 1 :
				vcd_print('%s %s'%(var.init_val, var.symbol))
			else :
				vcd_print('%s%s'%(var.init_val, var.symbol))	

		vcd_print('$end')																																															
		
	def change_state(self, time, symbol, value) :
		if self.time != time :
			vcd_print('#%d'%time)
			self.time = time
		
		if len(value) > 1 :
			vcd_print('%s %s'%(value, symbol))
		else :
			vcd_print('%s%s'%(value, symbol))																																																																				
if __name__ == '__main__' :
	vcd_print ('sim vcd init')

	vcd = vcd_manager()
	vcd.set_date()
	vcd.set_version('python ssd simulator vcd')
	vcd.set_comment('developed by yong jin')
	vcd.set_time_scale('1ps')

	vcd.add_module('logic')
	vcd.add_variable(vcd_variable('wire', 8, '#', 'data', 'bxxxxxxxx', 'logic'))
	vcd.add_variable(vcd_variable('wire', 1, '$', 'data_valid', 'x', 'logic'))
	vcd.add_variable(vcd_variable('wire', 1, '%', 'en', '0', 'logic'))
	vcd.add_variable(vcd_variable('wire', 1, '&', 'rx_en', 'x', 'logic'))
	vcd.add_variable(vcd_variable('wire', 1, '*', 'tx_en', 'x', 'logic'))
	vcd.add_variable(vcd_variable('wire', 1, '(', 'empty', '1', 'logic'))
	vcd.add_variable(vcd_variable('wire', 1, ')', 'underrun', '0', 'logic'))
	
	vcd.make_header()
	vcd.make_variable('logic')	
	vcd.make_init_state()						
	
	vcd.change_state(0, '#', 'b10000001')
	vcd.change_state(0, '$', '0')
	vcd.change_state(0, '*', '1')
	vcd.change_state(2211, '*', '0')
	vcd.change_state(2296, '#', 'b0')
	vcd.change_state(2296, '$ ', '1')
	vcd.change_state(2302, '$', '0')	
