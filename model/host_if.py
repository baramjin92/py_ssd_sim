#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.pcie_if import *
from model.sata_if import *

class host_interface :
	def __init__(self) :
		self.interface = None

	def set_config(self, host_if, gen, lane) :
		if host_if == 'PCIE' :
			self.interface = pcie(gen, lane)
		elif host_if == 'SATA' :
			self.interface = sata()
		
		self.calculate_xfer_time = self.interface.calculate_xfer_time
		self.min_packet_size = self.interface.min_packet_size
		
	def info(self) :
		self.interface.info()
							
host_if = host_interface()
host_if.set_config('PCIE', 3, 4)																																													

# register callback funtion
#calculate_xfer_time = host_if.calculate_xfer_time
#min_packet_size = host_if.min_packet_size

if __name__ == '__main__' :
	host_if.set_config('PCIE', 4, 4)																																													
	host_if.info()
	
	host_if.set_config('SATA', 3, 1)
	host_if.info()
	
																																			