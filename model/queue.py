#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.ssd_param import *

def log_print(message) :
	print('[queue] ' + message)

class queue : 
	def __init__(self, depth) :
		self.array = []
		self.depth = depth
		
	def push(self, value) :
		# so far doesn't check availability of queue because python list is powerful
		self.array.append(value)
	
	def push_first(self, value) :
		self.array.insert(0, value)	
				
	def pop(self) :
		data = self.array.pop(0)
		return data
		
	def get_entry_1st(self) :
		return self.array[0]	
		
	def length(self) : 
		return len(self.array)
	
	def get_depth(self) :
		return self.depth	
		
	def isFull(self) :
		if selp.depth == len(self.array) :
			return True
		else :
			return False	
				
def unit_test_queue() :
	q = queue(10)
	
	q.push(3)
	q.push(2)
	
	print('legnth : %d'%(q.length()))
	print(q.pop())
	print(q.pop())				
 																 																 																
if __name__ == '__main__' :
	print ('module queue')			
				
	unit_test_queue()																																	