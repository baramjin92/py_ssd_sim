import sys
import os
from random import randint

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

#QWidget, QGridLayout, QLabel
from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg

from threading import Thread

from sim_test import *

class SimWorker(QThread) :
	threadEvent = pyqtSignal(int)
	threadEndEvent = pyqtSignal()
	
	def __init__(self, parent = None) :
		super().__init__()
		self.main = parent
		self.sec = 0
		self.isRun = False
		
	#def __del__(self) :
		#self.wait()
		
	def run(self) :
		#sim_test_main()
		while self.isRun : 
			self.threadEvent.emit(self.sec)
			self.sec = self.sec + 1
			self.msleep(100)
			
		self.threadEndEvent.emit()
	
class MainWindow(QtWidgets.QMainWindow) :
	def __init__(self) :
		super().__init__()
						
		layout = QGridLayout()
		
		self.graphWidget = []
		self.graphWidget.append(pg.PlotWidget())
		self.graphWidget.append(pg.PlotWidget())
		self.graphWidget.append(pg.PlotWidget())		
		#self.setCentralWidget(self.graphWidget)
		
		layout.addWidget(self.graphWidget[0], 0, 0)
		layout.addWidget(self.graphWidget[1], 0, 1)
		layout.addWidget(self.graphWidget[2], 1, 0)
		#layout.addWidget(pg.PlotWidget(), 1, 1)

		self.progressBar = QProgressBar(self)
		#self.progressBar.setOrientation(Qt.Vertical)			# 디폴트가 Qt.Horizontal 
		self.progressBar.setAlignment(Qt.AlignCenter)		# 중간에 표시되는 텍트가 중앙에 나타남 
		self.progressBar.setRange(0,100) 
		#self.progressBar.setFormat("%v km") # 10 km 형태로 표시, 디폴트는 %p 
		#self.someSignal.connect(self.progressBar.setValue)

		progressLayout = QHBoxLayout()																																																
		progressLayout.addWidget(self.progressBar)																																										

		self.label = QLabel("status", self)

		labelLayout = QHBoxLayout()																																																
		labelLayout.addWidget(self.label)																																										

		self.button = QPushButton("start", self)
		self.button.clicked.connect(self.startButtonClicked)

		self.button1 = QPushButton("stop", self)
		self.button1.clicked.connect(self.stopButtonClicked)
		self.button1.setEnabled(False)

		self.button2 = QPushButton("show result", self)
		self.button2.clicked.connect(self.infoButtonClicked)

		buttonLayout = QHBoxLayout()																																																
		buttonLayout.addWidget(self.button)																																										
		buttonLayout.addWidget(self.button1)
		buttonLayout.addWidget(self.button2)

		mainLayout = QVBoxLayout()																																																
		mainLayout.addLayout(layout)
		mainLayout.addLayout(progressLayout)																																										
		mainLayout.addLayout(labelLayout)																																								
		mainLayout.addLayout(buttonLayout)
																																																
		widget = QWidget()
		widget.setLayout(mainLayout)
		self.setCentralWidget(widget)

		#styles = {'color' : '#f00', 'font-size' : '20px'}
		styles = {'color' : '#00f', 'font-size' : '16px'}
		info = [{'title' : 'nand current icc', 'y_label' : 'current (mA)', 'x_label' : 'sec(s)'},
					{'title' : 'nand current iccq', 'y_label' : 'current (mA)', 'x_label' : 'sec(s)'},
					{'title' : 'nand power', 'y_label' : 'power (mW)', 'x_label' : 'sec(s)'}]
								
		for index, graphWidget in enumerate(self.graphWidget) :								
			graphWidget.setBackground('w')
			graphWidget.setTitle(info[index]['title'], color = 'b', size = '20pt')
			graphWidget.setLabel('left', info[index]['y_label'],  **styles)
			graphWidget.setLabel('bottom', info[index]['x_label'],  **styles)		
			#self.graphWidget.addLegend()
			graphWidget.showGrid(x=True, y=True)
													
		#self.graphWidget[0].setXRange(0, 10, padding = 0)
		self.graphWidget[0].setYRange(-1, 2, padding = 0)
		
		self.graphWidget[1].setXRange(0, 100, padding = 0)
		self.graphWidget[1].setYRange(0, 100, padding = 0)
		
		self.x = list(range(100))
		self.y = [randint(0, 1) for _ in range(100)]
		
		#self.x1 = list(range(100))
		#self.y1 = [randint(0, 100) for _ in range(100)]
		self.x1 = [0]
		self.y1 = [0]
		
		pen = pg.mkPen(color=(255, 0, 0))
		self.data_line = self.graphWidget[0].plot(self.x, self.y, pen = pen)
		
		pen = pg.mkPen(color=(0, 0, 255))
		self.data_line1 = self.graphWidget[1].plot(self.x1, self.y1, pen = pen)

		self.timer = QtCore.QTimer()
		self.timer.setInterval(50)
		self.timer.timeout.connect(self.update_plot_data)
		self.timer.start()

		self.th = SimWorker(parent = self)
		self.th.threadEvent.connect(self.threadEventHandler)
		self.th.threadEndEvent.connect(self.threadEndEventHandler)

	def update_plot_data(self) :
		self.x = self.x[1:]
		self.x.append(self.x[-1]+1)

		self.y = self.y[1:]
		self.y.append(randint(0,1))
								
		self.data_line.setData(self.x, self.y)
		
	@pyqtSlot()
	def startButtonClicked(self) :
		print('startButtonClicked')
		self.button.setEnabled(False)
		self.button1.setEnabled(True)

		'''	
		th1 = Thread(target = sim_test_main)
		th1.start()
	
		#th1.join()
		'''
		self.th.isRun = True		
		self.th.start()

	@pyqtSlot()
	def stopButtonClicked(self) :
		print('stopButtonClicked')
		self.th.isRun = False	

	@pyqtSlot()
	def infoButtonClicked(self) :
		print('infoButtonClicked')	
														
	@pyqtSlot(int)
	def threadEventHandler(self, n) :	
		self.label.setText(str(n))
		#self.label.setText(test_gui_status.debug)
		
		if len(self.x1) >= 100 :
			self.x1 = self.x1[1:]
			self.x1.append(self.x1[-1]+1)
	
			self.y1 = self.y1[1:]
			self.y1.append(n)
			
			self.graphWidget[1].setXRange(self.x1[0], self.x1[-1], padding = 0)
		else :
			self.x1.append(self.x1[-1]+1)
			self.y1.append(n)
	
		self.data_line1.setData(self.x1, self.y1)

	@pyqtSlot()
	def threadEndEventHandler(self) :	
		self.label.setText('end simulation')
		#self.label.setText(test_gui_status.debug)
		self.button.setEnabled(True)
		self.button1.setEnabled(False)
				
def sim_gui_main( ) :
	app = QtWidgets.QApplication(sys.argv)
	main = MainWindow()
	main.show()
	
	sys.exit(app.exec_())
	
if __name__ == '__main__' :
	sim_gui_main()