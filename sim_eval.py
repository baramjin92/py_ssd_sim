#!/usr/bin/python

import os
import sys
import time

from sim_event import *

log_time_start = {'hil':0, 'ftl':0, 'fil':0, 'model':0, 'all':0}
log_time_data = {}

def init_eval_time() :	
	log_time_data['hil'] = 0
	log_time_data['ftl'] = 0
	log_time_data['fil'] = 0
	log_time_data['model'] = 0

	log_time_data['all'] = 0
	log_time_start['all'] = time.time()

def start_eval_module(key) :
	log_time_start[key] = time.time()
	
def end_eval_module(key) :
	log_time_data[key] = log_time_data[key] + (time.time() - log_time_start[key])

def measure_hil_time(func) :
	def measure_hil_time(*args, **kwargs) :
		start_eval_module('hil')
		result = func(*args, **kwargs)
		end_eval_module('hil')
		return result
	
	return measure_hil_time

def measure_ftl_time(func) :
	def measure_ftl_time(*args, **kwargs) :
		start_eval_module('ftl')
		result = func(*args, **kwargs)
		end_eval_module('ftl')
		return result
	
	return measure_ftl_time

def measure_fil_time(func) :
	def measure_fil_time(*args, **kwargs) :
		start_eval_module('fil')
		result = func(*args, **kwargs)
		end_eval_module('fil')
		return result
	
	return measure_fil_time

@report_print
def print_eval_time() :
	total_time = time.time() - log_time_start['all']
	simulation_time = event_mgr.timetick / 1000000000
	report_title = 'run time : %f, simulation time : %f [%d]'%(total_time, simulation_time, total_time/simulation_time)		
	#report_title = report_title + ', max event node : %d'%event_mgr.max_count																												
		
	table = []
	table.append([' ', 'hil', 'ftl', 'fil', 'handler', 'idle'])
						
	if log_time_data['hil'] > 0 and log_time_data['ftl'] > 0 and log_time_data['fil'] > 0 :
		hil = log_time_data['hil']
		ftl = log_time_data['ftl']
		fil = log_time_data['fil']
		handler = log_time_data['model']
		sw = hil + ftl + fil
		idle = total_time - handler - sw
		
		table.append(['time [sec]', str(hil), str(ftl), str(fil), str(handler), str(idle)])
		table.append(['percent', str(hil/total_time*100), str(ftl/total_time*100), str(fil/total_time*100), str(handler/total_time*100), str(idle/total_time*100)])	
		
	return report_title, table																																																																																																																																																																																
if __name__ == '__main__' :
	print ('sim evaluation')
		
	init_eval_time()
	time.sleep(1)
	log_time_data['hil'] = time.time()
	log_time_data['ftl'] = time.time()
	log_time_data['fil'] = time.time()
		
	print_eval_time()																											