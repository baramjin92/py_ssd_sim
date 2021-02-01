#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from model.buffer import *

from config.ssd_param import *

def log_print(message) :
	print('[cache] ' + message)

CACHE_SIZE = 1024

class buffer_cache : 
	def __init__(self, length) :
		self.lba = []
		self.buffer_id = []
		self.hit_ratio = []
		self.length = length
		
	def add(self, lba, buffer_id) :
		evict_buffer_id = -1
				
		# check full and eviction		
		cache_length = len(self.lba)
		if cache_length >= self.length :
			index = cache_length - 1
			
			evict_lba = self.lba.pop(index)
			evict_buffer_id = self.buffer_id.pop(index)
			evict_hit_ratio = self.hit_ratio.pop(index)
						
		# add buffer_id to cache
		try :
			index = self.hit_ratio.index(0)
			
			self.lba.insert(index, lba)
			self.buffer_id.insert(index, buffer_id)
			self.hit_ratio.insert(index, 0)		
		except :
			self.lba.append(lba)
			self.buffer_id.append(buffer_id)
			self.hit_ratio.append(0)		
					
		# release or return evict buffer id
		if evict_buffer_id != -1 :
			#log_print('evict buffer %d from cache'%(evict_buffer_id))
			
			# bm is global variabl for buffer management
			bm.release_buffer(evict_buffer_id)

	# evict buffer_id from cache by lba
	def evict(self, lba) :
		evict_buffer_id = -1
				
		# check full and eviction
		try :
			hit_index = self.lba.index(lba, 0)

			evict_lba = self.lba.pop(hit_index)
			evict_buffer_id = self.buffer_id.pop(hit_index)
			evict_hit_ratio = self.hit_ratio.pop(hit_index)
			
			#log_print('evict buffer %d from cache'%(evict_buffer_id))
			
			# bm is global variabl for buffer management
			bm.release_buffer(evict_buffer_id)			
			return True			
		except :
			return False
				
	# check_hit function only check existence of lba, it doesn't affect 									
	def check_hit(self, lba) :
		try :
			hit_index = self.lba.index(lba, 0)
		except :
			return -1, False
		
		return hit_index, True
		
	def get_buffer_id(self, lba) :
		index, is_hit = self.check_hit(lba)
		
		if is_hit == True :
			hit_lba = self.lba.pop(index)
			hit_buffer_id = self.buffer_id.pop(index)
			hit_ratio = self.hit_ratio.pop(index)
			
			max_hit_ratio = self.hit_ratio[0]
			
			hit_index = -1
			for hit_count in range(hit_ratio, max_hit_ratio) :
				try :
					hit_index = self.hit_ratio.index(hit_count)
					self.lba.insert(hit_index, hit_lba)
					self.buffer_id.insert(hit_index, hit_buffer_id)
					self.hit_ratio.insert(hit_index, hit_ratio+1)
					break		
				except :
					hit_index = -1
					
			if hit_index == -1 :
				self.lba.insert(0, hit_lba)
				self.buffer_id.insert(0, hit_buffer_id)
				self.hit_ratio.insert(0, hit_ratio+1)
			
			#log_print('cache hit - lba : %d'%hit_lba)																
			return hit_buffer_id, True
		else :
			return -1, False									
						
	def replace_buffer_id(self, lba, new_buffer_id) :
		index, is_hit = self.check_hit(lba)
		
		if is_hit == True :
			buffer_id = self.buffer_id[index]
			self.buffer_id[index] = new_buffer_id
			
			# release old buffer_id
			bm.release_buffer(buffer_id)
			return True
		else :
			return False																																																																																																																											
	def isFull(self) :
		if selp.length == len(self.lba) :
			return True
		else :
			return False	

	def debug(self) :
		print('\nlba : ')
		print(self.lba)
				 																 																 																
		print('buffer_id : ')
		print(self.buffer_id)
		
		print('hit_ratio : ')
		print(self.hit_ratio)

def unit_test_cache() :																 																																 						
	cache = buffer_cache(20)

	print('\nadd test 20 slots')
	buf_ids, ret_val = bm.get_buffer(BM_READ, 0, 0, 20)
			
	lba = 0		
	for buf_id in buf_ids :
		cache.add(lba, buf_id)
		lba = lba + 8
		  		
	cache.debug()  		
		 
	print('\nadd test 4 slots')		  		 		
	buf_ids, ret_val = bm.get_buffer(BM_READ, 0, 0, 4)	  		  		

	lba = 100		
	for buf_id in buf_ids :
		cache.add(lba, buf_id)
		lba = lba + 8
		  		  		  		  		
	cache.debug()

	print('\nhit check 1')
	for lba in range(16, 100, 8) :
		cache.get_buffer_id(lba)
		
	cache.debug()	

	print('\nhit check 2')
	for lba in range(32, 80, 8) :
		cache.get_buffer_id(lba)
		
	cache.debug()	

	print('\nreplace buffer id')																																							
	buf_ids, ret_val = bm.get_buffer(BM_READ, 0, 0, 4)	  		  		

	lba = 88		
	for buf_id in buf_ids :
		cache.replace_buffer_id(lba, buf_id)
		lba = lba + 8
		
	cache.debug()

	print('\nadd test 4 slots')
	buf_ids, ret_val = bm.get_buffer(BM_READ, 0, 0, 4)	  		  		

	lba = 200		
	for buf_id in buf_ids :
		cache.add(lba, buf_id)
		lba = lba + 8
		  		  		  		  		
	cache.debug()
	
	print('\nget buffer id test')

	lba = 100		
	for index in range(8) :
		buf_id, result = cache.get_buffer_id(lba)
		if result == True :
			print('cache hit - lba : %d, buffer_id : %d'%(lba, buf_id))
		else :
			print('cache miss - lba : %d'%lba)

		lba = lba + 8
		  		  		  		  		
	cache.debug()

	print('\nevict buffer id')
	lba = 0
	for index in range(10) :
		result = cache.evict(lba)

		if result == True :
			print('evict - lba : %d'%lba)
		else :
			print('cache miss - lba : %d'%lba)

		lba = lba + 8

bm_cache = buffer_cache(ssd_param.SSD_BUFFER_CACHE_NUM)
																				
if __name__ == '__main__' :
	print ('module buffer cache')

	unit_test_cache()																																																																																																																																																																																																															