#!/usr/bin/python

import os
import sys

# in order to import module from parent path
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from config.sim_config import unit
from config.ssd_param import *

from model.pcie_if import *
from model.sata_if import *

host_if = pcie(3, 4)									

calculate_xfer_time = host_if.calculate_xfer_time
min_packet_size = host_if.min_packet_size

if __name__ == '__main__' :
	host_if = pcie(4, 4)																																													
	host_if.info()
	
	host_if = sata()
	host_if.info()
	
																																			