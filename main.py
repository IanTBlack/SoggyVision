from datetime import datetime, timezone, timedelta
import serial
from PyQt6 import QtCore, QtGui, QtWidgets, uic
import sys
import time
import os
import pyqtgraph
import numpy as np
import xarray as xr

import serial.tools.list_ports
import json
import webbrowser


from SoggyVision.acs import ACS
from SoggyVision.core import wavelength_to_rgb, APP_DIR, CAL_DIR, DB_DIR, EXPORT_DIR, SV_VERSION, SV_REPO, SV_ISSUES, SV_DISCUSSION, build_directories
from SoggyVision.daq import DataAcquisitionThread
from SoggyVision.export import export_netcdf
# pyqtgraph.setConfigOption('background', 'gray')

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        build_directories() # Build directories for storing data.

        uic.loadUi("gui_templates/SoggyVision_v5.ui", self)

        self.setup_ui()
        self.LoadDevButton.clicked.connect(self.load_calibration_file)
        self.ConnectDisconnectButton.clicked.connect(self.daq_actions)
        self.StartStopLogButton.clicked.connect(self.logging_actions)
        self.actionVs_Time.triggered.connect(self.showVsTime)
        self.actionExit.triggered.connect(self.exit_app)


        self.actionManufacturer_Documents.triggered.connect(self.link_to_acs_manual)
        self.actionAbout.triggered.connect(self.showAbout)
        self.actionSensor_Metadata.triggered.connect(self.showMetadata)
        self._NoDataWindow.OK.clicked.connect(self.closeNoDataDialog)
        self.actionExport.triggered.connect(self.showExportWindow)
        self._ExportWindow.SelectDatabase.clicked.connect(self.select_database)
        self._ExportWindow.ExportFile.clicked.connect(self.export_data)

    def exit_app(self):
        QtWidgets.QApplication.closeAllWindows()
        sys.exit()

    def reset_app(self):
        pass

    def closeNoDataDialog(self):
        self._NoDataWindow.close()


    def link_to_acs_manual(self):
        url = "https://www.seabird.com/transmissometers/ac-s-spectral-absorption-and-attenuation-sensor/family-downloads?productCategoryId=54627869911"
        webbrowser.open(url)

    def select_database(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select a .db file...', DB_DIR)
        filename, ext = os.path.splitext(os.path.basename(filepath))
        self._ExportWindow.Database.setText(filename)


        fsel = self._ExportWindow.FiletypeBox.currentText()
        if 'netCDF4' in fsel:
            ftype = '.nc'
        self._ExportWindow.SaveName.setText(filename + ftype)
        self._ExportWindow.ExportFile.setEnabled(True)

    def export_data(self):
        dbname = self._ExportWindow.Database.text()
        output_filename = self._ExportWindow.SaveName.text()
        custom_attrs = {}
        custom_attrs['operator'] = self._ExportWindow.Operator.text()
        custom_attrs['institution'] = self._ExportWindow.Institution.text()
        custom_attrs['dataset_description'] = self._ExportWindow.Description.toPlainText()
        export_netcdf(dbname, output_filename, custom_attrs, self._ExportWindow.ExportProgress)

    def setup_ui(self):
        self.start_clock_timer(1000)
        self.verticalLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop) # Force user selection layout to align to the top.
        self.vsTimeWindow = VsTimeWindow()
        self.about = AboutWindow()
        self._metadata_window = MetadataWindow()
        self._NoDataWindow = NoDataWindow()
        self._ExportWindow = ExportWindow()
        self.initialize_plots()

        # Disable widgets and labels.
        self.MetadataHeader.setEnabled(False)
        self.SNLabel.setEnabled(False)
        self.SN.setEnabled(False)
        self.CalDateLabel.setEnabled(False)
        self.CalDate.setEnabled(False)
        self.NumWvlsLabel.setEnabled(False)
        self.NumWvls.setEnabled(False)
        self.CommSetupHeader.setEnabled(False)
        self.COMPortLabel.setEnabled(False)
        self.COMPortCombo.setEnabled(False)
        self.ConnectDisconnectButton.setEnabled(False)
        self.DataCollectionHeader.setEnabled(False)
        self.FilepathInputLabel.setEnabled(False)
        self.FilepathInput.setEnabled(False)
        self.StartStopLogButton.setEnabled(False)
        self.FileSizeLabel.setEnabled(False)
        self.FileSize.setEnabled(False)
        self.actionSensor_Metadata.setEnabled(False)
        self.statusbar.showMessage(f"Welcome to SoggyVision!")


        self.Visualizer.setCurrentIndex(0)

    def showVsTime(self):
        self.vsTimeWindow.show()

    def showMetadata(self):
        self._metadata_window.show()

    def showNoDataWindow(self):
        self._NoDataWindow.setModal(True)
        self._NoDataWindow.show()

    def showExportWindow(self):
        self._ExportWindow.setModal(True)
        self._ExportWindow.show()

    def showAbout(self):
        self.about.Version.setText(f"Version: {SV_VERSION}")
        self.about.RepoLink.setText(f"{SV_REPO}")
        self.about.IssueLink.setText(f"{SV_ISSUES}")
        self.about.DiscLink.setText(f"{SV_DISCUSSION}")
        self.about.show()


    def initialize_plots(self):
        font = QtGui.QFont("Times", 16)

        # Absorption vs Wavelength Plot
        self.avw = self.AvW.plot(pen = pyqtgraph.mkPen('w',width = 3))
        self.AvW.setTitle('<font>Absorption vs Wavelength</font>')
        self.AvW.showGrid(x=True, y = True)
        self.AvW.setLabel('left','Absorption',units='<font><sup>1</sup><sub>m</sub></font>')
        self.AvW.setLabel('bottom','Wavelength', units = '<font>nm</font>')
        self.AvW.getAxis('left').label.setFont(font)
        self.AvW.getAxis('bottom').label.setFont(font)
        self.AvW.getAxis("left").tickFont = font
        self.AvW.getAxis("bottom").tickFont = font

        # Attenuation vs Wavelength Plot
        self.cvw = self.CvW.plot(pen = pyqtgraph.mkPen('w',width = 3))
        self.CvW.setTitle('<font>Attenuation vs Wavelength</font>')
        self.CvW.showGrid(x=True, y = True)
        self.CvW.setLabel('left','Attenuation',units='<font><sup>1</sup><sub>m</sub></font>')
        self.CvW.setLabel('bottom','Wavelength', units = '<font>nm</font>')
        self.CvW.getAxis('left').label.setFont(font)
        self.CvW.getAxis('bottom').label.setFont(font)
        self.CvW.getAxis("left").tickFont = font
        self.CvW.getAxis("bottom").tickFont = font

        # Absorption vs Time Plot
        self.AvT.setTitle('<font>Absorption vs Time</font>')
        self.AvT.showGrid(x=True, y = True)
        self.AvT.setLabel('left','Absorption',units='<font><sup>1</sup><sub>m</sub></font>')
        self.AvT.setLabel('bottom','Time', units = '<font>UTC</font>')
        self.AvT.getAxis('left').label.setFont(font)
        self.AvT.getAxis('bottom').label.setFont(font)
        self.AvT.getAxis("left").tickFont = font
        self.AvT.getAxis("bottom").tickFont = font


        # Attenuation vs Time Plot
        self.CvT.setTitle('<font>Attenuation vs Time<f/ont>')
        self.CvT.showGrid(x=True, y = True)
        self.CvT.setLabel('left','Attenuation',units='<font><sup>1</sup><sub>m</sub></font>')
        self.CvT.setLabel('bottom','Time', units = '<font>UTC</font>')
        self.CvT.getAxis('left').label.setFont(font)
        self.CvT.getAxis('bottom').label.setFont(font)
        self.CvT.getAxis("left").tickFont = font
        self.CvT.getAxis("bottom").tickFont = font

        # Diagnostic Plots
        self.DiagT = self.Diagnostic.addPlot(row = 0, col = 0, title = '<font>Temperatures</font>')
        self.DiagT.addLegend()
        self.DiagT.showGrid(x=True, y = True)
        self._temp_int = self.DiagT.plot(name = 'Internal Temperature',pen = pyqtgraph.mkPen('g',width = 3))
        self._temp_ext = self.DiagT.plot(name = 'External Temperature',pen = pyqtgraph.mkPen('r',width = 3))
        self.DiagT.setLabel('left','Temperature',units='<font>\u00b0C</font>')
        self.DiagT.setLabel('bottom','Time', units = '<font>UTC</font>')
        self.DiagT.getAxis('left').label.setFont(font)
        self.DiagT.getAxis('bottom').label.setFont(font)
        self.DiagT.getAxis("left").tickFont = font
        self.DiagT.getAxis("bottom").tickFont = font

        self.DiagDarks = self.Diagnostic.addPlot(row = 0, col = 1, title = 'Dark Values')
        self.DiagDarks.setXLink(self.DiagT)
        self.DiagDarks.addLegend()
        self.DiagDarks.showGrid(x=True, y = True)
        self._darkcsig = self.DiagDarks.plot(name = 'C Signal',pen = pyqtgraph.mkPen('b',width = 3, style = QtCore.Qt.PenStyle.DotLine))
        self._darkcref = self.DiagDarks.plot(name = 'C Reference',pen = pyqtgraph.mkPen('b',width = 3))
        self._darkasig = self.DiagDarks.plot(name = 'A Signal',pen = pyqtgraph.mkPen('g',width = 3, style = QtCore.Qt.PenStyle.DotLine))
        self._darkaref = self.DiagDarks.plot(name = 'A Reference',pen = pyqtgraph.mkPen('g',width = 3))
        self.DiagDarks.setLabel('left','Signal',units='<font>counts</font>')
        self.DiagDarks.setLabel('bottom','Time', units = '<font>UTC</font>')
        self.DiagDarks.getAxis('left').label.setFont(font)
        self.DiagDarks.getAxis('bottom').label.setFont(font)
        self.DiagDarks.getAxis("left").tickFont = font
        self.DiagDarks.getAxis("bottom").tickFont = font

        self.DiagQ1 = self.Diagnostic.addPlot(row = 1, col = 0, title = '<font>Gap and Syntax Flags</font>')
        self.DiagQ1.setXLink(self.DiagT)
        self.DiagQ1.addLegend()
        self.DiagQ1.showGrid(x=True, y = True)
        self._qartodgap = self.DiagQ1.plot(name = 'Gap Test',pen = None, symbol = 'o', symbolPen = 'y',symbolBrush = 'y')
        self._qartodsyntax = self.DiagQ1.plot(name = 'Syntax Test',pen = None, symbol = 'x', symbolPen = 'b',symbolBrush = 'b')
        #self._qartodlocation= self.DiagQ1.plot(name = 'Location Test',pen = pyqtgraph.mkPen('g',width = 3, style = QtCore.Qt.PenStyle.DotLine))
        self.DiagQ1.setLabel('left','Flag')
        self.DiagQ1.setLabel('bottom','Time', units = '<font>UTC</font>')
        self.DiagQ1.getAxis('left').label.setFont(font)
        self.DiagQ1.getAxis('bottom').label.setFont(font)
        self.DiagQ1.getAxis("left").tickFont = font
        self.DiagQ1.getAxis("bottom").tickFont = font


        self.DiagQ2 = self.Diagnostic.addPlot(row = 1, col = 1, title = '<font>Gross Range Flags</font>')
        self.DiagQ2.addLegend()
        self.DiagQ2.showGrid(x=True, y = True)
        self._qartodgross_a = self.DiagQ2.plot(name = 'Gross Range Test - a_m',pen = None, symbol = 'o', symbolPen = 'red',symbolBrush = 'red')
        self._qartodgross_c = self.DiagQ2.plot(name = 'Gross Range Test - c_m ',pen = None, symbol = 'x', symbolPen = 'blue',symbolBrush = 'blue')
        self.DiagQ2.setLabel('left','Flag')
        self.DiagQ2.setLabel('bottom','Wavelength', units = '<font>nm</font>')
        self.DiagQ2.getAxis('left').label.setFont(font)
        self.DiagQ2.getAxis('bottom').label.setFont(font)
        self.DiagQ2.getAxis("left").tickFont = font
        self.DiagQ2.getAxis("bottom").tickFont = font

    def start_clock_timer(self, update_ms: int = 1000) -> None:
        """
        Start a timer for updating the clock every X milliseconds.
        :return: None
        """
        clock = QtCore.QTimer(self)
        clock.timeout.connect(self.update_clock)
        clock.start(update_ms)

    def update_clock(self):
        """
        Update the clock label with the time in an ISO8601 approved format.
        :return: None
        """
        iso8601_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        self.ClockUTC.setText(iso8601_str)


    def load_calibration_file(self):
        os.makedirs(CAL_DIR, exist_ok=True)
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select a .dev file...', CAL_DIR)
        self.acs = ACS(filepath)

        # Set Metadata
        self.SN.setText(self.acs.sn)
        self.CalDate.setText(self.acs.cal_date)
        self.NumWvls.setText(str(self.acs.output_wavelengths))

        # Enable Widgets
        self.MetadataHeader.setEnabled(True)
        self.SNLabel.setEnabled(True)
        self.CalDateLabel.setEnabled(True)
        self.NumWvlsLabel.setEnabled(True)
        self.SN.setEnabled(True)
        self.CalDate.setEnabled(True)
        self.NumWvls.setEnabled(True)

        self.CommSetupHeader.setEnabled(True)
        self.COMPortLabel.setEnabled(True)
        self.COMPortCombo.setEnabled(True)
        self.ConnectDisconnectButton.setEnabled(True)

        # Set additional info for Comm Setup.
        available_ports = sorted([v.name for v in serial.tools.list_ports.comports()])
        self.COMPortCombo.clear()
        self.COMPortCombo.addItems(['AUTO'] + available_ports)

        # Set additional info for timeseries plots:
        self.vsTimeWindow.AbsorptionList.clear()
        for wvl in self.acs.wavelength_a:
            self.vsTimeWindow.AbsorptionList.addItem(str(wvl))

        self.vsTimeWindow.AttenuationList.clear()
        for wvl in self.acs.wavelength_c:
            self.vsTimeWindow.AttenuationList.addItem(str(wvl))
        defaults = [440, 510, 580, 650, 715]
        self._old_a = []
        self._old_c = []
        for default in defaults:
            closest_a = min(self.acs.wavelength_a, key = lambda x:abs(x-default))
            self._old_a.append(closest_a)
            a_items = self.vsTimeWindow.AbsorptionList.findItems(str(closest_a),QtCore.Qt.MatchFlag.MatchExactly)
            for item in a_items:
                item.setSelected(True)
            closest_c = min(self.acs.wavelength_c, key = lambda x:abs(x-default))
            self._old_c.append(closest_a)
            c_items = self.vsTimeWindow.AttenuationList.findItems(str(closest_c),QtCore.Qt.MatchFlag.MatchExactly)
            for item in c_items:
                item.setSelected(True)
        self.vsTimeWindow.AbsorptionList.setEnabled(True)
        self.vsTimeWindow.AttenuationList.setEnabled(True)




        # Add metadata to MetadataWindow.
        self._metadata_window.SensorType.setText(str(self.acs.sensor_type))
        self._metadata_window.SN.setText(str(self.acs.sn))
        self._metadata_window.CalDate.setText(str(self.acs.cal_date))
        self._metadata_window.WBins.setText(str(self.acs.output_wavelengths))
        self._metadata_window.TBins.setText(str(self.acs.num_tbins))
        self._metadata_window.TRange.setText(f"{round(self.acs.tbins.min(),2)} - {round(self.acs.tbins.max(),2)}")
        self._metadata_window.TCal.setText(str(self.acs.tcal))
        self._metadata_window.ICal.setText(str(self.acs.ical))
        self._metadata_window.PathLength.setText(str(self.acs.path_length))
        self._metadata_window.DOff.setText(str(self.acs.depth_cal_1))
        self._metadata_window.DSF.setText(str(self.acs.depth_cal_2))
        self._metadata_window.StructVer.setText(str(self.acs.structure_version))
        self._metadata_window.Filepath.setText(str(self.acs.filepath))
        self._metadata_window.ANoise.setText(str(self.acs.max_a_noise))
        self._metadata_window.ANonConform.setText(str(self.acs.max_a_nonconform))
        self._metadata_window.ADiff.setText(str(self.acs.max_a_difference))
        self._metadata_window.ACounts.setText(str(self.acs.min_a_counts))
        self._metadata_window.CNoise.setText(str(self.acs.max_c_noise))
        self._metadata_window.CNonConform.setText(str(self.acs.max_c_nonconform))
        self._metadata_window.CDiff.setText(str(self.acs.max_c_difference))
        self._metadata_window.CCounts.setText(str(self.acs.min_c_counts))
        self._metadata_window.RCounts.setText(str(self.acs.min_r_counts))
        self._metadata_window.TSDev.setText(str(self.acs.max_tempsdev))
        self._metadata_window.DSDev.setText(str(self.acs.max_depth_sdev))

        self.actionSensor_Metadata.setEnabled(True)
        self.statusbar.showMessage(f"Loaded Factory Calibration File ({self.acs.filepath})")



        #Prep Vs Time Plots
        self.a_plots = {}
        self.a_colors = {}
        self.avt_legend = self.AvT.addLegend(colCount = 10)
        for wvl in self.acs.wavelength_a.tolist():
            self.a_plots[str(wvl)] = self.AvT.plot(setClickable = False,
                                                   name = str(wvl),
                                                   pen = pyqtgraph.mkPen(color = wavelength_to_rgb(float(wvl)),width = 1),
                                                   )
            self.avt_legend.removeItem(self.a_plots[str(wvl)])

            self.a_colors[str(wvl)] = wavelength_to_rgb(float(wvl))


        self.c_plots = {}
        self.c_colors = {}
        self.cvt_legend = self.CvT.addLegend(colCount = 10)
        for wvl in self.acs.wavelength_c.tolist():
            self.c_plots[str(wvl)] = self.CvT.plot(setClickable = False,
                                                   name = str(wvl),
                                                   pen = pyqtgraph.mkPen(color = wavelength_to_rgb(float(wvl)),width = 1),
                                                   )
            self.c_colors[str(wvl)] = wavelength_to_rgb(float(wvl))


        # Prep Diagnostic Plots
        self.DiagT.addItem(pyqtgraph.InfiniteLine(float(self.acs.tbins.max()),angle = 0), label = 'Maximum Temperature Calibration',pen = pyqtgraph.mkPen(width = 3, color = 'y'))
        self.DiagT.addItem(pyqtgraph.InfiniteLine(float(self.acs.tbins.min()),angle = 0), label = 'Minimum Temperature Calibration',pen = pyqtgraph.mkPen(width = 3, color = 'y'))

    def list_ports(self):
        available_ports = sorted([v.name for v in serial.tools.list_ports.comports()])
        return available_ports



    def daq_actions(self):
        button_state = self.ConnectDisconnectButton.text()
        if button_state == 'Connect':

            ports = self.list_ports()
            if self.COMPortCombo.currentText() == 'AUTO' and len(ports) == 1:
                [port] = ports
            elif self.COMPortCombo.currentText() == 'AUTO' and len(ports) > 1:
                for port in ports:
                    try:
                        _serial = serial.Serial(port = port, baudrate=self.acs.baudrate)
                        _serial.open()
                        time.sleep(3)
                        buffer = bytearray(_serial.read(_serial.in_waiting))
                        if self.acs.PACKET_REGISTRATION in buffer:
                            _serial.close()
                            time.sleep(1)
                            break
                        else:
                            continue
                    except:
                        continue
            elif self.COMPortCombo.currentText() != 'AUTO':
                port = self.COMPortCombo.currentText()

            try:
                self.COMPortCombo.setCurrentText(port)

                self.daq = DataAcquisitionThread(port, self.acs, int(self.vsTimeWindow.Hindcast.text()))
                if self.daq.serial.is_open:
                    time.sleep(0.25)
                    if self.daq.serial.in_waiting == 0 or self.acs.PACKET_REGISTRATION not in bytearray(
                            self.daq.serial.read(self.daq.serial.in_waiting)):
                        self.daq.running = False
                        self.daq.serial.reset_output_buffer()
                        self.daq.serial.reset_input_buffer()
                        self.daq.serial.close()
                        self._NoDataWindow.NoData.setText(f'Status: No ACS data detected on {self.daq.port}.')
                        self.statusbar.showMessage(f"Unable to connect to {self.acs.sn} on {self.daq.port}.")
                        self.daq.quit()
                        self.showNoDataWindow()
                    else:
                        self.daq.start()

                        # Change button state.

                        self.ConnectDisconnectButton.setText('Disconnect')  # Set the button to disconnect.
                        self.statusbar.showMessage(f"Connected to {self.acs.sn} on {self.daq.port}.")

                        # Disable Things
                        self.COMPortCombo.setEnabled(False)
                        self.COMPortLabel.setEnabled(False)
                        self.LoadDevButton.setEnabled(False)

                        # Enable Things
                        self.FilepathInput.setText(f"{self.acs.sn}_{datetime.now(timezone.utc).strftime('%Y%m%d')}")
                        self.FilepathInput.setEnabled(True)
                        self.FilepathInputLabel.setEnabled(True)

                        self.Visualizer.setEnabled(True)
                        self.StartStopLogButton.setEnabled(True)

                        self.daq.serial_data.connect(self.plot_data)

            except:
                self._NoDataWindow.NoData.setText(f'Status: No available serial ports detected.')
                self._NoDataWindow.setWindowTitle(f'No Available Serial Ports Detected')
                self.showNoDataWindow()




        elif button_state == 'Disconnect':
            if self.daq.isRunning():
                self.daq.running = False
                self.daq.serial.reset_output_buffer()
                self.daq.serial.reset_input_buffer()
                self.daq.serial.close()
            else:
                try:
                    self.daq.running = False
                    self.daq.serial.reset_output_buffer()
                    self.daq.serial.reset_input_buffer()
                    self.daq.serial.close()
                except:
                    pass

            self.Visualizer.setEnabled(False)
            self.COMPortCombo.setEnabled(True)
            self.COMPortLabel.setEnabled(True)
            self.LoadDevButton.setEnabled(True)
            self.FilepathInput.setText("")
            self.StartStopLogButton.setEnabled(False)





            self.ConnectDisconnectButton.setText('Connect') # Set the button to disconnect.
            self.statusbar.showMessage(f"Disconnected from {self.acs.sn}.")




    def logging_actions(self):
        button_state = self.StartStopLogButton.text()
        if 'Start' in button_state:
            self.daq.db = None
            self.daq.dbname, _ = os.path.splitext(f"{self.FilepathInput.text()}")
            self.daq.log = True
            self.StartStopLogButton.setText('Stop Logging')
            self.FilepathInputLabel.setEnabled(False)
            self.FilepathInput.setEnabled(False)
            self.FileSize.setEnabled(True)
            self.FileSizeLabel.setEnabled(True)
            self.ConnectDisconnectButton.setEnabled(False)
            self.statusbar.showMessage(f"Logging {self.acs.sn} data to {self.daq.dbname}.db.")

        elif 'Stop' in button_state:
            self.daq.log = False
            self.statusbar.showMessage(f"Stopped logging {self.acs.sn} data to {self.daq.dbname}.db.")
            self.daq.dbname = None
            self.db = None
            self.StartStopLogButton.setText('Start Logging')
            self.FilepathInput.setEnabled(True)
            self.FilepathInputLabel.setEnabled(True)
            self.ConnectDisconnectButton.setEnabled(True)


    def plot_data(self,ds):
        if self.daq.log is True: # If actively logging, update the database size to the nearest megabyte.
            filepath = os.path.join(DB_DIR,f"{os.path.splitext(os.path.normpath(self.FilepathInput.text()))[0]}.db")
            mb = str(round(os.stat(filepath).st_size/(1024 * 1024))).zfill(6)
            self.FileSize.setText(mb)

        hindcast = self.vsTimeWindow.Hindcast.text()
        try:
            self.daq.hindcast = int(hindcast)
        except:
            pass


        current_tab_idx = self.Visualizer.currentIndex()
        current_tab = self.Visualizer.tabText(current_tab_idx)
        if current_tab == 'a_m vs wavelength':
            self.avw.clear()
            last_sample = ds.sel(time = ds['time'].max())
            self.avw.setData(last_sample['wavelength_a'].values.flatten(), last_sample['a_m'].values.flatten())

        elif current_tab == 'c_m vs wavelength':
            self.cvw.clear()
            last_sample = ds.sel(time = ds['time'].max())
            self.cvw.setData(last_sample['wavelength_c'].values.flatten(), last_sample['c_m'].values.flatten())


        elif current_tab == 'a_m vs time':
            # for old_wvl in self._old_a:
            #     self.a_plots[str(old_wvl)].clear()
            #     self.avt_legend.removeItem(self.a_plots[str(old_wvl)])
            #
            for wvl, _plt in self.a_plots.items():
                _plt.clear()
                self.avt_legend.removeItem(self.a_plots[str(wvl)])
            selected_a = sorted([float(v.text()) for v in self.vsTimeWindow.AbsorptionList.selectedItems()])
            wvlds = ds.sel(wavelength_a = selected_a, method = 'nearest')
            for wvl in selected_a:
                _wvlds = wvlds.sel(wavelength_a = float(wvl), method = 'nearest')
                self.a_plots[str(wvl)].setData(_wvlds['time'].values.flatten(), _wvlds['a_m'].values.flatten())
                self.avt_legend.addItem(self.a_plots[str(wvl)], str(wvl))
            self._old_a = selected_a


        elif current_tab == 'c_m vs time':
            for wvl, _plt in self.c_plots.items():
                _plt.clear()
                self.cvt_legend.removeItem(self.c_plots[str(wvl)])
            selected_c = sorted([float(v.text()) for v in self.vsTimeWindow.AttenuationList.selectedItems()])
            wvlds = ds.sel(wavelength_c=selected_c, method='nearest')
            for wvl in selected_c:
                _wvlds = wvlds.sel(wavelength_c=float(wvl), method='nearest')
                self.c_plots[str(wvl)].setData(_wvlds['time'].values.flatten(), _wvlds['c_m'].values.flatten())
                self.cvt_legend.addItem(self.c_plots[str(wvl)], str(wvl))


        elif current_tab == 'diagnostic':
            for _plt in [self._temp_ext, self._temp_int,
                        self._darkcsig, self._darkaref, self._darkcref, self._darkasig, self._qartodgap, self._qartodsyntax, self._qartodgross_a, self._qartodgross_c]:
                _plt.clear()
            self._temp_int.setData(ds['time'].values.flatten(), ds['internal_temperature'].values.flatten())
            self._temp_ext.setData(ds['time'].values.flatten(), ds['external_temperature'].values.flatten())
            self._darkcsig.setData(ds['time'].values.flatten(), ds['c_signal_dark'].values.flatten())
            self._darkasig.setData(ds['time'].values.flatten(), ds['a_signal_dark'].values.flatten())
            self._darkcref.setData(ds['time'].values.flatten(), ds['c_reference_dark'].values.flatten())
            self._darkaref.setData(ds['time'].values.flatten(), ds['a_reference_dark'].values.flatten())

            self._qartodgap.setData(ds['time'].values.flatten(), ds['flag_gap'].values.flatten())
            self._qartodsyntax.setData(ds['time'].values.flatten(), ds['flag_syntax'].values.flatten())
            #self._qartodlocation.setData(ds['time'].values.flatten(), ds['flag_location'].values.flatten())

            last_sample = ds.sel(time = ds['time'].max())
            self._qartodgross_a.setData(last_sample['wavelength_a'].values.flatten(), last_sample['flag_gross_a_m'].values.flatten())
            self._qartodgross_c.setData(last_sample['wavelength_c'].values.flatten(), last_sample['flag_gross_c_m'].values.flatten())




class VsTimeWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("gui_templates/VsTime.ui", self)
        self.setWindowTitle("Vs Time Plot Settings")
        self.setWindowFlags(QtCore.Qt.WindowType.WindowCloseButtonHint)

class AboutWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("gui_templates/AboutForm.ui", self)
        self.setWindowTitle("About")
        self.setWindowFlags(QtCore.Qt.WindowType.WindowCloseButtonHint)

class MetadataWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("gui_templates/SensorMetadataForm.ui", self)
        self.setWindowTitle("Sensor Metadata")
        self.setWindowFlags(QtCore.Qt.WindowType.WindowCloseButtonHint)

class NoDataWindow(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("gui_templates/NoDataDialog.ui", self)
        self.setWindowTitle('No Data Received')
        self.setWindowFlags(QtCore.Qt.WindowType.WindowCloseButtonHint)

class ExportWindow(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("gui_templates/ExportDataForm.ui", self)
        self.setWindowTitle('Export ACS Database')
        self.setWindowFlags(QtCore.Qt.WindowType.WindowCloseButtonHint)

if __name__ == "__main__":
    main()