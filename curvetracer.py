#!/usr/bin/python3

# Samples the currently displayed signal of the active SDS1104X-U channels,
# optionally controlling the DSG1032X by enabling a sine wave on one channel and
# stepping through a series of DC voltages on another channel.
# Without arguments, this script produces a snapshot of the current trace.
#
# Prerequisites:
# - pip3 install -U pyvisa
# - pip3 install -U matplotlib
#
# (c) 2024 Sander Berents
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
	"""Small delay for DSO or AWG command processing."""
	time.sleep(0.5)
	dso.query("*OPC?")
	
def position_gate_init(t, dt):
	dso.write(f"MEGA {t - dt / 2}s")
	dso.write(f"MEGB {t + dt / 2}s")
	
def position_gate(t, dt):
	dso.write(f"MEGB {t + dt / 2}s")
	dso.write(f"MEGA {t - dt / 2}s")

def plot(iterations, xpts, ypts, channels):
	"""Plots V of given channels."""
	colors = [ 'gold', 'magenta', 'cyan', 'limegreen' ]
	fig, ax1 = plt.subplots()
	ax1.set_title("Curve Tracer (V/t)")
	ax1.set_xlabel("Time [s]")
	ax1.set_ylabel("Voltage [V]")
	for i in range(0, iterations):
		for idx, ch in enumerate(channels):
			label = ch if i == 0 else None
			ax1.plot(xpts[i], ypts[i][idx], color=colors[idx], label=label)
	ax1.legend()

def plotxy(iterations, ypts, channels, dclabels):
	"""Plots X/Y."""
	fig, ax1 = plt.subplots()
	ax1.set_title(f"Curve Tracer ({channels[1]}/{channels[0]})")
	ax1.set_xlabel("Voltage [V]")
	ax1.set_ylabel("Voltage [V]")
	for i in range(0, iterations):
		label = dclabels[i] if len(dclabels) > 0 else None
		ax1.plot(ypts[i][0], ypts[i][1], label=label)
	if len(dclabels) > 0: ax1.legend()
	
parser = argparse.ArgumentParser(
	description="Curve Tracer",
	epilog="Samples signal of active DSO channels, optionally enabling a sine wave and stepping through a series of DC voltages with the AWG."
)
parser.add_argument('-awg', type=int, choices=range(0, 3), dest='cawg', default=0, metavar='awgchannel', help="AWG sine wave output channel ([1,2])")
parser.add_argument('-amp', type=float, dest='amp', default=2, metavar='amplitude', help="Sine wave amplitude in V (default is 2)")
parser.add_argument('-o', type=float, dest='offset', default=0, metavar='offset', help="Sine wave offset in V (default is 0)")
parser.add_argument('-f', type=int, dest='freq', default=1000, metavar='freq', help="Sine wave frequency in Hz (default is 1000)")
parser.add_argument('-dcawg', type=int, choices=range(0, 3), dest='dcawg', default=0, metavar='awgchannel', help="AWG DC output channel ([1,2])")
parser.add_argument('-vmin', type=float, dest='vmin', default=0, metavar='vmin', help="AWG minimum DC voltage (default is 0)")
parser.add_argument('-vmax', type=float, dest='vmax', default=2, metavar='vmax', help="AWG maximum DC voltage (default is 2)")
parser.add_argument('-n', type=int, choices=range(1, 11), dest='iterations', default=5, metavar='steps', help="Number of DC steps (default is 5)")
parser.add_argument('-q', type=int, choices=range(1, 11), dest='quality', default=1, metavar='quality', help="Output quality ([1-10], default is 1)")
args = parser.parse_args()

channels = active_channels()
if (len(channels) == 0): sys.exit()
if (args.cawg != 0 and args.cawg == args.dcawg):
	errprint(f"Invalid AWG output channel")
	sys.exit(3)
	
cawgch = f"C{args.cawg}"
dcawgch = f"C{args.dcawg}"
dvawg = 0
vawg = args.vmin
iterations = 1

if args.cawg != 0:
	# AWG setup: sine wave, amplitude, HiZ output ON
	awg.write(f"{cawgch}:OUTP LOAD,HZ,PLRT,NOR")
	awg.write(f"{cawgch}:BSWV WVTP,SINE")
	awg.write(f"{cawgch}:BSWV FRQ,{args.freq}")
	awg.write(f"{cawgch}:BSWV OFST,{args.offset}")
	awg.write(f"{cawgch}:BSWV AMP,{args.amp}")
	awg.write(f"{cawgch}:OUTP ON")

if args.dcawg != 0:
	# AWG setup: DC, offset, HiZ output ON
	awg.write(f"{dcawgch}:BSWV WVTP,DC")
	awg.write(f"{dcawgch}:OUTP LOAD,HZ,PLRT,NOR")
	awg.write(f"{dcawgch}:BSWV OFST,{args.vmin}")
	awg.write(f"{dcawgch}:OUTP ON")
	if args.iterations > 1: dvawg = (args.vmax - args.vmin) / (args.iterations - 1)
	iterations = args.iterations
	
xpts = []
ypts = []
dclabels = []

print("  AWG DCV,      [s]", end='')
for ch in channels: print(f",{ch:>9}", end='')
print()

dso.write(f"XYDS OFF")
dso.write(f"PACU ALL,{channels[0]}")
dso.write(f"MEGS ON")
wait()

hdiv = measure_hscale();
dt = hdiv / 4 / args.quality
dt2 = dt / 2
for i in range(0, iterations):
	dso.write(f"STOP")
	if args.dcawg != 0:
		awg.write(f"{dcawgch}:BSWV OFST,{vawg}")
		dclabels.append(f"{vawg:.2f}V")
	dso.write(f"ARM")
	wait()

	t = -7 * hdiv + dt2
	position_gate_init(t, dt2)
	xpts.append([])
	ypts.append([])
	for ch in channels: ypts[i].append([])
	while t <= 7 * hdiv - dt2:
		print(f"{vawg:9.5f},", end='')
		xpts[i].append(t)
		print(f"{t / hdiv:9.3f}", end='')
		position_gate(t, dt)
		wait()
		for idx, ch in enumerate(channels):
			v = measure_mean(ch)
			ypts[i][idx].append(v)
			print(f",{v:9.5f}", end='')
		print()
		t = t + dt
	vawg = vawg + dvawg

dso.write(f"MEGS OFF")

if awg != None:
	if args.cawg != 0: awg.write(f"{cawgch}:OUTP OFF")
	if args.dcawg != 0: awg.write(f"{dcawgch}:OUTP OFF")
close_resources()

plt.figure()
plot(iterations, xpts, ypts, channels)
plt.figure()
if (len(channels) > 1):
	plotxy(iterations, ypts, channels, dclabels)
plt.show()
