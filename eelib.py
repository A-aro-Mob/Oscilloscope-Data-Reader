#!/usr/bin/python3

import time
import sys
import math
import array
import re
import struct
import enum
import pyvisa
import configparser

def errprint(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)
	
def norm_angle(x: float) -> float:
	"""Normalizes angle to value between [-180,180[."""
	x = x % 360
	if x >= 180:
		x -= 360
	elif x < -180:
		x += 360
	return x

def vunit(v):
	"""Returns voltage with proper unit."""
	units = ("V", "mV", "uV")
	factors = (1, 1e-3, 1e-6)
	for i in range(0, len(units)):
		if abs(v) >= factors[i]: return f"{v / factors[i]}{units[i]}"
	return "1uV"

def active_channels():
	"""Returns active DSO channels."""
	channels = []
	for ch in ['C1', 'C2', 'C3', 'C4']:
		s = dso.query(f"{ch}:TRA?").strip()
		match = re.search("^(C\d):TRA ON$", s)
		if match: channels.append(match.group(1))
	return channels

def measure_vscale(ch):
	"""Returns vertical scale per division."""
	s = dso.query(f"{ch}:VDIV?").strip()
	match = re.search(f"^{ch}:VDIV ([-+0-9.E]+)V$", s)
	if match:
		v = float(match.group(1))
	else:
		errprint(f"Error parsing: {s}")
		sys.exit(7)
	return v

def measure_voffset(ch):
	"""Returns vertical offset."""
	s = dso.query(f"{ch}:OFST?").strip()
	match = re.search(f"^{ch}:OFST ([-+0-9.E]+)V$", s)
	if match:
		v = float(match.group(1))
	else:
		errprint(f"Error parsing: {s}")
		sys.exit(8)
	return v

def vautoscale(ch, iterations = 2, vdiv = 7.5):
	"""Automatic vertical offset and scale adjustment."""
	# Measures Vmin and Vmax, then adjusts vertical offset and scale
	for i in range(0, iterations):
		if i > 0: time.sleep(0.1)
		s = dso.query(f"{ch}:PAVA? MIN").strip()
		match1 = re.search(f"^{ch}:PAVA MIN,(.*)V$", s)
		s = dso.query(f"{ch}:PAVA? MAX").strip()
		match2 = re.search(f"^{ch}:PAVA MAX,(.*)V$", s)
		if match1 and match2 and not match1.group(1).startswith("*") and not match2.group(1).startswith("*"):
			vmin = float(match1.group(1))
			vmax = float(match2.group(1))
			vpp = vmax - vmin
			v0 = vmin + vpp / 2
			dso.write(f"{ch}:OFST {-v0:.5f}V")
			dso.write(f"{ch}:VDIV {vpp / vdiv:.5f}V")
		else:
			errprint(f"Error parsing for vautoscale: {s}")
			sys.exit(1)

def hscale(f):
	"""Computes optimal horizontal scale for given frequency."""
	t = 1 / (f * 4)
	units = ("ns", "us", "ms", "s")
	factors = (1e-9, 1e-6, 1e-3, 1)
	for i in range(0, len(units)):
		for j in (1, 2, 5, 10, 20, 50, 100, 200, 500):
			if j * factors[i] > t: return f"{j}{units[i]}"
	return "1s"

def dBV(v):
	return 20 * math.log10(v)

def measure_hscale():
	"""Returns horizontal scale per division."""
	s = dso.query(f"TDIV?").strip()
	match = re.search("^TDIV ([-+0-9.E]+)S$", s)
	if match:
		t = float(match.group(1))
	else:
		errprint(f"Error parsing: {s}")
		sys.exit(2)
	return t

def measure_vpp(ch):
	"""Returns Vpp of given DSO channel."""
	# Assumes optimal vertical scale
	s = dso.query(f"{ch}:PAVA? PKPK").strip()
	match = re.search(f"^{ch}:PAVA PKPK,(.*)V$", s)
	if match and not match.group(1).startswith("*"):
		vpp = float(match.group(1))
	else:
		errprint(f"Error parsing Vpp: {s}")
		sys.exit(2)
	return vpp

def measure_mean(ch):
	"""Returns mean of given DSO channel."""
	# Assumes optimal vertical scale
	s = dso.query(f"{ch}:PAVA? MEAN").strip()
	match = re.search(f"^{ch}:PAVA MEAN,(.*)V$", s)
	if match and not match.group(1).startswith("*"):
		v = float(match.group(1))
	else:
		errprint(f"Error parsing V: {s}")
		sys.exit(2)
	return v

def measure_level(ch):
	"""Returns V of given DSO channel at the trigger point."""
	# Assumes optimal vertical scale
	s = dso.query(f"{ch}:PAVA? LEVELX").strip()
	match = re.search(f"^{ch}:PAVA LEVELX,(.*)V$", s)
	if match:
		sample = float(match.group(1))
	else:
		errprint(f"Error parsing: {s}")
		sys.exit(2)
	return sample

def measure_phase(ch1, ch2):
	"""Returns phase difference between two DSO channels."""
	# Assumes optimal horizontal and vertical scales
	dso.write(f"{ch2}-{ch1}:MEAD? PHA") # Query returns extra \xa1\xe3 data, so using read_raw
	s = dso.read_raw()[:-2].decode()
	match = re.search(f"^{ch2}-{ch1}:MEAD PHA,(.*)$", s)
	if match:
		if match.group(1).startswith("*"):
			phase = 0
		else:
			phase = norm_angle(float(match.group(1)))
	else:
		errprint(f"Error parsing phase: {s}")
		sys.exit(4)
	return phase

def nsamples(ch):
	"""Returns number of samples."""
	s = dso.query(f"SANU? {ch}").strip()
	match = re.search("^SANU (.*)pts$", s)
	if match:
		n = float(match.group(1))
	else:
		errprint(f"Error parsing: {s}")
		sys.exit(5)
	return math.floor(n)
	
def fetch(ch):
	"""Returns waveform data of a channel."""
	vscale = measure_vscale(ch)
	voffset = measure_voffset(ch)
	data = array.array('f')
	stride = 1
	batchsize = 20 # Apparent limit on SDS1104X-U
	n = nsamples(ch)
	for i in range(0, n, batchsize):
		dso.write(f"WFSU SP,{stride},NP,{batchsize},FP,{i}")
		dso.write(f"{ch}:WF? DAT2")
		rawdata = dso.read_raw()
		remaining = min(batchsize, n - i + 1)
		header = f"{ch}:WF DAT2,#90{remaining:08d}"
		if (rawdata[0:len(header)].decode() == header):
			for b in list(rawdata[len(header): -2]):
				if b > 127: b = b - 256
				v = b * (vscale / 25) - voffset
				data.append(v)
		else:
			errprint(f"Error parsing: {rawdata}")
			sys.exit(6)
	return data

def close_resources():
	for instr in resources:
		resources[instr].close()

rm = pyvisa.ResourceManager()
resources = {}

config = configparser.ConfigParser()
config.read("config.ini")
defaults = config['DEFAULT']

try:
	if 'dso_instr' in defaults:
		resources['dso'] = rm.open_resource(defaults['dso_instr'])
	if 'awg_instr' in defaults:
		resources['awg'] = rm.open_resource(defaults['awg_instr'])
	if 'psu_instr' in defaults:
		resources['psu'] = rm.open_resource(defaults['psu_instr'])

	for instr in rm.list_resources():
		match = re.search("::SDS.*::INSTR$", instr)
		if match:
			resources['dso'] = rm.open_resource(instr)
		match = re.search("::SDG.*::INSTR$", instr)
		if match:
			resources['awg'] = rm.open_resource(instr)
		match = re.search("::SPD.*::INSTR$", instr)
		if match:
			resources['psu'] = rm.open_resource(instr)
except OSError as e:
	sys.exit(f"Unable to connect to instrument: {e}")

dso = resources['dso'] if 'dso' in resources else None
awg = resources['awg'] if 'awg' in resources else None
psu = resources['psu'] if 'psu' in resources else None

# Module Tests
if __name__ == "__main__":
	assert norm_angle(240) == -120
	assert vunit(2.5e-3) == "2.5mV"
	