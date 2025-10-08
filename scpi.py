#!/usr/bin/python3

# SCPI Utility for SDS1104X-U, DSG1032X and SPD4323X.
#
# Prerequisites:
# - pip3 install -U pyvisa
#
# (c) 2024-2025 Sander Berents
# Published under GNU General Public License v3.0. See file "LICENSE" for full license text.

import argparse
import pyvisa
from eelib import *

parser = argparse.ArgumentParser(
	description="SCPI Utility",
	epilog="Submit SCPI query or command to SDS1104X-U, DSG1032X or SPD4323X."
)
parser.add_argument('target', type=str, choices=('dso', 'awg', 'psu'), metavar='target', help="Target instrument (one of 'dso', 'awg' or 'psu')")
parser.add_argument('command', type=str, metavar='command', help="SCPI query or command")
parser.add_argument('-x', action='store_true', dest='hex', help="Output query result as byte array")
args = parser.parse_args()

instr = resources[args.target]

if "?" in args.command:
	if args.hex:
		instr.write(args.command)
		print(instr.read_raw())
	else:
		print(instr.query(args.command).strip())
else:
	instr.write(args.command)

close_resources()
