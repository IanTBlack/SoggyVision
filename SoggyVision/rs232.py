import serial
import serial.tools.list_ports


class RS232():
    def __init__(self):
        self._serial = serial.Serial()

        self._available_ports = self.list_available_ports()

    def list_available_ports(self):
        available_ports = [v.name for v in serial.tools.list_ports.comports()]
        return available_ports

    def __enter__(self):
        return self


    def __exit__(self,et, ev, etb):
        self.disconnect()

    def connect(self, port, baudrate, bytesize = 8, parity = 'N', stopbits = 1, flowcontrol = 0, timeout = 1):
        self._serial.port = port
        self._serial.baudrate = int(baudrate)
        self._serial.bytesize = bytesize
        self._serial.parity = parity
        self._serial.stopbits = stopbits
        self._serial.xonxoff = flowcontrol
        self._serial.timeout = int(timeout)
        try:
            self._serial.open()
            return True
        except ConnectionError:
            raise serial.PortNotOpenError()


    def clear_buffers(self):
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()


    def read_buffer(self):
        buffer = self._serial.read(self._serial.in_waiting)
        return buffer

    def disconnect(self):
        self._serial.close()

