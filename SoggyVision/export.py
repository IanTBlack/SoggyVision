import numpy as np
import json
import xarray as xr
import os
import yaml
import matplotlib.pyplot as plt

from SoggyVision.database import SVDB, ACSDataTable, ACSMetadataTable, ACSFlagsTable
from SoggyVision.core import APP_NAME, EXPORT_DIR
from SoggyVision.acs import ACS


class DBLoader():
    def __init__(self, dbname):
        self.db = SVDB(dbname)
        self.metadata = self.load_metadata()

        with open('C:/Users/Ian/projects/SoggyVision/SoggyVision/attributes.yaml', 'r') as f:
            self.attrs = yaml.safe_load(f)

    def load_metadata(self):
        # TODO, add conditions for multiple entries. The acs_metadata table is setup to create a new entry each time logging is started.
        #  Currently there is a low risk of cross contamination between ACS. The expected use cases is a single database per ACS + Date.
        metadata = self.db.get_all_data(ACSMetadataTable.name)[0]
        metadata = dict(zip(ACSMetadataTable.fields, metadata))
        for k, v in metadata.items():
            if k in ['wavelengths_a', 'wavelengths_c', 'offsets_a', 'offsets_c', 'temperature_bins','delta_t_a','delta_t_c']:
                metadata[k] = json.loads(v)

        return metadata

    def build_metdata_dataset(self):
        metadata = self.metadata

        ds = xr.Dataset()
        ds = ds.assign_coords({'wavelength_c': metadata['wavelengths_c'], 'wavelength_a': metadata['wavelengths_c'], 'temperature_bins': metadata['temperature_bins']})
        ds['offset_a'] = (['wavelength_a'], metadata['offsets_a'])
        ds['offset_c'] = (['wavelength_c'], metadata['offsets_c'])
        ds['delta_t_a'] = (['wavelength_a','temperature_bins'], metadata['delta_t_a'])
        ds['delta_t_c'] = (['wavelength_c','temperature_bins'], metadata['delta_t_c'])

        ds.attrs['sensor_type'] = self.metadata['sensor_type']
        ds.attrs['serial_number'] = self.metadata["serial_number"]
        ds.attrs['serial_number_hexdec'] = self.metadata["serial_number_hexdec"]
        ds.attrs['number_of_wavelengths'] = self.metadata['number_of_wavelengths']
        ds.attrs['number_of_temperature_bins'] = self.metadata['number_of_temperature_bins']
        ds.attrs['baudrate'] = self.metadata['baudrate']
        ds.attrs['tcal'] = self.metadata['tcal']
        ds.attrs['ical'] = self.metadata['ical']
        ds.attrs['factory_calibration_structure_version'] = self.metadata['structure_version']
        ds.attrs['calibration_filename'] = self.metadata['calibration_filename']
        ds.attrs['factory_calibration_date'] = self.metadata['factory_calibration_date']

        # Assign variable level attributes.
        for coord in list(ds.coords):
            _attr = self.attrs[coord]
            for k, v in _attr.items():
                ds[coord].attrs[k] = v
        for var in list(ds.data_vars):
            _attr = self.attrs[var]
            for k, v in _attr.items():
                ds[var].attrs[k] = v


        return ds


    def build_flag_dataset(self):
        table = ACSFlagsTable.name
        fields = ACSFlagsTable.fields
        d = np.array(self.db.get_all_data(table))
        data = {}
        for field in fields:
            idx = fields.index(field)
            data[field] = d[:, idx]

        for k, d in data.items():
            if k in ['flag_gross_range_test_a_m', 'flag_gross_range_test_c_m']:
                data[k] = [json.loads(v.item()) for v in d]
        for coord in ['time']:
            data[coord] = data[coord].astype('datetime64[ns]')
        for var in ['flag_syntax_test', 'flag_gap_test', 'flag_elapsed_time', 'flag_outside_temperature_calibration']:
            data[var] = data[var].astype(np.int8)

        ds = xr.Dataset()
        ds = ds.assign_coords({'time': data['time']})
        ds['flag_gross_range_test_a_m'] = (['time', 'wavelength_a'], data['flag_gross_range_test_a_m'])
        ds['flag_gross_range_test_c_m'] = (['time', 'wavelength_c'], data['flag_gross_range_test_c_m'])

        ds['flag_syntax_test'] = (['time'], data['flag_syntax_test'])
        ds['flag_gap_test'] = (['time'], data['flag_gap_test'])

        ds['flag_elapsed_time'] = (['time'], data['flag_elapsed_time'])
        ds['flag_outside_temperature_calibration'] = (['time'], data['flag_outside_temperature_calibration'])

        # Assign dataset level attributes.
        ds.attrs['sensor_type'] = self.metadata['sensor_type']
        ds.attrs['serial_number'] = self.metadata["serial_number"]
        ds.attrs['serial_number_hexdec'] = self.metadata["serial_number_hexdec"]
        ds.attrs['number_of_wavelengths'] = self.metadata['number_of_wavelengths']
        ds.attrs['number_of_temperature_bins'] = self.metadata['number_of_temperature_bins']
        ds.attrs['baudrate'] = self.metadata['baudrate']
        ds.attrs['tcal'] = self.metadata['tcal']
        ds.attrs['ical'] = self.metadata['ical']
        ds.attrs['factory_calibration_structure_version'] = self.metadata['structure_version']
        ds.attrs['calibration_filename'] = self.metadata['calibration_filename']
        ds.attrs['factory_calibration_date'] = self.metadata['factory_calibration_date']

        # Assign variable level attributes.
        for coord in list(ds.coords):
            _attr = self.attrs[coord]
            for k, v in _attr.items():
                ds[coord].attrs[k] = v
        for var in list(ds.data_vars):
            _attr = self.attrs[var]
            for k, v in _attr.items():
                ds[var].attrs[k] = v

        return ds

    def build_converted_dataset(self):
        fields = ['time', 'a_m', 'a_uncorr', 'c_m', 'c_uncorr', 'internal_temperature', 'external_temperature']

        table = ACSDataTable.name
        d = np.array(self.db.select_data(table, fields))

        data = {}
        for field in fields:
            idx = fields.index(field)
            data[field] = d[:, idx]
        for k, d in data.items():
            if k in ['a_m', 'a_uncorr', 'c_m', 'c_uncorr']:
                data[k] = [json.loads(v.item()) for v in d]
        for coord in ['time']:
            data[coord] = data[coord].astype('datetime64[ns]')
        for var in ['internal_temperature', 'external_temperature']:
            data[var] = data[var].astype(np.float32)

        ds = xr.Dataset()
        ds = ds.assign_coords({'time': data['time'], 'wavelength_c': self.metadata['wavelengths_c'],
                               'wavelength_a': self.metadata['wavelengths_a']})
        ds['a_uncorr'] = (['time', 'wavelength_a'], data['a_uncorr'])
        ds['a_m'] = (['time', 'wavelength_a'], data['a_m'])
        ds['c_uncorr'] = (['time', 'wavelength_c'], data['c_uncorr'])
        ds['c_m'] = (['time', 'wavelength_c'], data['c_m'])
        ds['internal_temperature'] = (['time'], data['internal_temperature'])
        ds['external_temperature'] = (['time'], data['external_temperature'])

        # Assign dataset level attributes.
        ds.attrs['sensor_type'] = self.metadata['sensor_type']
        ds.attrs['serial_number'] = self.metadata["serial_number"]
        ds.attrs['serial_number_hexdec'] = self.metadata["serial_number_hexdec"]
        ds.attrs['number_of_wavelengths'] = self.metadata['number_of_wavelengths']
        ds.attrs['number_of_temperature_bins'] = self.metadata['number_of_temperature_bins']
        ds.attrs['baudrate'] = self.metadata['baudrate']
        ds.attrs['tcal'] = self.metadata['tcal']
        ds.attrs['ical'] = self.metadata['ical']
        ds.attrs['factory_calibration_structure_version'] = self.metadata['structure_version']
        ds.attrs['calibration_filename'] = self.metadata['calibration_filename']
        ds.attrs['factory_calibration_date'] = self.metadata['factory_calibration_date']

        # Assign variable level attributes.
        for coord in list(ds.coords):
            _attr = self.attrs[coord]
            for k, v in _attr.items():
                ds[coord].attrs[k] = v
        for var in list(ds.data_vars):
            _attr = self.attrs[var]
            for k, v in _attr.items():
                ds[var].attrs[k] = v
        return ds

    def build_raw_dataset(self):
        fields = ['time', 'frame_length', 'frame_type', 'a_reference_dark', 'pressure_signal', 'c_signal_dark',
                  'c_reference_dark', 'a_signal_dark', 't_external', 't_internal', 'elapsed_time', 'c_reference',
                  'a_reference', 'c_signal', 'a_signal']

        table = ACSDataTable.name
        d = np.array(self.db.select_data(table, fields))

        data = {}
        for field in fields:
            idx = fields.index(field)
            data[field] = d[:, idx]
        for k, d in data.items():
            if k in ['c_reference', 'a_reference', 'c_signal', 'a_signal']:
                data[k] = [json.loads(v.item()) for v in d]
        for coord in ['time']:
            data[coord] = data[coord].astype('datetime64[ns]')
        for var in ['pressure_signal', 'frame_length', 'frame_type', 'a_reference_dark', 'a_signal_dark', 't_external',
                    't_internal', 'c_reference_dark', 'c_signal_dark']:
            data[var] = data[var].astype(np.int32)
        for var in ['elapsed_time']:
            data[var] = data[var].astype(np.int64)

        ds = xr.Dataset()
        ds = ds.assign_coords({'time': data['time'], 'wavelength_c': self.metadata['wavelengths_c'],
                               'wavelength_a': self.metadata['wavelengths_a']})
        ds['a_signal'] = (['time', 'wavelength_a'], data['a_signal'])
        ds['a_reference'] = (['time', 'wavelength_a'], data['a_reference'])
        ds['c_signal'] = (['time', 'wavelength_c'], data['c_signal'])
        ds['c_reference'] = (['time', 'wavelength_c'], data['c_reference'])

        ds['frame_length'] = (['time'], data['frame_length'])
        ds['frame_type'] = (['time'], data['frame_type'])
        ds['a_reference_dark'] = (['time'], data['a_reference_dark'])
        ds['a_signal_dark'] = (['time'], data['a_signal_dark'])
        ds['pressure_signal'] = (['time'], data['pressure_signal'])
        ds['c_reference_dark'] = (['time'], data['c_reference_dark'])
        ds['c_signal_dark'] = (['time'], data['c_signal_dark'])
        ds['t_external'] = (['time'], data['t_external'])
        ds['t_internal'] = (['time'], data['t_internal'])
        ds['elapsed_time'] = (['time'], data['elapsed_time'])

        # Assign dataset level attributes.
        ds.attrs['sensor_type'] = self.metadata['sensor_type']
        ds.attrs['serial_number'] = self.metadata["serial_number"]
        ds.attrs['serial_number_hexdec'] = self.metadata["serial_number_hexdec"]
        ds.attrs['number_of_wavelengths'] = self.metadata['number_of_wavelengths']
        ds.attrs['number_of_temperature_bins'] = self.metadata['number_of_temperature_bins']
        ds.attrs['baudrate'] = self.metadata['baudrate']
        ds.attrs['tcal'] = self.metadata['tcal']
        ds.attrs['ical'] = self.metadata['ical']
        ds.attrs['factory_calibration_structure_version'] = self.metadata['structure_version']
        ds.attrs['calibration_filename'] = self.metadata['calibration_filename']
        ds.attrs['factory_calibration_date'] = self.metadata['factory_calibration_date']

        # Assign variable level attributes.
        for coord in list(ds.coords):
            _attr = self.attrs[coord]
            for k, v in _attr.items():
                ds[coord].attrs[k] = v
        for var in list(ds.data_vars):
            _attr = self.attrs[var]
            for k, v in _attr.items():
                ds[var].attrs[k] = v
        return ds


def export_netcdf(dbname, output_filename,attrs, progress):
    encoding = {'time': {'units': 'nanoseconds since 1900-01-01'}}
    engine = 'netcdf4'
    output = os.path.join(EXPORT_DIR,output_filename)
    dbl = DBLoader(dbname)
    mds = dbl.build_metdata_dataset()


    root = xr.Dataset()
    root.attrs['sensor_type'] = mds.attrs['sensor_type']
    root.attrs['serial_number'] = mds.attrs["serial_number"]
    root.attrs['serial_number_hexdec'] = mds.attrs["serial_number_hexdec"]
    root.attrs['number_of_wavelengths'] = mds.attrs['number_of_wavelengths']
    root.attrs['baudrate'] = mds.attrs['baudrate']
    root.attrs['calibration_filename'] = mds.attrs['calibration_filename']
    root.attrs['calibration_date'] = mds.attrs['factory_calibration_date']


    progress.setValue(10)
    fds = dbl.build_flag_dataset()
    progress.setValue(25)
    cds = dbl.build_converted_dataset()
    progress.setValue(50)
    rds = dbl.build_raw_dataset()
    progress.setValue(75)
    combo = xr.combine_by_coords([cds,fds])
    progress.setValue(90)


    for attr, val in attrs.items():
        root.attrs[attr] = val
        combo.attrs[attr] = val
        rds.attrs[attr] = val
        mds.attrs[attr] = val

    root.to_netcdf(output, engine = engine)
    combo.to_netcdf(output, encoding = encoding, engine = engine, group = 'converted', mode = 'a')
    progress.setValue(95)
    rds.to_netcdf(output, encoding = encoding, engine = engine, group = 'raw', mode = 'a')
    progress.setValue(99)
    mds.to_netcdf(output,engine = engine, group = 'calibration', mode = 'a')

    if os.path.isfile(output):
        progress.setValue(100)
        return True
    else:
        progress.setValue(-1)
        return False