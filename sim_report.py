#!/usr/bin/python

import os
import sys
import csv
import numpy as np
import matplotlib.pyplot as plt

import datetime
import base64
from io import BytesIO

from model.host import *
from model.hic import hic_manager

from model.nand import nand_manager
from model.nfc import nfc

from model.hil import hil_manager
from model.ftl import *
from model.fil import fil_manager
from model.nand import *

from model.workload import *

from config.ssd_param import *

from sim_event import *

ENABLE_PERF_MONITOR = False

def check_perf_monitor(func) :
	def check_perf_monitor(*args, **kwargs) :
		if ENABLE_PERF_MONITOR == False :
			return 0
			
		result = func(*args, **kwargs)
		
		return result

	return check_perf_monitor


html_fp = None

def html_open(filename) :
	global html_fp
	
	if os.path.isfile(filename) :
		os.remove(filename)
	
	html_fp = open(filename, 'w')
	
def html_close() :
	global html_fp
	
	if html_fp != None :
		html_fp.close()
		html_fp = None
	
def html_put_str(str) :
	html_fp.write(str)
		
def html_put_header(title) :
	html_string_start = '''
	<html>
		<head><title>Report Title</title></head>
		<link rel = "stylesheet" type = "text/css" href = "mystyle.css"/>
		<body>
	'''
	
	html_fp.write(html_string_start)
	
def html_put_end() :		
	html_string_end = '''
		</body>
	</html>
	'''
	html_fp.write(html_string_end)	
		
def html_put_table(dataframe) :
	fp = html_fp

	if type(dataframe) is str :
		str1 = '<h5>'+dataframe
		fp.write(str1)
	else :			 	
		fp.write('<center>')
		fp.write('<table>')
		for header in dataframe.columns.values :
			fp.write('<th>'+str(header)+'</th>')
		for i in range(len(dataframe)) :
			fp.write('<tr>')
			for col in dataframe.columns :
				value = dataframe.iloc[i][col]
				fp.write('<td style="text-align:right;">' + str(value) + '</td>')
			fp.write('</tr>')
		fp.write('</table>')
		fp.write('</center>')

@check_perf_monitor
def plot_result(filename):	
	times = []
	write_throughput = []
	read_throughput = []

	unit = BYTES_PER_SECTOR / (1024*1024)	
	with open(filename, newline='') as csvfile :
		performances = csv.reader(csvfile, delimiter=',')

		# heading information
		performance_line = next(performances)

		# main information
		for index, performance_line in enumerate(performances) :
			time = float(performance_line[0]) / 1000000000			
			times.append(time)
			write_throughput.append((float(performance_line[1]) * unit) / time)
			read_throughput.append((float(performance_line[2]) * unit) / time)

		plt.clf()
						
		dot_size = 8
		plot_color = ['b', 'y']
		plot_label = ['write', 'read']		
		
		#size = len(lba)
		i = 0				
		plt.scatter(times, write_throughput, s=dot_size, c=plot_color[i], label=plot_label[i])
		i = 1				
		plt.scatter(times, read_throughput, s=dot_size, c=plot_color[i], label=plot_label[i])
		
		#plt.xscale('log')
		plt.legend(loc='upper right')
		plt.xlabel('time')
		plt.ylabel('throughput [MB/s]')
		plt.title('performance :' + filename)
		
		tmpfile = BytesIO()
		
		if False :
			print('plot performance')
			#plt.show()
		else :		
			plt.savefig(tmpfile, format='png')
			encoded = base64.b64encode(tmpfile.getvalue()).decode('utf-8')
			html = '<img src=\'data:image/png;base64, {}\'>'.format(encoded)
			
			#with open('test.html', 'w') as f :
			#	html_put_header(f, None)
			#	f.write(html)
			#	html_put_end(f)
			html_fp.write('<center>')																								
			html_fp.write(html)
			html_fp.write('</center>')

class report_manager :
	def __init__(self) :
		# 0.0001 sec
		self.interval = 1000000

		self.log_enable = False
		self.log_filename = None
		self.fp = None
		self.csv_wr = None
		self.log_list = []
		
		self.html_fp = None

		self.workload = None

		self.host_model = None
		self.hic_model = None
		self.nfc_model = None
		self.nand_model = None

		self.hil_module = None 
		self.ftl_module = None
		self.fil_module = None
	
	@check_perf_monitor											
	def open(self, seq_no) :								
		# prepare the csv file for recoding workload
		today = datetime.datetime.today()
		#self.log_filename = 'sim_%04d%02d%02d_%08d_%02d.csv'%(today.year, today.month, today.day, (today.hour*today.minute*today.second), seq_no)
		self.log_filename = 'sim_%04d%02d%02d_%02d.csv'%(today.year, today.month, today.day, seq_no)
		
		if os.path.isfile(self.log_filename) :
			os.remove(self.log_filename)
			
		self.fp = open(self.log_filename, 'w', encoding='utf-8')
		self.csv_wr = csv.writer(self.fp)
		#self.csv_wr.writerow(['time', 'write sectors', 'write latency[max]', 'write latency[min]', 'read sectors', 'read latency[max]', 'read latency[min]'])
		self.csv_wr.writerow(['time', 'write sectors', 'read sectors'])
	
		self.log_enable = True
			
		# 0.1 second
		node = event_mgr.alloc_new_event(self.interval)
		node.dest = event_dst.MODEL_KERNEL
		node.code = event_id.EVENT_RESULT
	
	@check_perf_monitor
	def close(self) :
		if len(self.log_list) > 0 :				
	
			for log_entry in self.log_list :			
				self.csv_wr.writerow(log_entry)
			self.log_list.clear()
		
		if self.fp != None :
			self.fp.close()
			
		self.log_enable = False

	@check_perf_monitor
	def log(self, event, host_stat) :					
		if event.code == event_id.EVENT_RESULT:	
			if self.fp == None :
					open()

			perf_sum = host_stat_param()
			queue_depth = len(host_stat.perf)
			for queue_perf in host_stat.perf :
				perf_sum.num_write_sectors = queue_perf.num_write_sectors 
				perf_sum.num_read_sectors = queue_perf.num_read_sectors
	
			#num_write_sectors = perf_sum.num_write_sectors / queue_depth				
			#num_read_sectors = perf_sum.num_read_sectors / queue_depth
																					
			cur_time = event.time
			#log_entry = [cur_time, num_write_sectors, perf.max_write_latency, perf.min_write_latency, num_read_sectors, perf.max_read_latency, perf.min_read_latency]
			log_entry = [cur_time, perf_sum.num_write_sectors, perf_sum.num_read_sectors]
			self.log_list.append(log_entry)
			
			if len(self.log_list) >= 100 :				
				for log_entry in self.log_list :			
					self.csv_wr.writerow(log_entry)
				self.log_list.clear()

		if self.log_enable == True :
			node = event_mgr.alloc_new_event(self.interval)
			node.dest = event_dst.MODEL_KERNEL
			node.code = event_id.EVENT_RESULT									
	
	def disable(self) :
		self.log_enable  = False
	
	def set_model(self, workload, host, hic, nfc, nand) :
		self.workload = workload
		self.host_model = host
		self.hic_model = hic
		self.nfc_model = nfc
		self.nand_model = nand

	def set_module(self, hil, ftl, fil) :
		self.hil_module = hil 
		self.ftl_module = ftl
		self.fil_module = fil		

	def show_result(self) :
		if self.host_model != None :
			self.host_model.host_stat.print(event_mgr.timetick)			
		
		if self.nfc_model != None :
			#self.nfc_model.print_cmd_descriptor()
			self.nfc_model.print_ch_statistics()
			self.nfc_model.print_way_statistics()
		
		#host_model.print_host_data(2048,512)	#(0, 128)		
		if self.ftl_module != None :
			if self.ftl_module.name == 'conventional' :
				blk_grp.debug(meta)
				blk_manager = blk_grp.get_block_manager_by_name('user')
				blk_manager.debug_valid_block_info(meta)
													
				self.ftl_module.host_sb.debug()
				self.ftl_module.gc_sb.debug()
			elif self.ftl_module.name == 'zns' :
				self.ftl_module.zone_debug()
	
	def show_debug_info(self) :
		if self.ftl_module != None and self.ftl_module.name == 'conventional' :
			# print mapping table
			lba_start = 0
			sector_num = 128									
			meta.print_map_table(lba_start, sector_num)
			
			# print valid data info of host super block
			way = 0
			block = self.ftl_module.host_sb.get_block_addr()
			meta.print_valid_data(way, block)
	
		if self.nand_model != None :
			lba_index = 0			
			map_entry = meta.map_table[lba_index]
			way = int(map_entry / CHUNKS_PER_WAY)
			address = int((map_entry % CHUNKS_PER_WAY) / CHUNKS_PER_PAGE) * CHUNKS_PER_PAGE	
						
			nand = self.nand_model.nand_ctx[way]
	
			nand_block = int(address / CHUNKS_PER_BLOCK) 
			nand_page = int((address % CHUNKS_PER_BLOCK) / CHUNKS_PER_PAGE)
					
			nand.print_block_data(nand_block, nand_page, nand_page + 2)			
				
	def build_html(self, include_graph = False) :
		html_open('ssd_sim_report.html')
		html_put_header(None)
					
		if self.workload != None :
			html_put_str('<h2> workload')
			html_put_str('<hr>')
			index, num = self.workload.get_info()
			self.workload.print_current(index, html_put_table)			
											
		if self.host_model != None :
			html_put_str('<h2> performance')
			html_put_str('<hr>')
			self.host_model.host_stat.show_performance(event_mgr.timetick, html_put_table)			
			
			if include_graph == True :
				html_put_str('<br>')
				plot_result(self.log_filename)
				html_put_str('<br>')
				
			html_put_str('<h2> host statistics')
			html_put_str('<hr>')
			self.host_model.host_stat.print(event_mgr.timetick, html_put_table)			
				
		if self.nfc_model != None :
			#self.nfc_model.print_cmd_descriptor()
			html_put_str('<h2> nand channel statistics')
			html_put_str('<hr>')
			self.nfc_model.print_ch_statistics(html_put_table)
				
			html_put_str('<h2> nand way statistics')
			html_put_str('<hr>')
			self.nfc_model.print_way_statistics(html_put_table)

		html_put_end()
		html_close()
																																																								
report = report_manager()
																														
if __name__ == '__main__' :
	print ('sim result init')
	
	host_model = host_manager(NUM_HOST_CMD_TABLE)
	hic_model = hic_manager(NUM_CMD_EXEC_TABLE * NUM_HOST_QUEUE)
	
	nand_model = nand_manager(NUM_WAYS, nand_info)
	nfc_model = nfc(NUM_CHANNELS, WAYS_PER_CHANNELS)

	#meta.config(NUM_WAYS)
	blk_grp.add('meta', block_manager(NUM_WAYS, 1, 9))
	blk_grp.add('slc_cache', block_manager(NUM_WAYS, 10, 19, 1, 2))
	blk_grp.add('user', block_manager(NUM_WAYS, 20, 100, FREE_BLOCKS_THRESHOLD_LOW, FREE_BLOCKS_THRESHOLD_HIGH))
				
	host_stat = host_statistics(2)

	report.set_model(None, host_model, hic_model, nfc_model, nand_model)		
	report.open(0)
								
	node = event_mgr.alloc_new_event(10)
	node.dest = event_dst.MODEL_KERNEL
	node.code = event_id.EVENT_RESULT												
	report.log(node, host_stat)
	
	node = event_mgr.alloc_new_event(100)
	node.dest = event_dst.MODEL_KERNEL
	node.code = event_id.EVENT_RESULT									
	report.log(node, host_stat)
		
	report.show_result()
	
	report.build_html(False)								
	#result.open('test.csv')
	#result.print(0, 0, 'event', 'test1')
	#result.print(0, 0, 'nfc', 'test2')
	#result.print(0, 0, 'nand', 'test2')
	#result.close()						