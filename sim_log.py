#!/usr/bin/python

import os
import sys
import csv

from config.ssd_param import *

# ENABLE_CONSOLE_LOG is defined in ssd_param.py

class log_manager :
	def __init__(self) :
		self.console_log = False
		self.fp = None
		self.csv_wr = None
		
	def open(self, filename, console_log = False) :
		self.console_log = console_log
		
		if filename == None :
			return
			
		# prepare the csv file for recoding workload
		if os.path.isfile(filename) :
			os.remove(filename)
			
		self.fp = open(filename, 'w', encoding='utf-8')
		self.csv_wr = csv.writer(self.fp)
		self.csv_wr.writerow(['time', 'time gap', 'tag', 'log'])
	
	def close(self) :
		if self.fp != None :
			self.fp.close()
							
	def print(self, cur_time, prev_time, tag, message) :
		time_gap = cur_time - prev_time
		
		if self.console_log == True :
			print('%08d, %08d, %s, %s' %(cur_time, time_gap, tag, message))
		
		if self.csv_wr != None :
			self.csv_wr.writerow([cur_time, time_gap, tag, message])
								
log = log_manager()
																														
if __name__ == '__main__' :
	print ('sim log init')
	
	log.open('test.csv')
	log.print(0, 0, 'event', 'test1')
	log.print(0, 0, 'nfc', 'test2')
	log.print(0, 0, 'nand', 'test2')
	log.close()						