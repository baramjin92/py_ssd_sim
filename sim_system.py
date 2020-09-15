#!/usr/bin/python

import os
import sys
import time

from model.ftl import *

from sim_event import *

hw_controller = {
	'workload' : None,
	'host' : None,
	'hic' : None,
	'nfc' : None,
	'nand' : None,
}

fw_module = {
	'hil' : None,
	'ftl' : None,
	'fil' : None,
}

def set_ctrl(key, model) :	
	hw_controller[key] = model

def get_ctrl(key) :
	return hw_controller[key]	

def set_fw(key, module) :	
	fw_module[key] = module

def get_fw(key) :
	return fw_module[key]	

def save_meta() :
	print('number of meta entries : %d'%NUM_LBA)
	print('size of map : %d'%len(meta.map_table))
																																																												
if __name__ == '__main__' :
	print ('sim system')
	
	save_meta()
																													