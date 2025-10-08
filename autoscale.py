#!/usr/bin/python3

# Optimizes vertical offset and scale of active scope channels.
# Assumes that the minimum and maximum values of the signals each fit within the
# screen limits before the script is executed.
#
# Prerequisites:
# - pip3 install -U pyvisa
# - pip3 install -U matplotlib
#
# (c) 2024 Sander Berents
# Published under GNU General Public License v3.0. See file "LICENSE" for full license text.

import time
import argparse
import pyvisa
from eelib import *

parser = argparse.ArgumentParser(
	description="Autoscale",
	epilog="Optimizes vertical offset and scale of active scope channels."
)
parser.add_argument('-d', type=float, dest='vdiv', default=7.5, metavar='vdiv', help="Vertical divisions (default is 7.5)")
parser.add_argument('-i', type=int, dest='iterations', default=2, metavar='iterations', help="Number of iterations (default is 2)")
args = parser.parse_args()

channels = active_channels()
for idx, ch in enumerate(channels):
	vautoscale(ch, args.iterations, args.vdiv)

close_resources()
