#!/usr/bin/python

import os
import sys
import time

from model.workload import *

from progress.bar import Bar

class sim_status : 
	def __init__(self) :
		self.debug = ''
		self.log = ''
		self.progress = 0

class util_progress :
	def __init__(self, callback = None) :
		self.bar = None
		self.progress_save = 0
		self.progress_next = callback
		if self.progress_next == None :
			self.progress_next = self.do_next		
		
	def reset(self, wlm) :				
		index, total_num = wlm.get_info()
		workload_title = 'workload [%d/%d] processing'%(index+1, total_num)
		
		self.progress_save = 0

		self.bar = Bar(workload_title, max=100)
		
		return index
		
	def check(self, wlm) :		
		progress = wlm.get_progress(async_group = False)
		if self.progress_save != progress :
			self.progress_save = progress
			
			self.do_next(progress)
				
		return progress+1
		
	def done(self) :
		self.bar.finish()
		
	def do_next(self, value) :
		self.bar.index = value
		self.bar.next()
					  					  