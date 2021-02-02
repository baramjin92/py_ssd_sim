#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.pcie_if import *
from model.sata_if import *
from model.ufs_if import *

class host_interface :
	def __init__(self) :
		self.interface = None

	def set_config(self, host_if, gen, lane, mps) :
		if host_if == 'PCIE' :
			self.interface = pcie(gen, lane, mps)
		elif host_if == 'SATA' :
			self.interface = sata()
		elif host_if == 'UFS' :
			self.interface = ufs(gen, lane)
		
		self.set_latency_callback(True)
		self.min_packet_size = self.interface.min_packet_size	
		
	def use_no_latency(self, num_sectors) :
		return 1, 1
				
	def set_latency_callback(self, enable = True) :
		if enable == True :
			self.calculate_xfer_time = self.interface.calculate_xfer_time
		else :																						
			self.calculate_xfer_time = self.use_no_latency
												
		self.cmd_packet_xfer_time = self.interface.cmd_packet_xfer_time
		self.rqt_packet_xfer_time = self.interface.rqt_packet_xfer_time												
												
	def info(self) :
		self.interface.info()
							
host_if = host_interface()
host_if.set_config('PCIE', 3, 4, 256)																																													

if __name__ == '__main__' :
	host_if.set_config('PCIE', 4, 4, 256)																																													
	host_if.info()
	
	host_if.set_config('SATA', 3, 1, 0)
	host_if.info()
	
	host_if.set_config('UFS', 3, 2, 0)
	host_if.info()
																																			