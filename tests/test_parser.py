"""Regression tests and a CRC check independent of generated frames."""
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from demo import SAMPLE_DATA
from hj212 import HJ212Parser, MessageError

ROOT = Path(__file__).resolve().parents[1]

class ParserTests(unittest.TestCase):
    def setUp(self):
        self.p = HJ212Parser()
        self.message = self.p.build_message(SAMPLE_DATA)

    def frame(self, data):
        return "##{:04d}{}{:04X}\r\n".format(len(data), data, self.p.crc16(data.encode('ascii')))

    def test_known_crc(self):
        self.assertEqual(self.p.crc16(b'123456789'), 0x4B37)
        self.assertEqual(self.p.crc16(b''), 0xFFFF)

    def test_valid_frames(self):
        for message in (self.message, self.message.encode('ascii'),
                        self.message[:-6] + self.message[-6:-2].lower() + '\r\n'):
            self.assertTrue(self.p.is_valid_message(message))
            self.assertTrue(self.p.validate_crc(message))

    def test_invalid_frames(self):
        cases = [None, 123, '', self.message[1:], self.message[:-2],
                 self.message[:-2] + '\n', self.message + self.message,
                 '##0001' + self.message[6:], '##abcd' + self.message[6:],
                 self.message[:-6] + 'ZZZZ\r\n',
                 self.message.replace('ST=32', 'ST=\u4e2d\u6587'),
                 self.message.encode().replace(b'ST=32', b'ST=\xff2')]
        for message in cases:
            with self.subTest(message=repr(message)[:40]):
                self.assertFalse(self.p.is_valid_message(message))
                self.assertFalse(self.p.validate_crc(message))
                with self.assertRaises(MessageError):
                    self.p.parse_data_segment(message)

    def test_crc_tampering(self):
        message = self.message.replace('7.25', '8.25')
        self.assertTrue(self.p.is_valid_message(message))
        self.assertFalse(self.p.validate_crc(message))
        for method in (self.p.parse_data_segment, self.p.parse_cp_fields, self.p.extract_monitoring_data):
            with self.assertRaisesRegex(MessageError, 'CRC mismatch'):
                method(message)

    def test_fields(self):
        self.assertEqual(self.p.parse_data_segment(self.message)['CN'], '2011')
        self.assertEqual(self.p.parse_cp_fields(self.message)['DataTime'], '20260914090000')

    def test_measurements(self):
        self.assertEqual(self.p.extract_monitoring_data(self.message), {
            'w01001': {'Rtd': Decimal('7.25'), 'Flag': 'N'},
            'w01010': {'Rtd': Decimal('23.50'), 'Flag': 'N'}})

    def test_empty_cp(self):
        self.assertEqual(self.p.extract_monitoring_data(self.frame('ST=32;CP=&&&&')), {})

    def test_equal_sign_values(self):
        message = self.frame('ST=32;Note=a=b;CP=&&Remark=x=y&&')
        self.assertEqual(self.p.parse_data_segment(message)['Note'], 'a=b')
        self.assertEqual(self.p.parse_cp_fields(message)['Remark'], 'x=y')

    def test_all_numeric_attributes(self):
        message = self.frame('ST=32;CP=&&a01001-Min=-1.2,a01001-Max=1e3,a01001-Avg=0.10,a01001-Cou=10,a01001-Unit=custom&&')
        self.assertEqual(self.p.extract_monitoring_data(message)['a01001'], {
            'Min': Decimal('-1.2'), 'Max': Decimal('1000'), 'Avg': Decimal('0.10'),
            'Cou': Decimal('10'), 'Unit': 'custom'})

    def test_invalid_numeric_values(self):
        for value in ('NaN', 'Infinity', 'abc', '1_000', ' 2', '--1'):
            with self.subTest(value=value):
                with self.assertRaises(MessageError):
                    self.p.extract_monitoring_data(self.frame('ST=32;CP=&&w01001-Rtd=' + value + '&&'))

    def test_bad_fields(self):
        cases = ['ST=32', 'ST=32;CP=abc', 'ST=32;CP=&&x=1&',
                 'ST=32;ST=21;CP=&&&&', 'ST=;CP=&&&&', 'ST32;CP=&&&&',
                 'ST=32;CP=&&x=1;x=2&&', 'ST=32;CP=&&x=&&',
                 'ST=32;CP=&&x=1;&&', 'ST=32;CP=&&x=1&&;CN=2011',
                 'ST=32;CP=&&w01001-Rtd=1,w01001-Rtd=2&&',
                 'ST=32;CP=&&x=1&&;CP=&&y=2&&', 'ST=32;CP=old;CP=&&&&']
        for data in cases:
            with self.subTest(data=data):
                message = self.frame(data)
                self.assertFalse(self.p.is_valid_message(message))
                with self.assertRaises(MessageError):
                    self.p.parse_data_segment(message)

    def test_control_characters(self):
        for character in ('\n', '\t', '\x00', '\x7f'):
            self.assertFalse(self.p.is_valid_message(self.frame('ST=32;CP=&&x=' + character + '&&')))

    def test_size_boundary(self):
        prefix, suffix = 'ST=32;CP=&&Note=', '&&'
        data = prefix + 'x' * (1024 - len(prefix) - len(suffix)) + suffix
        self.assertTrue(self.p.is_valid_message(self.p.build_message(data)))
        with self.assertRaises(MessageError):
            self.p.build_message(prefix + 'x' * (1025 - len(prefix) - len(suffix)) + suffix)

    def test_builder_type(self):
        with self.assertRaises(MessageError):
            self.p.build_message(b'ST=32;CP=&&&&')

    def test_hello_world(self):
        result = subprocess.run([sys.executable, str(ROOT / 'hello_world.py')], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, 'Hello World\n')

    def test_demo(self):
        result = subprocess.run([sys.executable, str(ROOT / 'demo.py')], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        self.assertTrue(output['crc_valid'])
        self.assertEqual(output['monitoring_data']['w01001']['Rtd'], '7.25')

    def test_file_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'message.txt'
            path.write_bytes(self.message.encode('ascii'))
            result = subprocess.run([sys.executable, str(ROOT / 'demo.py'), str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            path.write_bytes(b'bad frame')
            result = subprocess.run([sys.executable, str(ROOT / 'demo.py'), str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Error', result.stderr.title())

if __name__ == '__main__':
    unittest.main()
