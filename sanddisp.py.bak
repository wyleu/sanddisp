#!/usr/bin/python

import time
import datetime
from dot3k import backlight, lcd

# MIDI library
import mido
import numpy as np

base_led_level = 150
backlight_step = 10
backlight_val = 100
second_tick = True
prev_second_tick = not second_tick

backlight.rgb(200,0,200)

time.sleep(1)

backlight.rgb(0,200,200)

time.sleep(1)

backlight.rgb(200,200,0)

time.sleep(1)

lcd.clear()
dt = datetime.datetime.now()
lcd.write(str(dt.strftime('%m-%d %H-%M:%S')))

with mido.open_input('QmidiNet:port 0 128:0') as inport:
	print('Port Opend')
	loop_tick = True

	try:
		while True:
			for msg in inport:
				print('A message ', msg)
				if dt.microsecond > 499999:
					second_tick = True
					backlight.set(9, base_led_level)
				else:
					backlight.set(9,0)
					second_tick = False
				if msg.type == 'note_on':
					backlight.set(10, base_led_level)

				if msg.type == 'note_off':
					backlight.set(10,0)

				dt = datetime.datetime.now()

				if second_tick != prev_second_tick:
					if backlight_val > 200 or backlight_val < 100 :
						backlight_step = 0 - backlight_step

					backlight_val = backlight_val + backlight_step
					backlight.rgb(backlight_val, backlight_val, 0)
					prev_second_tick = second_tick


				lcd.clear()
				dt = datetime.datetime.now()
				lcd.write(str(dt.strftime('%m-%d %H-%M:%S')))
				if loop_tick:
					backlight.set(11, base_led_level)
				else:
					backlight.set(11,0)

				loop_tick = not loop_tick
	except KeyboardInterrupt:
		pass
print('Closing Down...')
lcd.clear()

