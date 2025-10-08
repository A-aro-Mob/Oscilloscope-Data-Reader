#!/usr/bin/python3

# Fetches and plots up to 14,000 data points from the active SDS1104X-U scope channels, 
# optionally averaging multiple sweeps.
#
# Prerequisites:
# - pip3 install -U pyvisa
# - pip3 install -U matplotlib
#
# (c) 2025 Sander Berents
# Published under GNU General Public License v3.0. See file "LICENSE" for full license text.

import sys
import time
import datetime
import re
import argparse
import pyvisa
import matplotlib.pyplot as plt
from eelib import *

def wait():
	"""Small delay for DSO command processing."""
	time.sleep(0.1)
	dso.query("*OPC?")

def plot(xpts, ypts, channels):
	"""Plots V of given channels."""
	colors = [ 'gold', 'magenta', 'cyan', 'limegreen' ]
	fig, ax1 = plt.subplots()
	ax1.set_xlabel("Time [s]")
	ax1.set_ylabel("Voltage [V]")
	for idx, ch in enumerate(channels):
		ax1.plot(xpts, ypts[idx], color=colors[idx], label=ch)
	ax1.legend()
	plt.show()
		
parser = argparse.ArgumentParser(
	description="Plot",
	epilog="Fetches and plots up to 14,000 data points from the active SDS1104X-U scope channels, optionally averaging multiple sweeps."
)
parser.add_argument('-n', type=int, dest='navg', default=1, metavar='navg', help="Number of sweeps to average (default is 1)")
args = parser.parse_args()

navg = args.navg

channels = active_channels()
if len(channels) == 0: sys.exit(0)
n = nsamples(channels[0])
if n > 14000:
	errprint(f"Error: Waveform fetching is limited to 14,000 data points")
	sys.exit(1)
for ch in channels:
	if nsamples(ch) != n:
		errprint(f"Error: Data points inconsistency")
		sys.exit(2)

hdiv = measure_hscale();
ypts = []

for i in range(0, navg):
	if i > 0: wait()
	dso.write(f"STOP")
	for c, ch in enumerate(channels):
		errprint(f"Fetching {n} data points of {ch} (sweep {i + 1} of {navg})")
		data = fetch(ch)
		if i == 0: ypts.append([0] * n)
		for j in range(0, n): ypts[c][j] = ypts[c][j] + data[j]
	dso.write(f"ARM")

for c, ch in enumerate(channels):
	for j in range(0, n): ypts[c][j] = ypts[c][j] / navg

close_resources()

t = -7 * hdiv
dt = hdiv * 14 / n
xpts = []
for j in range(0, n):
	xpts.append(t)
	t = t + dt
plot(xpts, ypts, channels)
