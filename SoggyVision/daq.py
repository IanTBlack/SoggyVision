from datetime import datetime, timedelta
import json
from PyQt6 import QtCore
import serial
import serial.tools.list_ports
import time
import xarray as xr

from SoggyVision.database import SVDB, ACSMetadataTable, ACSDataTable, ACSFlagsTable
from SoggyVision.qc import gap_test, syntax_test

class DataAcquisitionThread(QtCore.QThread):
    serial_data = QtCore.pyqtSignal(object)

    def __init__(self, port: str, ACS: object, hindcast: int) -> None:
        QtCore.QThread.__init__(self)

        self.port = port
        self.acs = ACS
        self.hindcast = int(hindcast)
        self.baudrate = self.acs.baudrate  #Get the baudrate defined in the .dev file. Should always be 115200.

        self.serial = serial.Serial()# Create a serial instance.
        self.serial.port = self.port
        self.serial.baudrate = self.baudrate
        self.serial.open()

        # Create a blank dataset to append data too. Size is dictated by the user defined hindcast.
        self._ds = xr.Dataset()
        self._ds = self._ds.assign_coords({'time': [],
                                           'wavelength_a': self.acs.wavelength_a,
                                           'wavelength_c': self.acs.wavelength_c})
        self._ds['time'] = self._ds['time'].astype('datetime64[ns]')

        self.log = False
        self.dbname = None
        self.db = None
        self.running = True


    def run(self) -> None:

        # Reset serial buffers.
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()
        self._buffer = bytearray()

        # Loop for seeking and passing data.
        valid_counter = 0
        while self.running:
            dt = datetime.now()
            incoming = self.serial.read(self.serial.in_waiting)
            self._buffer.extend(incoming)
            frame, checksum, self._buffer, unknown_bytes = self.acs.find_packet(self._buffer)
            if frame is None:
                valid_counter += 1
                if valid_counter >= 60:
                    raise
                time.sleep(0.005)
                continue
            else:
                valid_counter = 0

                # Run gap test.
                gap_test_results = gap_test(datetime.now(), dt, len(self._buffer), len(frame))

                # Obtain data.
                data = self.acs.get_data(dt, frame)
                syntax_test_results = syntax_test(data.frame, data.frame_length, checksum)
                flags = self.acs.get_flags(data,gap_test_results, syntax_test_results)

                # Log data if the user indicates they want to log data.
                if self.dbname is not None and self.log is True:
                    dti = [json.dumps(v) if isinstance(v, list) else float(v) if isinstance(v, float) else int(
                        v) if isinstance(v, int) else str(v) for v in list(data)]
                    fti = [int(v) if isinstance(v, int) else str(v) for v in list(flags)]
                    if self.db is None: #Initiate
                        self.db = SVDB(self.dbname)
                        metadata = self.acs.get_metadata()
                        mti = [json.dumps(v) if isinstance(v, list) else float(v) if isinstance(v, float) else int(
                            v) if isinstance(v, int) else str(v) for v in
                               list(metadata)]
                        begin_time_idx = ACSMetadataTable.fields.index('begin_time')
                        mti[begin_time_idx] = data.time
                        self._begin_time = data.time
                        self.db.insert_data(ACSMetadataTable.name, ACSMetadataTable.fields,mti)

                    self.db.insert_data(ACSDataTable.name, ACSDataTable.fields, dti)
                    self.db.insert_data(ACSFlagsTable.name, ACSFlagsTable.fields, fti)
                    self.db.update_end_time(ACSMetadataTable.name,self._begin_time, data.time)

                _ds = xr.Dataset()
                _ds = _ds.assign_coords(
                    {'time': [dt], 'wavelength_c': self.acs.wavelength_c, 'wavelength_a': self.acs.wavelength_a})
                _ds['time'] = _ds['time'].astype('datetime64[ns]')
                _ds['a_m'] = (['time', 'wavelength_a'], [data.a_m])
                _ds['c_m'] = (['time', 'wavelength_c'], [data.c_m])
                _ds['internal_temperature'] = (['time'], [round(data.internal_temperature, 2)])
                _ds['external_temperature'] = (['time'], [round(data.external_temperature, 2)])

                _ds['a_signal_dark'] = (['time'], [data.a_signal_dark])
                _ds['c_signal_dark'] = (['time'], [data.c_signal_dark])
                _ds['a_reference_dark'] = (['time'], [data.a_reference_dark])
                _ds['c_reference_dark'] = (['time'], [data.c_reference_dark])

                _ds['flag_gap'] = (['time'], [flags.flag_gap_test])
                _ds['flag_syntax'] = (['time'], [flags.flag_syntax_test])
                _ds['flag_gross_a_m'] = (['time', 'wavelength_a'], [flags.flag_gross_range_test_a_m])
                _ds['flag_gross_c_m'] = (['time', 'wavelength_c'], [flags.flag_gross_range_test_c_m])


                self._ds = xr.concat([self._ds, _ds], dim='time')
                self._ds = self._ds.sel(time=slice(dt - timedelta(seconds=self.hindcast), dt))
                self.serial_data.emit(self._ds)  # Pass data to GUI.



            #time.sleep(0.1)

    def stop(self):
        self.running = False

