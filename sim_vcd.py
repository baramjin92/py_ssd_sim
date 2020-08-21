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

format_str = ['00b', '01b', '02b', '03b', '04b', '05b', '06b', '07b', '08b']

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
		self.variables = {}
		
		self.time = -1						

		self.str_buf = ''

	#@enable_console
	def vprint(self, message) :
		self.str_buf = self.str_buf + message+'\n'
		
		if len(self.str_buf) > 1000 and self.fp != None :
			self.fp.write(self.str_buf)
			self.str_buf = ''
	
	def vflush(self) :
		if len(self.str_buf) > 0 and self.fp != None :
			self.fp.write(self.str_buf)
			self.str_buf = ''
																																																											
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
		self.vflush()
		
		if self.fp == None :
			self.fp.close()

	def add_module(self, module) :
		self.modules.append(module)

	def add_variable(self, var) :
		self.variables[var.symbol] = var

	def set_value(self, symbol, value) :	
		if self.variables[symbol].size == 1 :
			if self.variables[symbol].type == 'real' and value != 'x' :
				str = 'r%s %s'%(value, symbol)
			else :
				str = '%s%s'%(value, symbol)
		else :
			str = '%s %s'%(value, symbol)
			
		self.vprint(str)

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
		self.vflush()
		
	def make_variable(self, module) :
		if len(self.modules) == 0 :
			return
		
		if module in self.modules :		
			self.vprint('$scope module %s $end'%module)
							
			for key in self.variables :
				var = self.variables[key]
				if var.module == module:
					self.vprint('$var %s %d %s %s $end'%(var.type, var.size, var.symbol, var.name))	
	
			self.vprint('$upscope $end')

		self.vflush()			
				
	def make_init_state(self) :
		self.vprint('$enddefinitions $end')
		self.vprint('$dumpvars')																																												
		
		for index, key in enumerate(self.variables) :
			var = self.variables[key]
			self.set_value(var.symbol, var.init_val)
			
		self.vprint('$end')
		self.vflush()																																															
					
	def change_state(self, time, symbol, value) :
		if self.time != time :
			self.vprint('#%d'%time)
			self.time = time

		self.set_value(symbol, value)

	def change_binary(self, time, symbol, value) :
		if self.time != time :
			self.vprint('#%d'%time)
			self.time = time

		str = 'b%s %s'%(format(value, format_str[self.variables[symbol].size]), symbol)			
		self.vprint(str)																																																																						
												
if __name__ == '__main__' :
	# in order to show data, please enable 'enable_console' in vprint()
	
	print ('sim vcd init')
	print ('==========')

	vcd = vcd_manager()
	vcd.open('test_vcd.vcd')
	
	vcd.set_date()
	vcd.set_version('python ssd simulator vcd')
	vcd.set_comment('developed by yong jin')
	vcd.set_time_scale('1ps')

	vcd.add_module('logic')
	vcd.add_variable(vcd_variable('wire', 8, '#', 'data', 'bxxxxxxxx', 'logic'))
	vcd.add_variable(vcd_variable('real', 1, '$', 'data_valid', 'x', 'logic'))
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
	vcd.change_state(2296, '$', '1')
	vcd.change_state(2302, '$', '0')
	vcd.change_binary(2310, '#', 12)		

	vcd.close()