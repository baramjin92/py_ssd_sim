#!/usr/bin/python

import os
import sys
import csv
import numpy as np
import matplotlib.pyplot as plt

import datetime
import base64
from io import BytesIO

from config.ssd_param import *

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

BYTES_PER_SECTOR = 512

def plot_result(filename, to_html = False):	
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
		
		if to_html == False:
			#print('plot performance')
			plt.show()
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
				
def build_html(csv_filename, html_filename) :
	html_open(html_filename)
	html_put_header(None)
								
	html_put_str('<br>')
	plot_result(csv_filename)
	html_put_str('<br>')
				
	html_put_end()
	html_close()
																														
if __name__ == '__main__' :
	print ('sim graph init')
	
	#plot_result('sim_20200402_00.csv')
	build_html('sim_20200402_00.csv', 'ssd_sim_test.html')					