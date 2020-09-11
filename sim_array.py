#!/usr/bin/python

import os
import sys

import numpy as np

ENABLE_NUMPY = False

def make_1d_array(size, init_value = 0, use_numpy = ENABLE_NUMPY) :
	if use_numpy == True :
		print('make 1d array with numpy')
		arr = np.empty((size), np.int32)
		#for index in range(size) :
		#	arr[index] = init_value
			
		return arr
	else :
		return [init_value for x in range(size)]

#array[row][col]
def make_2d_array(row, col, init_value = 0, use_numpy = ENABLE_NUMPY) :
		if use_numpy == True :
			return np.empty((row, col), np.uint32)
		else :
			return [[init_value for y in range(col)] for x in range(row)]

#array[row][col][depth]
def make_3d_array(row, col, depth, init_value = 0, use_numpy = ENABLE_NUMPY) :
		if use_numpy == True :
			return np.empty((row, col, depth), np.uint32)
		else :
			return [[[init_value for z in range(depth)] for y in range(col)] for x in range(row)]		
																																																												
if __name__ == '__main__' :
	print ('sim array')
		
	a = make_1d_array(10)
	a[0] = 1
	a[2] = 2
	print(a)

	b = make_2d_array(10, 5)
	b[0][0] = 10
	b[2][1] = 20
	print(b)

	c = make_3d_array(10, 5, 2)
	c[0][0][0] = 100
	c[2][1][1] = 200
	print(c)
																												