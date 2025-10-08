#!/usr/bin/python3

# Creates Bode Plot and CSV output using SDS1104X-U and DSG1032X.
#
# Prerequisites:
# - pip3 install -U pyvisa
# - pip3 install -U matplotlib
#
# (c) 2024 Sander Berents
# Published under GNU General Public License v3.0. See file "LICENSE" for full license text.

import sys
import math
import time
import re
import argparse
import pyvisa
import matplotlib.pyplot as plt
from eelib import *

def wait():
	"""Small delay for DSO or AWG command processing."""
	time.sleep(args.delay)
	time.sleep(0.1)
	awg.query("*OPC?")
	dso.query("*OPC?")

def step(f):
	"""Computes frequency sweep step size for given frequency."""
	p = math.floor(math.log10(f))
	return round((10 ** p) / args.quality)

def plotvpp(xpts, vpps1, vpps2, phases):
	"""Plots Vpp and phase difference of two channels on logarithmic scales."""
	fig, ax1 = plt.subplots()
	ax1.set_title("Bode Plot - Vpp")
	ax1.set_xscale('log')
	ax1.set_yscale('log')
	ax1.set_xlabel("Frequency (Hz)")
	ax1.set_ylabel("Vpp [V]", color='blue')
	ax1.plot(xpts, vpps1, color='gold', label="C1")
	ax1.tick_params(axis ='y', labelcolor='blue')
	ax1.plot(xpts, vpps2, color='magenta', label="C2")
	ax1.legend()
	
	ax2 = ax1.twinx()
	ax2.set_ylabel("Phase [˚]", color='red')
	ax2.plot(xpts, phases, color='red', label="Phase")
	ax2.tick_params(axis ='y', labelcolor='red')
	fig.tight_layout()
	
def plotvdb(xpts, vdbs, phases):
	"""Plots dBV and phase difference on logarithmic scales."""
	fig, ax1 = plt.subplots()
	ax1.set_title("Bode Plot - dbV")
	ax1.set_xscale('log')
	ax1.set_xlabel("Frequency (Hz)")
	ax1.set_ylabel("dBV [dB]", color='blue')
	ax1.plot(xpts, vdbs, color='blue')
	ax1.tick_params(axis ='y', labelcolor='blue')
	
	ax2 = ax1.twinx()
	ax2.set_ylabel("Phase [˚]", color='red')
	ax2.plot(xpts, phases, color='red', label="Phase")
	ax2.tick_params(axis ='y', labelcolor='red')
	fig.tight_layout()

parser = argparse.ArgumentParser(
	description="Bode Plot",
	epilog="Creates Bode Plot and CSV output using SDS1104X-U and DSG1032X."
)
parser.add_argument('-in', type=int, choices=range(1, 5), dest='cin', default=1, metavar='inchannel', help="DSO channel for AWG output ([1-4], default is 1)")
parser.add_argument('-out', type=int, choices=range(1, 5), dest='cout', default=2, metavar='outchannel', help="DSO channel for DUT ([1-4], default is 2)")
parser.add_argument('-awg', type=int, choices=range(1, 3), dest='cawg', default=1, metavar='awgchannel', help="AWG output channel ([1,2], default is 1)")
parser.add_argument('-amp', type=int, dest='amp', default=1, metavar='amplitude', help="AWG sine wave amplitude in V (default is 1)")
parser.add_argument('-fs', type=int, dest='fs', default=1000, metavar='startfreq', help="Sweep start frequency in Hz (default is 1000)")
parser.add_argument('-fe', type=int, dest='fe', default=100000, metavar='endfreq', help="Sweep end frequency in Hz (default is 100000)")
parser.add_argument('-a1', type=int, dest='attn1', default=10, metavar='attenuation', help="Probe attenuation factor for inchannel (default is 10)")
parser.add_argument('-a2', type=int, dest='attn2', default=10, metavar='attenuation', help="Probe attenuation factor for outchannel (default is 10)")
parser.add_argument('-q', type=int, choices=range(1, 11), dest='quality', default=1, metavar='quality', help="Output quality ([1-10], default is 1)")
parser.add_argument('-d', type=float, dest='delay', default=0, metavar='delay', help="Delay between measurements in seconds (default is 0)")
args = parser.parse_args()

awgch = f"C{args.cawg}"
dsoch1 = f"C{args.cin}" # Channel for measuring AWG output
dsoch2 = f"C{args.cout}" # DUT channel

wait()

# AWG setup: sine wave, amplitude, HiZ output ON
awg.write(f"{awgch}:OUTP LOAD,HZ,PLRT,NOR")
awg.write(f"{awgch}:BSWV WVTP,SINE")
awg.write(f"{awgch}:BSWV FRQ,{args.fs}")
awg.write(f"{awgch}:BSWV OFST,0")
awg.write(f"{awgch}:BSWV AMP,{args.amp}")
awg.write(f"{awgch}:OUTP ON")

# DSO general setup
dso.write(f"CHDR SHORT")
dso.write(f"MSIZ 7M")
dso.write(f"MENU ON") # Actually turns the menu off
hs = hscale(args.fs)
dso.write(f"TDIV {hs}")

# DSO channels setup: attenuation, bandwidth limit OFF, DC coupling, zero offset, V unit, 150mV divisions
dso.write(f"{dsoch1}:ATTN {args.attn1}")
dso.write(f"{dsoch2}:ATTN {args.attn2}")
for ch in [dsoch1, dsoch2]:
	dso.write(f"{ch}:BWL OFF")
	dso.write(f"{ch}:CPL D1M")
	dso.write(f"{ch}:OFST 0V")
	dso.write(f"{ch}:UNIT V")
	dso.write(f"{ch}:VDIV {vunit(args.amp / 7.5)}")

# DSO trigger setup: edge trigger at 0V for AWG output channel
dso.write(f"{dsoch1}:TRCP DC")
dso.write(f"{dsoch1}:TRLV 0V")
dso.write(f"TRSE EDGE,SR,{dsoch1},HT,OFF")
dso.write("TRMD AUTO")

wait()

match = re.search("^SARA (.*)Sa/s", dso.query("SARA?").strip())
if match:
	sr = float(match.group(1))
	errprint(f"DSO sample rate: {sr} Sa/s")
	
wait()

xpts = []
vpps1 = []
vpps2 = []
vdbs = []
phases = []

print("    Freq,     Vpp 1,     Vpp 2,       dBV,     Phase")
f = args.fs
while f <= args.fe:
	hs = hscale(f)
	dso.write(f"TDIV {hs}")
	awg.write(f"{awgch}:BSWV FRQ,{f}")
	if f < 100: time.sleep(1)
	wait()

	vautoscale(dsoch1)
	vautoscale(dsoch2)
	wait()

	vpp1 = measure_vpp(dsoch1)
	vpp2 = measure_vpp(dsoch2)
	vdb = dBV(vpp2 / vpp1)
	phase = measure_phase(dsoch1, dsoch2)

	print(f"{f:8.0f},{vpp1:10.5f},{vpp2:10.5f},{vdb:10.5f},{phase:10.5f}")
	xpts.append(f);
	vpps1.append(vpp1);
	vpps2.append(vpp2);
	vdbs.append(vdb);
	phases.append(phase);
	
	df = step(f)
	f += df

awg.write(f"{awgch}:OUTP OFF")
close_resources()

plt.figure()
plotvpp(xpts, vpps1, vpps2, phases)
plt.figure()
plotvdb(xpts, vdbs, phases)
plt.show()
