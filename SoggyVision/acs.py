import struct
import numpy as np
from struct import error as struct_error
from typing import NamedTuple
import os


from SoggyVision.dev import Dev
from SoggyVision.qc import gross_range_test, elapsed_time_test, outside_temperature_calibration_test

class ACSMetadata(NamedTuple):
    begin_time: str
    sensor_type: str
    calibration_filepath: str
    calibration_filename: str
    factory_calibration_date: str
    serial_number: str
    serial_number_hexdec: str
    wavelengths_c: list
    wavelengths_a: list
    baudrate: int
    path_length: float
    tcal: float
    ical: float
    structure_version: int
    number_of_wavelengths: int
    number_of_temperature_bins: int
    temperature_bins: list
    offsets_a: list
    offsets_c: list
    delta_t_a: list
    delta_t_c: list
    end_time: str


class ACSFlags(NamedTuple):
    time: str
    flag_elapsed_time: int
    flag_syntax_test: int
    flag_gap_test: int
    flag_gross_range_test_a_m: int
    flag_gross_range_test_c_m: int
    flag_outside_temperature_calibration: int

class ACSData(NamedTuple):
    time : str
    frame: bytes
    frame_length: int
    frame_type: int
    serial_number_hexdec: bytes
    a_reference_dark: int
    pressure_signal: int
    a_signal_dark: int
    t_external: int
    t_internal: int
    c_reference_dark: int
    c_signal_dark: int
    elapsed_time: int
    number_of_wavelengths: int
    c_reference: list
    a_reference: list
    c_signal: list
    a_signal: list
    a_uncorr: list
    c_uncorr: list
    a_m: list
    c_m: list
    internal_temperature: float
    external_temperature: float


class ACS(Dev):
    def __init__(self, filepath):
        super().__init__(filepath)
        self.reset_buffer()

    def reset_buffer(self):
        self._buffer = bytearray()

    def find_packet(self, buffer):
        """
        Find the first and complete frame from the buffer
        :param buffer: byte array
        :return: frame: first frame found
                 checksum: boolean indicating if valid or invalid frame
                 buffer_post_frame: buffer left after the frame
                 buffer_pre_frame: buffer preceding the first frame returned (likely unknown frame header)
        """
        try:

            i = buffer.index(self.PACKET_REGISTRATION) # Look for registration bytes
            while buffer.find(self.PACKET_REGISTRATION, i + 2, i + 2 + self.LEN_PACKET_REGISTRATION) != -1:
                i += 2
            frame_end_index = i + self.packet_length
            frame = buffer[i:frame_end_index]
            checksum = buffer[frame_end_index:frame_end_index + 2]  # Get checksum

            if len(frame) != self.packet_length:
                raise IndexError
            elif len(checksum) != 2:
                raise ValueError



            return (frame, checksum,  buffer[frame_end_index + 2:], buffer[:i])
        except:
            return (None, None, buffer, None)

    def compute_internal_temperature(self,counts: int) -> float:
        counts = np.array(counts).astype('int64')
        volts = 5 * counts / 65535
        resistance = 10000 * volts / (4.516 - volts)
        internal_temperature = 1 / (
                    0.00093135 + 0.000221631 * np.log(resistance) + 0.000000125741 * np.log(resistance) ** 3) - 273.15
        return float(internal_temperature)


    def compute_external_temperature(self,counts: int) -> float:
        counts = np.array(counts).astype('int64')
        a = -7.1023317e-13
        b = 7.09341920e-08
        c = -3.87065673e-03
        d = 95.8241397
        external_temperature = a * counts ** 3 + b * counts ** 2 + c * counts + d
        return float(external_temperature)


    def compute_uncorrected(self, signal_counts: list, reference_counts: list) -> list:
        x = self.path_length
        uncorr = (1 / x) * np.log(np.array(signal_counts) / np.array(reference_counts))
        return uncorr.tolist()


    def compute_measured(self, uncorrected: list, channel: str, internal_temperature: float):
        if channel.lower() == 'a':
            delta_t = self.f_delta_t_a(internal_temperature).T
            offsets = self.offset_a
        elif channel.lower() == 'c':
            delta_t = self.f_delta_t_c(internal_temperature).T
            offsets = self.offset_c
        measured = (offsets - np.array(uncorrected)) - delta_t
        return measured.tolist()


    def get_metadata(self):
        metadata = ACSMetadata(begin_time = None, sensor_type=self.sensor_type, calibration_filepath=self.filepath,
                            calibration_filename=os.path.basename(self.filepath),
                            factory_calibration_date=self.cal_date,
                            serial_number=self.sn,
                            serial_number_hexdec = self.sn_hexdec,
                            wavelengths_c=self.wavelength_c.tolist(),
                            wavelengths_a=self.wavelength_a.tolist(),
                            baudrate=self.baudrate,
                            path_length=self.path_length,
                            tcal = self.tcal,
                            ical = self.ical,
                            structure_version=self.structure_version,
                            number_of_wavelengths=self.output_wavelengths,
                            number_of_temperature_bins=self.num_tbins,
                            temperature_bins=self.tbins.tolist(),
                            offsets_a=self.offset_a.tolist(),
                            offsets_c=self.offset_c.tolist(),
                            delta_t_a=self.delta_t_a.tolist(),
                            delta_t_c=self.delta_t_c.tolist(),
                            end_time = 'placeholder')
        return metadata


    def get_data(self, dt, frame):

        # Unpack the frame.
        raw_data = struct.unpack_from(self.packet_header, frame, offset = self.LEN_PACKET_REGISTRATION)

        # Assign raw data.
        frame_length=raw_data[0]
        frame_type=raw_data[1]
        serial_number_hexdec=raw_data[3]
        a_reference_dark=raw_data[4]
        pressure_signal=raw_data[5]
        a_signal_dark=raw_data[6]
        t_external=raw_data[7]
        t_internal=raw_data[8]
        c_reference_dark=raw_data[9]
        c_signal_dark=raw_data[10]
        elapsed_time=raw_data[11]
        number_of_wavelengths=raw_data[13]
        c_reference=np.array(raw_data[14::4]).tolist()
        a_reference=np.array(raw_data[15::4]).tolist()
        c_signal=np.array(raw_data[16::4]).tolist()
        a_signal=np.array(raw_data[17::4]).tolist()


        # Convert data.
        internal_temperature = self.compute_internal_temperature(t_internal)
        external_temperature = self.compute_external_temperature(t_external)
        a_uncorr = self.compute_uncorrected(a_signal, a_reference)
        c_uncorr = self.compute_uncorrected(c_signal, c_reference)
        a_m = self.compute_measured(a_uncorr,'a',internal_temperature)
        c_m = self.compute_measured(c_uncorr,'c',internal_temperature)



        data = ACSData(time = dt,
                       frame = frame,
                       frame_length = frame_length,
                       frame_type = frame_type,
                       serial_number_hexdec = serial_number_hexdec,
                       a_reference_dark = a_reference_dark,
                       a_signal_dark= a_signal_dark,
                       pressure_signal = pressure_signal,
                       t_external = t_external,
                       t_internal = t_internal,
                       c_reference_dark = c_reference_dark,
                       c_signal_dark = c_signal_dark,
                       elapsed_time = elapsed_time,
                       number_of_wavelengths = number_of_wavelengths,
                       c_reference = c_reference,
                       a_reference = a_reference,
                       c_signal = c_signal,
                       a_signal = a_signal,
                       a_uncorr = a_uncorr,
                       c_uncorr = c_uncorr,
                       a_m = a_m,
                       c_m = c_m,
                       internal_temperature = internal_temperature,
                       external_temperature = external_temperature)
        return data


    def get_flags(self, data, gap_test_results, syntax_test_results):
        # Flag data.

        flag_data = ACSFlags(time = data.time,
                                flag_elapsed_time = elapsed_time_test(data.elapsed_time),
                                flag_syntax_test = syntax_test_results,
                                flag_gap_test =  gap_test_results,
                                flag_gross_range_test_a_m = gross_range_test(data.a_m),
                                flag_gross_range_test_c_m = gross_range_test(data.c_m),
                                flag_outside_temperature_calibration = outside_temperature_calibration_test(data.internal_temperature, min(self.tbins), max(self.tbins)))
        return flag_data