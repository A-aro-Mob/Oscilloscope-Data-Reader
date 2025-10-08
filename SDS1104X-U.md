# SDS1104X-U

The SDS1104X-U is an 8-bit oscilloscope similar to the SDS1104X-E but with a reduced feature set. With the release of the SDS800X HD series, neither of these should be considered for purchase, but if you own one already, there is no need to immediate replace it. Its main issue is the strict 8-bits math and acquisition modes, and that, unlike the SDS1104X-E and other Siglent products, it has never received even a single firmware update since its launch in 2021. It is a reliable oscilloscope in daily use, albeit with a buggy SCPI subsystem. In this document I will list some of the limitations and bugs I ran into.

- Firmware: 1.1.5R6 (2021-05-11).
- Connection: USB
- Software: Python & PyVisa

## General Limitations

- As an 8 bit oscilloscope, it is limited to 256 discrete voltage levels at a given scale. Its average and ERES acquisition modes are implemented in hardware. Although they do significantly reduce noise, the output is still always 8 bits on screen and when exported.

- Math operations are also limited to 8 bits output. Differential measurements are futile even with the average and ERES acquisition modes. Using the `+` operation in an attempt to simulate 9-bit output for a channel is therefore still limited to 8 bits. Vertically scaling the math channel only magnifies this limit.

## SCPI Bugs

- That the oscilloscope has support for SCPI is great, but it is buggy. If only Siglent had released a single firmware update with just these bugs fixed. The SCPI subsystem usually gets into a bad state when it is interrupted or a buggy command is used, e.g. `SCDP` or `<source>:PAVA? ALL`. In this state new queries always fail, or return data of a previous query, or always result in a timeout error.

	Workaround: Unplug and replug the USB cable, or turn the oscilloscope off and on again.

- Any query that returns more than approximately 40 bytes results in an internal buffer overflow.

- Using an incorrect command or query often results in an unresponsive SCPI subsystem.

- `SCDP`

	The screen dump command only returns the BMP header and incorrect data for 12½ pixels. The example of the manual does not work on the SDS1104X-U. It always returns the same 116 bytes. By reading the data in small chunks, up to a few KB may be returned before an inevitable timeout error, even with increased timeout setting. That data still does not resemble the contents of the screen though. It is mostly repeated `\x8631` words. Using this command often leaves the oscilloscope's SCPI subsystem in a bad state. Because the SDS1104X-U does not have a webserver, this command might have been a convenient way to obtain screenshots without having to resort to a USB stick, but alas, the command is totally broken.
	
	Workaround: none.

- `<source>:WF? DAT2`

	Only 20 waveform samples can be retrieved reliably. In coordination with the `WFSU` command 14,000 samples can be retrieved in 9 seconds over USB. Retrieving the full 14,000,000 samples buffer is therefore not feasible. By sampling multiple sweeps, samples can be averaged programatically.

- `<source>:MEAD? PHA`

	Querying for the phase difference between two channels results in a decode error because of two extra bytes: `\xa1\xe3`. The returned phase is not in the range [-180,180[ but [-90, 270[ instead. The same is the case in the user interface.
	
	Workaround: Instead of `.query()` use `.write()` and `.read_raw()[:-2].decode()`. Convert to [-180,180[.

- `<source>:PAVA? ALL`

	Returns a truncated response and SCPI gets into a bad state. Subsequent queries return different parts of this request.

	Workaround: Use `PAVA` commands for individual measurements.

- `'MENU?` / `MENU ON` / `MENU OFF`

	Returns and sets the opposite of the actual state of the menu.

	Workaround: to turn off the menu, use `MENU ON`.

- `MEGS?`

	SCPI subsystem hangs.
	
	Workaround: don't use this query.

- Cursor track mode is slow. Gate measurements is faster and should be used instead with SCPI.
