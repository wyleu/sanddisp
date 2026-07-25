#!/usr/bin/env python3
"""
sanddisp_log.py — Dot3K MIDI confirm + timestamped event log

Row 0: date/time (updates ~4 Hz)
Row 1: USB port / device name
Row 2: last MIDI summary

RGB: sticky by message type (note on/off, CC, PC)
Bargraph: brief flash on activity
Log: append ISO-8601 timestamped lines under logs/
"""

import os
import time
import signal
from datetime import datetime
from pathlib import Path

import mido
from dot3k import backlight, lcd

# --- config ---
BASE_LED = 180
FLASH_SEC = 0.12
POLL_SEC = 0.01
CLOCK_SEC = 0.25
LCD_W = 16
LOG_DIR = Path.home() / "Code" / "Sanddisp" / "logs"

SKIP_SUBSTR = (
    "Midi Through", "QmidiNet", "RtMidi", "PipeWire", "Timer", "Announce",
)

# Optional: early Dot3K colour swap
try:
    backlight.use_rbg()
except Exception:
    pass


def trunc(s, width=LCD_W):
    s = str(s)
    return s if len(s) <= width else s[: width - 1] + "~"


def stamp_iso():
    """Wall-clock stamp as soon as we handle a message."""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def clock_line():
    """Compact for 16 cols: DD-MM HH:MM:SS"""
    return datetime.now().strftime("%d-%m %H:%M:%S")


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


def set_backlight(r, g, b):
    backlight.rgb(r, g, b)
    backlight.update()


def flash_bar(on: bool):
    backlight.set_graph(1.0 if on else 0.0)
    backlight.update()


def show_clock():
    lcd.set_cursor_position(0, 0)
    lcd.write(trunc(clock_line()).ljust(LCD_W))


def show_device(name: str):
    lcd.set_cursor_position(0, 1)
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


def log_path_today():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y%m%d")
    return LOG_DIR / f"midi-{day}.log"


def log_event(port_name: str, msg):
    ts = stamp_iso()
    # one compact field instead of type + full str(msg)
    line = f"{ts}\t{port_name}\t{fmt_msg(msg)}\n"
    path = log_path_today()
    with open(path, "a") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    return ts

def shutdown_display(message="Shutting down..."):
    try:
        backlight.set_graph(0.0)
        backlight.rgb(40, 0, 0)
        backlight.update()
        lcd.clear()
        lcd.set_cursor_position(0, 1)
        lcd.write((message[:16]).ljust(16))
        time.sleep(0.8)
        lcd.clear()
        backlight.rgb(0, 0, 0)
        backlight.update()
    except Exception:
        pass

def main():
    lcd.clear()
    set_backlight(0, 0, 80)
    show_clock()
    show_device("No USB MIDI...")
    show_msg("")

    ports = open_usb_inputs()

    if not ports:
        show_device("No USB MIDI")
        show_msg("plug & restart")
        stop = {"flag": False}
        def request_stop(signum, frame):
            stop["flag"] = True
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        try:
            while not stop["flag"]:
                show_clock()
                time.sleep(1)
        finally:
            shutdown_display("Shutting down...")
        return

    show_device(ports[0].name)
    flash_until = 0.0
    last_clock = 0.0

    stop = {"flag": False}

    def request_stop(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


    # Log header once per run
    path = log_path_today()
    with open(path, "a") as f:
        f.write(f"# sanddisp_log start {stamp_iso()} ports={[p.name for p in ports]}\n")
        f.flush()

    try:
        while not stop["flag"]:
            now = time.time()

            for inport in ports:
                for msg in inport.iter_pending():
                    # 1) stamp + log immediately
                    log_event(inport.name, msg)

                    # 2) UI
                    show_device(inport.name)
                    show_msg(fmt_msg(msg))

                    if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                        set_backlight(200, 0, 0)
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                    elif msg.type == "note_off" or (
                        msg.type == "note_on" and getattr(msg, "velocity", 0) == 0
                    ):
                        set_backlight(0, 180, 0)
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                    elif msg.type == "control_change":
                        set_backlight(0, 80, 200)
                        flash_bar(True)
                        flash_until = now + FLASH_SEC
                    elif msg.type == "program_change":
                        set_backlight(200, 0, 200)
                        flash_bar(True)
                        flash_until = now + FLASH_SEC

            if flash_until and now >= flash_until:
                flash_bar(False)
                flash_until = 0.0

            if now - last_clock >= CLOCK_SEC:
                show_clock()
                last_clock = now

            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        pass

    finally:
        print("Closing...")
        shutdown_display("Shutting down...")
        for p in ports:
            try:
                p.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
