#!/usr/bin/python

import os
import sys
import random
import numpy as np
import pandas as pd

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.queue import *

from sim_event import *

def log_print(message) :
	event_log_print('[ftl]', message)

# 'hil2ftl_high/low_queue' conveys ftl_cmd_desc
# hil created entry of ftl_cmd_desc and send it via 'hil2ftl_high/low_qeueu'
# ftl get entry of ftl_cmd_desc from these queues
# ftl has another queue like 'write_cmd_queue' in order to gather write command 
class ftl_cmd_desc :
	def __init__(self) :
		self.qid = 0					# qid can have queue id, zone id, stream id and so on. 
		self.cmd_tag = 0
		self.code = 0
		self.lba = 0
		self.sector_count = 0

# initialize hil2ftl queue 
# hil2ftl_high/low_queue conveys ftl_cmd_desc
# ftl_cmd_desc is defined in the ftl.py
hil2ftl_high_queue = queue(FTL_CMD_QUEUE_DEPTH)
hil2ftl_low_queue = queue(FTL_CMD_QUEUE_DEPTH)

# initialize ftl2fil queue
# ftl2fil_queue conveys cmd_index of nandcmd_table
ftl2fil_queue = queue(32)

# initialize fil2ftl queue
# fil2ftl queue conveys gc contents
fil2ftl_queue = queue(32) 																
 																																				 																																				
if __name__ == '__main__' :
	print ('module ftl (flash translation layer) common')
	
																			