#!/usr/bin/env python3
"""
sanddisp_usb.py — Dot3K USB-MIDI confirmation display
Line 0: USB port name
Line 2: last MIDI message
RGB: stays red after note_on, green after note_off
Bargraph: brief flash on note on/off
"""

import time
import mido
from dot3k import backlight, lcd

BASE_LED = 180
FLASH_SEC = 0.12
POLL_SEC = 0.01
LCD_W = 16

SKIP_SUBSTR = (
    "Midi Through",
    "QmidiNet",
    "RtMidi",
    "PipeWire",
    "Timer",
    "Announce",
)

backlight.use_rbg()


def trunc(s, width=LCD_W):
    s = str(s)
    return s if len(s) <= width else s[: width - 1] + "~"


def is_usbish(name: str) -> bool:
    return not any(s.lower() in name.lower() for s in SKIP_SUBSTR)


def open_usb_inputs():
    ports = []
    for name in mido.get_input_names():
        if is_usbish(name):
            try:
                ports.append(mido.open_input(name))
                print("Opened:", name)
            except Exception as e:
                print("Skip", name, e)
    return ports

def flash_bar(on: bool):
    # 0.0 = off, 1.0 = full bargraph
    backlight.set_graph(1.0 if on else 0.0)
    backlight.update()

def set_backlight(r, g, b):
    backlight.rgb(r, g, b)
    backlight.update()


def show_port(name: str):
    lcd.set_cursor_position(0, 0)
    lcd.write(trunc(name).ljust(LCD_W))


def show_msg(text: str):
    lcd.set_cursor_position(0, 2)
    lcd.write(trunc(text).ljust(LCD_W))

def fmt_msg(msg) -> str:
    ch = getattr(msg, "channel", None)
    ch_s = f"c{ch + 1}" if ch is not None else ""

    if msg.type == "note_on" and msg.velocity > 0:
        return trunc(f"ON  {ch_s} n{msg.note} v{msg.velocity}")
    if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
        vel = getattr(msg, "velocity", 0)
        return trunc(f"OFF {ch_s} n{msg.note} v{vel}")
    if msg.type == "control_change":
        return trunc(f"CC  {ch_s} cc{msg.control}={msg.value}")
    if msg.type == "program_change":
        return trunc(f"PC  {ch_s} p{msg.program}")
    return trunc(str(msg))

def main():
    lcd.clear()
    backlight.rgb(0, 0, 60)
    show_port("No USB MIDI...")
    show_msg("")
    set_backlight(0, 0, 80)

    ports = open_usb_inputs()
    if not ports:
        show_port("No USB MIDI")
        show_msg("plug & restart")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        return

    show_port(ports[0].name)
    flash_until = 0.0

    try:
        while True:
            now = time.time()
            for inport in ports:
                for msg in inport.iter_pending():
                    show_port(inport.name)

                    if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                        set_backlight(200, 0, 0)       # red
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                        show_msg(fmt_msg(msg))
                    elif msg.type == "note_off" or (
                        msg.type == "note_on" and getattr(msg, "velocity", 0) == 0
                    ):
                        set_backlight(0, 180, 0)       # green
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                        show_msg(fmt_msg(msg))
                    elif msg.type == "control_change":
                        set_backlight(0, 80, 200)      # blue
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                        show_msg(fmt_msg(msg))
                    elif msg.type == "program_change":
                        set_backlight(200, 0, 200)     # magenta
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                        show_msg(fmt_msg(msg))
                    else:
                        show_msg(fmt_msg(msg))

            if flash_until and now >= flash_until:
                flash_bar(False)
                flash_until = 0.0

            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing...")
        flash_bar(False)
        backlight.rgb(0, 0, 0)
        lcd.clear()
        for p in ports:
            p.close()


if __name__ == "__main__":
    main()
