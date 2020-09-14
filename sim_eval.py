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

def print_eval_time() :
	total_time = time.time() - log_time_start['all']
	print('\nsimulation time : %f'%total_time)		
				
	if log_time_data['hil'] > 0 and log_time_data['ftl'] > 0 and log_time_data['fil'] > 0 :
		sw_time0 = log_time_data['hil']
		sw_time1 = log_time_data['ftl']
		sw_time2 = log_time_data['fil']
		handler_time = log_time_data['model']
		sw_time = sw_time0+sw_time1+sw_time2
		print('sw time : %f(%f, %f, %f), handler time : %f'%(sw_time, sw_time0, sw_time1, sw_time2, handler_time))
		print('sw time : %f %%(%f, %f, %f), handler time : %f %%'%(sw_time/total_time*100, sw_time0/sw_time*100, sw_time1/sw_time*100, sw_time2/sw_time*100, handler_time/total_time*100))
		print('\n')
																														
if __name__ == '__main__' :
	print ('sim evaluation')
		
	init_eval_time()
	time.sleep(1)
	log_time_data['hil'] = time.time()
	log_time_data['ftl'] = time.time()
	log_time_data['fil'] = time.time()
		
	print_eval_time()																											