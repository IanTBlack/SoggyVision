from datetime import datetime
import numpy as np
import re
from scipy import interpolate
from struct import calcsize
import xarray as xr
import os


class Dev():
    """
    A class for parsing ACS calibration (.dev) files.
    These files are necessary for performing corrections.

    This class can be instantiated and data can be accessed as class attributes.
    Alternatively, the to_ds() function will format calibration data so that it can be used with
    operations based in xarray. The to_nc() function will export calibration data as a netcdf.
    """

    def __init__(self, filepath: os.path.abspath) -> None:
        """
        Parse the .dev file.

        :param filepath: The location of the dev file.
        """
        self.filepath = os.path.normpath(filepath)
        self.__read_dev()
        self.__parse_metadata()
        self.__parse_tbins()
        self.__parse_offsets()
        self.__check_parse()
        self.__build_packet_header()

    def __read_dev(self) -> None:
        """Import the .dev file as a text file."""

        with open(self.filepath, 'r') as _file:
            self._lines = _file.readlines()

    def __parse_metadata(self) -> None:
        """Parse the .dev file for sensor metadata."""

        metadata_lines = [line for line in self._lines if 'C and A offset' not in line]
        for line in metadata_lines:
            if 'ACS Meter' in line:
                self.sensor_type = re.findall('(.*?)\n', line)[0]
            elif 'Serial' in line:
                self.sn_hexdec = re.findall('(.*?)\t', line)[0]
                self.sn = 'ACS-' + str(int(self.sn_hexdec[-6:], 16)).zfill(5)
            elif 'structure version' in line:
                self.structure_version = int(re.findall('(.*?)\t', line)[0])
            elif 'tcal' in line:
                self.tcal, self.ical = [float(v) for v in re.findall(': [+-]?([0-9]*[.]?[0-9]+) C', line)]
                cal_date_str = re.findall('file on (.*?)[.].*?\n', line)[0].replace(' ', '')
                try:
                    self.cal_date = datetime.strptime(cal_date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                except:
                    self.cal_date = datetime.strptime(cal_date_str, '%m/%d/%y').strftime('%Y-%m-%d')
            elif 'Depth calibration' in line:
                (self.depth_cal_1,
                 self.depth_cal_2) = [float(v) for v in re.findall('[+-]?([0-9]*[.]?[0-9]+)\t', line)]
            elif 'Baud' in line:
                self.baudrate = int(re.findall('(.*?)\t', line)[0])
            elif 'Path' in line:
                self.path_length = float(re.findall('(.*?)\t', line)[0])
            elif 'wavelengths' in line:
                self.output_wavelengths = int(re.findall('(.*?)\t', line)[0])
            elif 'number of temperature bins' in line:
                self.num_tbins = int(re.findall('(.*?)\t', line)[0])
            elif 'maxANoise' in line:
                (self.max_a_noise, self.max_c_noise, self.max_a_nonconform, self.max_c_nonconform,
                 self.max_a_difference, self.max_c_difference, self.min_a_counts,
                 self.min_c_counts, self.min_r_counts, self.max_tempsdev,
                 self.max_depth_sdev) = [float(v) for v in re.findall('[+-]?([0-9]*[.]?[0-9]+)\t', line)]

    def __parse_tbins(self) -> None:
        """Parse the .dev file for temperature bin information."""

        line = [line for line in self._lines if '; temperature bins' in line][0]
        tbins = line.split('\t')
        tbins = [v for v in tbins if v]
        tbins = [v for v in tbins if v != '\n']
        tbins = [float(v) for v in tbins if 'temperature bins' not in v]
        self.tbins = np.array(tbins)

    def __parse_offsets(self) -> None:
        """Parse the .dev file for a and c offsets."""

        offset_lines = [line for line in self._lines if 'C and A offset' in line]
        c_wavelengths = []
        a_wavelengths = []
        c_offsets = []
        a_offsets = []
        c_deltas = []
        a_deltas = []
        for line in offset_lines:
            offsets, c_delta, a_delta = line.split('\t\t')[:-1]
            wavelength_c, wavelength_a, _, offset_c, offset_a = offsets.split('\t')
            wavelength_c = float(wavelength_c.replace('C', ''))
            wavelength_a = float(wavelength_a.replace('A', ''))
            c_wavelengths.append(wavelength_c)
            a_wavelengths.append(wavelength_a)
            offset_c = float(offset_c)
            offset_a = float(offset_a)
            c_offsets.append(offset_c)
            a_offsets.append(offset_a)
            c_delta = np.array([float(v) for v in c_delta.split('\t')])
            a_delta = np.array([float(v) for v in a_delta.split('\t')])
            c_deltas.append(c_delta)
            a_deltas.append(a_delta)
        self.wavelength_c = np.array(c_wavelengths)
        self.wavelength_a = np.array(a_wavelengths)
        self.offset_c = np.array(c_offsets)
        self.offset_a = np.array(a_offsets)
        self.delta_t_c = np.array(c_deltas)
        self.delta_t_a = np.array(a_deltas)
        self.f_delta_t_c = interpolate.interp1d(self.tbins, self.delta_t_c, axis=1, assume_sorted=True, copy=False,
                                                bounds_error=False,
                                                fill_value=(self.delta_t_c[:, 1], self.delta_t_c[:, -1]))
        self.f_delta_t_a = interpolate.interp1d(self.tbins, self.delta_t_a, axis=1, assume_sorted=True, copy=False,
                                                bounds_error=False,
                                                fill_value=(self.delta_t_a[:, 1], self.delta_t_a[:, -1]))

    def __build_packet_header(self) -> None:
        """
        Build a packet descriptor for parsing binary ACS packets.
        Only used when reading raw binary from a file or over serial.
        """

        self.PACKET_REGISTRATION = b'\xff\x00\xff\x00'
        self.LEN_PACKET_REGISTRATION = len(self.PACKET_REGISTRATION)
        self.PACKET_HEADER = '!HBBlHHHHHHHIBB'
        self.LEN_PACKET_HEADER = calcsize(self.PACKET_HEADER)

        self.packet_header = self.PACKET_HEADER
        for i in range(self.output_wavelengths):
            self.packet_header += 'HHHH'
        self.packet_length = self.LEN_PACKET_REGISTRATION + calcsize(self.packet_header)

    def __check_parse(self) -> None:
        """Verify that the parse obtained the correct informatoin."""

        if len(self.wavelength_c) != len(self.wavelength_a):
            raise ValueError('Mismatch between number of wavelengths extracted for A and C.')
        if self.delta_t_c.shape != (len(self.wavelength_c), self.num_tbins):
            raise ValueError('Mismatch between length of C wavelengths and number of temperature bins.')
        if self.delta_t_a.shape != (len(self.wavelength_a), self.num_tbins):
            raise ValueError('Mismatch between length of A wavelengths and number of temperature bins.')

    def to_ds(self) -> xr.Dataset:
        """
        Export class attributes as an xr.Dataset.

        :return: An xarray dataset containing calibration information.
        """

        ds = xr.Dataset()
        ds = ds.assign_coords({'wavelength_a': self.wavelength_a})
        ds = ds.assign_coords({'wavelength_c': self.wavelength_c})
        ds = ds.assign_coords({'temperature_bins': self.tbins})

        ds['offsets_a'] = (['wavelength_a'], np.array(self.offset_a))
        ds['delta_t_a'] = (['wavelength_a', 'temperature_bins'], np.array(self.delta_t_a))

        ds['offsets_c'] = (['wavelength_c'], np.array(self.offset_c))
        ds['delta_t_c'] = (['wavelength_c', 'temperature_bins'], np.array(self.delta_t_c))

        ds.attrs['sensor_type'] = self.sensor_type
        ds.attrs['serial_number'] = self.sn
        ds.attrs['factory_calibration_date'] = self.cal_date
        ds.attrs['output_wavelengths'] = self.output_wavelengths
        ds.attrs['number_temp_bins'] = self.num_tbins
        ds.attrs['path_length'] = self.path_length
        ds.attrs['tcal'] = self.tcal
        ds.attrs['ical'] = self.ical
        ds.attrs['baudrate'] = self.baudrate
        ds.attrs['dev_structure_version'] = self.structure_version
        return ds

    def to_nc(self, out_filepath: os.path.abspath) -> None:
        """
        Export .dev data as a netcdf.

        :param out_filepath:
        """

        split = os.path.splitext(out_filepath)
        if split[-1] != '.nc':
            out_filepath += '.nc'
        ds = self.to_ds()
        ds.to_netcdf(out_filepath, engine='netcdf4')