from datetime import timedelta
import numpy as np
import struct

class FLAGS:
    OK: int = 1
    PASS: int = 1
    NOT_EVALUATED: int = 2
    SUSPECT: int = 3
    HIGH_INTEREST: int = 3
    FAIL: int = 4
    MISSING_DATA: int = 9



@staticmethod
def gap_test(now, tim_stmp, buffer_length, frame_length, time_inc = 0.25):
    if now - tim_stmp > timedelta(seconds = time_inc): # Defined in QARTOD Ocean Optics Manual.
        return FLAGS.FAIL
    elif buffer_length > frame_length:
        """
        This is a custom take on the gap test. 
        If for some reason the buffer length exceeds the previous frame length, that would indicate that
        the buffer is filling up faster than the packets can be unpacked. This would ultimately result in the timestamp
        of the value being off by one or multiple 250ms periods, depending on the buffer length. This would also indicate 
        an issue with the timing of the data acquisition thread.
        """
        return FLAGS.FAIL

    else:
        return FLAGS.PASS

@staticmethod
def syntax_test(rec_char, nchar, checksum):
    if len(rec_char) - 3 != nchar:
        return FLAGS.FAIL
    elif np.uint16(sum(rec_char[:-3])) != struct.unpack_from('!H', checksum): # Taken from Inlinino.
        return FLAGS.FAIL
    else:
        return FLAGS.PASS

@staticmethod
def location_test():
    """NOT IMPLEMENTED"""
    return FLAGS.MISSING_DATA

@staticmethod
def gross_range_test(oon, sensor_min = -0.05, sensor_max = 10, op_min =0.001,  op_max = 10):
    """
    According to the manual, the dynamic range of the sensor is 0.001 to 10. However, in the processing
    protocols, there is a call for values between -0.005 and 0 to be considered equivalent to 0.

    Thus, the decision was made to flag values outside -0.005 and 10 as FAIL and values between 0.001 and 10 as SUSPECT.
    It is important to note that a_m and c_m represent data that has not had temperature-salinity-scattering correction.
    The flags associated with this gross range test should be taken lightly and used as an indicator to assess data validity
    after correction has been applied. After correction, if the value is within the anticipated sensor range, then it is probably acceptable.

    :param oon:
    :param sensor_min:
    :param sensor_max:
    :param op_min:
    :param op_max:
    :return:
    """


    oon = np.array(oon)
    flag = np.where((oon < sensor_min) | (oon > sensor_max), FLAGS.FAIL, FLAGS.PASS)
    flag = np.where((oon > op_min) & (oon < op_max), flag, FLAGS.SUSPECT)
    return flag.tolist()

@staticmethod
def elapsed_time_test(elapsed_time: int, fail_lim = 60 * 1000, suspect_lim = 240 * 1000):
    if elapsed_time <= fail_lim:
        flag = FLAGS.FAIL
    elif fail_lim < elapsed_time <= suspect_lim:
        flag = FLAGS.SUSPECT
    else:
        flag = FLAGS.PASS
    return flag

@staticmethod
def outside_temperature_calibration_test(internal_temperature, tmin, tmax):
    if tmin <= internal_temperature <= tmax:
        return FLAGS.PASS
    else:
        return FLAGS.FAIL


