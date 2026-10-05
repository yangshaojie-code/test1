#test_for_git
import re
from decimal import Decimal, InvalidOperation

class MessageError(ValueError):
    """The message cannot be interpreted safely."""

class HJ212Parser:
    """Parse HJ212 framing and common CP monitoring fields."""
    MAX_DATA_LENGTH = 1024
    NUMERIC_ATTRIBUTES = frozenset({"Rtd", "Avg", "Min", "Max", "Cou"})
    _FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z", re.ASCII)
    _CP_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z][A-Za-z0-9_]*)?\Z", re.ASCII)
    _NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z", re.ASCII)

    @staticmethod
    def crc16(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return crc

    @staticmethod
    def _as_bytes(message):
        if isinstance(message, bytes):
            return message
        if isinstance(message, str):
            try:
                return message.encode("ascii")
            except UnicodeEncodeError as exc:
                raise MessageError("Only ASCII messages are supported") from exc
        raise MessageError("Message must be str or bytes")

    def _split_frame(self, message):
        raw = self._as_bytes(message)
        if not raw.startswith(b"##") or not raw.endswith(b"\r\n"):
            raise MessageError("Expected ## header and CRLF terminator")
        if len(raw) < 12 or re.fullmatch(rb"[0-9]{4}", raw[2:6]) is None:
            raise MessageError("Length must contain four ASCII digits")
        size = int(raw[2:6])
        if not 1 <= size <= self.MAX_DATA_LENGTH or len(raw) != size + 12:
            raise MessageError("Declared length differs from data length")
        data, crc_text = raw[6:6 + size], raw[6 + size:-2]
        if re.fullmatch(rb"[0-9a-fA-F]{4}", crc_text) is None:
            raise MessageError("CRC must contain four hexadecimal digits")
        if any(byte < 32 or byte > 126 for byte in data):
            raise MessageError("Data must contain printable ASCII")
        return data, int(crc_text, 16)

    @staticmethod
    def _put_field(target, token, pattern):
        key, separator, value = token.partition("=")
        if not separator or pattern.fullmatch(key) is None or not value:
            raise MessageError("Malformed or empty field: " + token)
        if key in target:
            raise MessageError("Duplicate field: " + key)
        target[key] = value

    def _parse_cp(self, cp):
        fields = {}
        if cp:
            for token in re.split("[;,]", cp):
                self._put_field(fields, token, self._CP_FIELD)
        return fields

    def _parse_segment(self, data):
        text = data.decode("ascii")
        marker = ";CP=&&"
        if text.count(marker) != 1 or not text.endswith("&&"):
            raise MessageError("Expected one terminal CP field")
        header, cp = text.split(marker, 1)
        cp = cp[:-2]
        if "&" in header or "&" in cp:
            raise MessageError("Unexpected CP delimiter")
        fields = {}
        for token in header.split(";"):
            self._put_field(fields, token, self._FIELD)
        if "CP" in fields:
            raise MessageError("Duplicate CP field")
        self._parse_cp(cp)
        fields["CP"] = cp
        return fields

    def is_valid_message(self, message):
        try:
            data, _ = self._split_frame(message)
            self._parse_segment(data)
            return True
        except MessageError:
            return False

    def validate_crc(self, message):
        try:
            data, expected = self._split_frame(message)
            return self.crc16(data) == expected
        except MessageError:
            return False

    def parse_data_segment(self, message):
        data, expected = self._split_frame(message)
        if self.crc16(data) != expected:
            raise MessageError("CRC mismatch")
        return self._parse_segment(data)

    def parse_cp_fields(self, message):
        return self._parse_cp(self.parse_data_segment(message)["CP"])

    def extract_monitoring_data(self, message):
        factors = {}
        for key, value in self.parse_cp_fields(message).items():
            factor, separator, attribute = key.partition("-")
            if not separator:
                continue
            parsed = value
            if attribute in self.NUMERIC_ATTRIBUTES:
                if self._NUMBER.fullmatch(value) is None:
                    raise MessageError("Invalid numeric measurement: " + key)
                try:
                    parsed = Decimal(value)
                except InvalidOperation as exc:
                    raise MessageError("Invalid numeric measurement: " + key) from exc
            factors.setdefault(factor, {})[attribute] = parsed
        return factors

    def build_message(self, data_segment):
        if not isinstance(data_segment, str):
            raise MessageError("Data segment must be str")
        data = self._as_bytes(data_segment)
        if len(data) > self.MAX_DATA_LENGTH:
            raise MessageError("Data segment is too long")
        message = "##{:04d}{}{:04X}\r\n".format(len(data), data_segment, self.crc16(data))
        if not self.is_valid_message(message):
            raise MessageError("Invalid data segment")
        return message
