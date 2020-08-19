#!/usr/bin/python

import os
import sys
import datetime

def enable_console(func) :
	def enable_console(*args, **kwargs) :
		print(args[1])
		result = func(*args, **kwargs)
		return result
	
	return enable_console

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

		self.date = datetime.datetime.today()
		self.version = 'python vcd tool'
		self.comment = 'developed by yong jin'
		self.time_scale = '1us'		

		self.modules = []
		self.variables = []
		
		self.time = -1						

	@enable_console
	def vprint(self, message) :
		if self.fp != None :
			self.fp.write(message)
			self.fp.write('\n')
																																																																			
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
	
	def close(self) :
		if self.fp == None :
			self.fp.close()

	def add_module(self, module) :
		self.modules.append(module)

	def add_variable(self, var) :
		self.variables.append(var)

	def make_header(self) :
		self.vprint('$date')
		self.vprint('\t' + self.date.strftime('%c'))
		self.vprint('$end')													

		self.vprint('$version')
		self.vprint('\t' + self.version)
		self.vprint('$end')													
																														
		self.vprint('$comment')
		self.vprint('\t' + self.comment)
		self.vprint('$end')													

		self.vprint('$timescale %s $end'%(self.time_scale))
		
	def make_variable(self, module) :
		
		if len(self.modules) == 0 :
			return
		
		if module in self.modules :		
			self.vprint('$scope module %s $end'%module)
							
			for var in self.variables :
				if var.module == module:
					self.vprint('$var %s %d %s %s $end'%(var.type, var.size, var.symbol, var.name))	
	
			self.vprint('$upscope $end')
	
	def make_init_state(self) :
		self.vprint('$enddefinitions $end')
		self.vprint('$dumpvars')																																												
		
		for index, var in enumerate(self.variables) :
			if len(var.init_val) > 1 :
				self.vprint('%s %s'%(var.init_val, var.symbol))
			else :
				self.vprint('%s%s'%(var.init_val, var.symbol))	

		self.vprint('$end')																																															
		
	def change_state(self, time, symbol, value) :
		if self.time != time :
			self.vprint('#%d'%time)
			self.time = time
		
		if len(value) > 1 :
			self.vprint('%s %s'%(value, symbol))
		else :
			self.vprint('%s%s'%(value, symbol))																																																																				
if __name__ == '__main__' :
	# in order to show data, please enable 'enable_console' in vprint()
	
	print ('sim vcd init')
	print ('==========')

	vcd = vcd_manager()
	vcd.open('test_vcd.txt')
	
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

	vcd.close()