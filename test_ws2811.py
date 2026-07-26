#!/usr/bin/env python3
from rpi_ws281x import PixelStrip, Color
import time

LED_COUNT = 9
LED_PIN = 18          # BCM numbering
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 64   # 0–255; keep modest while testing
LED_INVERT = False
LED_CHANNEL = 0

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                   LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

def set_all(r, g, b):
    c = Color(r, g, b)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, c)
    strip.show()

set_all(0, 0, 0)
time.sleep(0.2)
set_all(32, 0, 0)     # dim red
time.sleep(1)
set_all(0, 32, 0)     # dim green
time.sleep(1)
set_all(0, 0, 0)


