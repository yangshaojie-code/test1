"""Run a generated HJ212 example or parse a message file."""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from hj212 import HJ212Parser, MessageError

SAMPLE_DATA = ("QN=20260914090000000;ST=32;CN=2011;PW=123456;MN=TEST0000000001;Flag=4;"
               "CP=&&DataTime=20260914090000;"
               "w01001-Rtd=7.25,w01001-Flag=N;"
               "w01010-Rtd=23.50,w01010-Flag=N&&")

def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)

def main():
    parser = HJ212Parser()
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("message_file", nargs="?", type=Path)
    args = cli.parse_args()
    try:
        message = args.message_file.read_bytes() if args.message_file else parser.build_message(SAMPLE_DATA)
        result = {
            "message": message.decode("ascii") if isinstance(message, bytes) else message,
            "format_valid": parser.is_valid_message(message),
            "crc_valid": parser.validate_crc(message),
            "data_segment": parser.parse_data_segment(message),
            "cp_fields": parser.parse_cp_fields(message),
            "monitoring_data": parser.extract_monitoring_data(message),
        }
        print(json.dumps(result, indent=2, default=json_value))
        return 0
    except (OSError, MessageError, UnicodeError) as exc:
        cli.error(str(exc))

if __name__ == "__main__":
    raise SystemExit(main())
