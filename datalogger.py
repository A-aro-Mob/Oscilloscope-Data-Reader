#!/usr/bin/python3

# Outputs timestamp, elapsed time, and voltage of active scope channels at trigger point with SDS1104X-U.
# Optionally change SDG1032X DC voltage before taking each sample.
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
import argparse
import pyvisa
import matplotlib.pyplot as plt
import csv
from eelib import *

def wait():
    """Small delay for DSO or AWG command processing."""
    time.sleep(0.5)
    awg.query("*OPC?")
    dso.query("*OPC?")

def plot(xpts, ypts, channels):
    """Plots V of given channels."""
    colors = [ 'gold', 'magenta', 'cyan', 'limegreen' ]
    fig, ax1 = plt.subplots()
    ax1.set_title("Data Logger")
    ax1.set_xlabel("Time [s]")
    ax1.set_ylabel("Voltage [V]")
    for idx, ch in enumerate(channels):
        ax1.plot(xpts, ypts[idx], color=colors[idx % len(colors)], label=ch)
    ax1.legend()
    plt.show()

def create_csv(filename="data_logger_output.csv", channels=None, xpts=None, ypts=None, start=None):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        header = ["Timestamp", "Elapsed Time [s]"] + channels
        writer.writerow(header)
        for i in range(len(xpts)):
            timestamp = start + datetime.timedelta(seconds=xpts[i])
            row = [timestamp.strftime("%Y-%m-%d %H:%M:%S"), f"{xpts[i]:.3f}"]
            for j in range(len(channels)):
                row.append(f"{ypts[j][i]:.5f}")
            writer.writerow(row)

# ------------------ Argument Parser ------------------
parser = argparse.ArgumentParser(
    description="Data Logger",
    epilog="Output timestamp, elapsed time, and voltage of active scope channels at trigger point with SDS1104X-U. Optionally change SDG1032X DC voltage before taking each sample."
)
parser.add_argument('-i', type=float, dest='interval', default=1, metavar='interval', help="Sample interval in seconds (default is 1)")
parser.add_argument('-n', type=int, dest='limit', default=0, metavar='limit', help="Maximum number of samples (default is unlimited)")
parser.add_argument('-p', action='store_true', dest='plot', help="Plot samples (only available with sample limit)")
parser.add_argument('-awg', type=int, choices=range(0, 3), dest='cawg', default=0, metavar='awgchannel', help="AWG output channel ([1,2], AWG off by default)")
parser.add_argument('-vmin', type=int, dest='vmin', default=0, metavar='vmin', help="AWG minimum DC voltage (default is 0)")
parser.add_argument('-vmax', type=int, dest='vmax', default=1, metavar='vmax', help="AWG maximum DC voltage (default is 1)")
parser.add_argument('-ch', nargs='+', dest='channels', metavar='channel', help="Specify scope channels to log (e.g., CH1 CH2)")

args = parser.parse_args()

# ------------------ Setup ------------------
sample_size = args.limit
awgch = f"C{args.cawg}"
dvawg = 0

scrollmode = dso.query("SAST?").strip() == "SAST Roll"

if args.cawg == 0:
    if not scrollmode:
        errprint("Warning: scope roll mode not enabled")
elif sample_size != 0:
    if scrollmode:
        errprint("Warning: scope roll mode enabled")
    # AWG setup: DC, offset, HiZ output ON
    awg.write(f"{awgch}:OUTP LOAD,HZ,PLRT,NOR")
    awg.write(f"{awgch}:BSWV WVTP,DC")
    awg.write(f"{awgch}:BSWV OFST,{args.vmin}")
    awg.write(f"{awgch}:OUTP ON")
    dvawg = (args.vmax - args.vmin) / (sample_size - 1)

channels = args.channels if args.channels else active_channels()
xpts = []
ypts = []
raw_data = {ch: [] for ch in channels}

print("                 Timestamp,      [s]", end='')
for ch in channels:
    print(f",{ch:>9}", end='')
    ypts.append([])
print()

# ------------------ Sampling Loop ------------------
n = 0
start = None
vawg = args.vmin
while n < sample_size or sample_size == 0:
    if dvawg != 0:
        awg.write(f"{awgch}:BSWV OFST,{vawg}")
        vawg = vawg + dvawg
        wait()

    now = datetime.datetime.now()
    if start is None:
        start = now
    elapsed = (now - start).total_seconds()
    xpts.append(elapsed)
    print(f"{now},{elapsed:9.3f}", end='')

    for idx, ch in enumerate(channels):
        v = measure_level(ch)
        ypts[idx].append(v)
        raw_data[ch].append(v)
        print(f",{v:9.5f}", end='')
    print()
    n += 1
    time.sleep(args.interval)

# ------------------ Output ------------------
create_csv(
    channels=channels,
    xpts=xpts,
    ypts=ypts,
    start=start
)

close_resources()

if args.plot:
    plot(xpts, ypts, channels)
    

# Example command on running the function
#
# python3 logger.py -i 2 -n 10 -p -awg 1 -vmin 0 -vmax 5 -ch CH1 CH2
#
#This will:
#    Sample every 2 seconds
#    Take 10 samples
#    Plot the results
#    se AWG channel 1 with voltage sweep from 0 to 5 V
#    Log data from CH1 and CH2