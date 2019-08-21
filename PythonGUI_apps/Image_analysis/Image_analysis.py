import sys
from pathlib import Path
import os.path
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets#, QColorDialog
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

# local modules
 
pg.mkQApp()
pg.setConfigOption('imageAxisOrder', 'col-major') 

base_path = Path(__file__).parent
file_path = (base_path / "image_analysis_gui.ui").resolve()

uiFile = file_path

WindowTemplate, TemplateBaseClass = pg.Qt.loadUiType(uiFile)

def updateDelay(scale, time):
	""" Hack fix for scalebar inaccuracy"""
	QtCore.QTimer.singleShot(time, scale.updateBar)

class MainWindow(TemplateBaseClass):  

	def __init__(self):
		super(TemplateBaseClass, self).__init__()
		
		# Create the main window
		self.ui = WindowTemplate()
		self.ui.setupUi(self)

		#setup imageview
		self.imv = pg.ImageView()
		self.imv.getView().setAspectLocked(lock=False, ratio=1)
		self.imv.getView().setMouseEnabled(x=True, y=True)
		self.imv.getView().invertY(False)
		self.imv.ui.roiBtn.setEnabled(False)
		self.roi = self.imv.roi
		self.roi.translateSnap = True
		self.roi.scaleSnap = True
		#self.roi.removeHandle(1)
		#self.roi.addScaleHandle([0, 0], [1, 1])
		self.update_camera() #initialize camera pixel size
		self.update_scaling_factor() #initialize scaling_factor

		self.roi_plot = self.imv.getRoiPlot().getPlotItem() #get roi plot
		self.ui.image_groupBox.layout().addWidget(self.imv)

		#setup plot
		self.rgb_plot_layout=pg.GraphicsLayoutWidget()
		self.ui.rgb_plot_groupBox.layout().addWidget(self.rgb_plot_layout)
		self.rgb_plot = self.rgb_plot_layout.addPlot()

		#set up ui signals
		self.roi.sigRegionChanged.connect(self.line_profile_update_plot)
		self.ui.load_image_pushButton.clicked.connect(self.load_image)
		self.ui.custom_pixel_size_checkBox.stateChanged.connect(self.switch_custom_pixel_size)
		self.ui.update_scaling_factor_pushButton.clicked.connect(self.reload_image)
		self.ui.spot_radioButton.toggled.connect(self.update_camera)
		self.ui.custom_pixel_size_spinBox.valueChanged.connect(self.update_scaling_factor)

		self.show()

		#row major. invert y false, rotate false
	def load_image(self):
		"""
		Prompts the user to select a text file containing image data.
		"""
		try:
			file = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', os.getcwd())
			self.original_image = Image.open(file[0])
			self.original_image = self.original_image.rotate(-90, expand=True) #correct image orientation
			self.resize_to_scaling_factor(self.original_image)
		except Exception as err:
			print(format(err))

	def resize_to_scaling_factor(self, image):
		"""
		Handles loading of image according to scaling_factor
		"""

		if self.ui.pixera_radioButton.isChecked():
			image = self.original_image
		elif self.ui.spot_radioButton.isChecked():
			image = self.original_image.resize((round(image.size[0]*self.scaling_factor), round(image.size[1]*self.scaling_factor)))
			
		if self.ui.greyscale_checkBox.isChecked():
			image = image.convert("L") #convert to greyscale

		image_array = np.array(image)
		width = image_array.shape[0]
		height = image_array.shape[1]
		
		try:
			if self.ui.vertical_radioButton.isChecked():
				x_vals = np.arange(width)
			elif self.ui.horizontal_radioButton.isChecked():
				x_vals = np.arange(height)

			if self.ui.pixera_radioButton.isChecked():
				x_vals = x_vals * self.scaling_factor
			
			self.imv.setImage(image_array, xvals= x_vals)
			
			if self.ui.vertical_radioButton.isChecked():
				roi_height = self.scaling_factor * height
				self.roi.setSize([width, roi_height])
			elif self.ui.horizontal_radioButton.isChecked():
				roi_height = self.scaling_factor * width
				self.roi.setSize([roi_height, height])

			self.roi.setPos((0, 0))
			
			scale = pg.ScaleBar(size=1,suffix='um')
			scale.setParentItem(self.imv.view)
			scale.anchor((1, 1), (1, 1), offset=(-30, -30))
			self.imv.view.sigRangeChanged.connect(lambda: updateDelay(scale, 10))
			self.roi.show()
			self.line_profile_update_plot()
		except:
			pass

	def line_profile_update_plot(self):
		""" Handle line profile for intensity sum viewbox """
		self.rgb_plot.clear()
		image = self.imv.getProcessedImage()

		# Extract image data from ROI
		axes = (self.imv.axes['x'], self.imv.axes['y'])
		data, coords = self.roi.getArrayRegion(image.view(np.ndarray), self.imv.imageItem, axes, returnMappedCoords=True)
		if data is None:
			return

		if self.ui.vertical_radioButton.isChecked():
			x_values = coords[0,:,0]
		elif self.ui.horizontal_radioButton.isChecked():
			x_values = coords[1,0,:]

		if self.ui.pixera_radioButton.isChecked():
			x_values = x_values * self.scaling_factor
		
		#calculate average along columns in region
		if len(data.shape) == 2: #if grayscale, average intensities 
			if self.ui.vertical_radioButton.isChecked():
				avg_to_plot = np.mean(data, axis=-1)
			elif self.ui.horizontal_radioButton.isChecked():
				avg_to_plot = np.mean(data, axis=0)
			try:
				self.rgb_plot.plot(x_values, avg_to_plot)
			except:
				pass
		elif len(data.shape) > 2: #if rgb arrays, plot individual components
			r_values = data[:,:,0]
			g_values = data[:,:,1]
			b_values = data[:,:,2]
			if self.ui.vertical_radioButton.isChecked():
				r_avg = np.mean(r_values, axis=-1) #average red values across columns
				g_avg = np.mean(g_values, axis=-1) #average green values
				b_avg = np.mean(b_values, axis=-1) #average blue values
			elif self.ui.horizontal_radioButton.isChecked():
				r_avg = np.mean(r_values, axis=0)
				g_avg = np.mean(g_values, axis=0)
				b_avg = np.mean(b_values, axis=0)
			try:
				self.rgb_plot.plot(x_values, r_avg, pen='r')
				self.rgb_plot.plot(x_values, g_avg, pen='g')
				self.rgb_plot.plot(x_values, b_avg, pen='b')
			except Exception as e:
				pass

	def update_scaling_factor(self):
		"""
		Calculate scaling factor
		"""
		if self.ui.custom_pixel_size_checkBox.isChecked():
			self.camera_pixel_size = self.ui.custom_pixel_size_spinBox.value()
			self.scaling_factor = self.camera_pixel_size
		else:
			self.scaling_factor = self.camera_pixel_size/int(self.ui.magnification_comboBox.currentText())
		self.roi.snapSize = self.scaling_factor #roi snaps to multiples of scaling_factor

	def reload_image(self):
		if hasattr(self, "original_image"):
			self.resize_to_scaling_factor(self.original_image) #resize image, sets up roi

	def switch_custom_pixel_size(self):
		checked = self.ui.custom_pixel_size_checkBox.isChecked()
		self.ui.custom_pixel_size_spinBox.setEnabled(checked)
		self.ui.magnification_comboBox.setEnabled(not checked)

	def update_camera(self):
		if self.ui.spot_radioButton.isChecked():
			self.camera_pixel_size = 7.4
			self.ui.greyscale_checkBox.setChecked(False)
			self.update_scaling_factor()
		elif self.ui.pixera_radioButton.isChecked():
			self.camera_pixel_size = 3
			self.ui.greyscale_checkBox.setChecked(True)
			self.update_scaling_factor()

	def close_application(self):
		choice = QtGui.QMessageBox.question(self, 'EXIT!',
											"Do you want to exit the app?",
											QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
		if choice == QtGui.QMessageBox.Yes:
			sys.exit()
		else:
			pass

"""Run the Main Window"""    
def run():
	win = MainWindow()
	QtGui.QApplication.instance().exec_()
	return win

#Uncomment below if you want to run this as standalone
#run()