#!/usr/bin/env python3
"""
sanddisp_log.py — Dot3K MIDI confirm + timestamped event log

Programme: sanddisp_log
Host role: sanddisp (USB MIDI → LCD + log file)

Layout (Dot3K 16x3)
  Row 0: date/time (UK DD-MM HH:MM:SS), ~4 Hz
  Row 1: USB port / device name
  Row 2: last MIDI summary
  RGB:   sticky by type (note on/off, CC, PC)
  Bar:   brief flash on activity
  Log:   logs/midi-YYYYMMDD.log (ISO-8601 stamps)

Hotplug
  About every HOTPLUG_SEC seconds we re-read mido.get_input_names(),
  open any new USB-ish ports, and close ports that have disappeared
  (cable unplugged, device powered off). Each change is written to the
  log as a system line:
    ...  -  MIDI port connected: <name>
    ...  -  MIDI port disconnected: <name>
  The LCD device row updates to the newest port, or "No USB MIDI" /
  "waiting..." when none remain. MIDI traffic is still drained with
  iter_pending() so bursts do not stall the UI.

Structure
  config / constants
  helpers:     trunc, stamp_iso, clock_line, is_usbish, usbish_names
  hardware:    set_backlight, flash_bar, show_*, shutdown_display
  midi:        open_usb_inputs, fmt_msg, apply_msg_ui, sync_ports
  log:         _get_log_file, log_event, log_system, close_log, log_header
  control:     install_stop_handlers, poll_ports, tick_flash, tick_clock
               run_idle_no_ports, run_main_loop
  main()
"""

import os
import time
import signal
from datetime import datetime
from pathlib import Path

import mido
from dot3k import backlight, lcd

# --- config / constants ---
BASE_LED = 180
FLASH_SEC = 0.12
POLL_SEC = 0.01
CLOCK_SEC = 0.25
HOTPLUG_SEC = 1.0
LCD_W = 16
LOG_DIR = Path.home() / "Code" / "Sanddisp" / "logs"

SKIP_SUBSTR = (
    "Midi Through",
    "QmidiNet",
    "RtMidi",
    "PipeWire",
    "Timer",
    "Announce",
)

_log_file = None
_log_day = None

try:
    backlight.use_rbg()
except Exception:
    pass


# --- helpers ---
def trunc(s, width=LCD_W):
    s = str(s)
    return s if len(s) <= width else s[: width - 1] + "~"


def stamp_iso():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def clock_line():
    """UK day-month on the LCD."""
    return datetime.now().strftime("%d-%m %H:%M:%S")


def is_usbish(name: str) -> bool:
    return not any(s.lower() in name.lower() for s in SKIP_SUBSTR)


def usbish_names():
    return [n for n in mido.get_input_names() if is_usbish(n)]


# --- hardware ---
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


def shutdown_display(message="Shutting down..."):
    try:
        flash_bar(False)
    except Exception:
        pass
    try:
        set_backlight(40, 0, 0)
        lcd.clear()
        lcd.set_cursor_position(0, 1)
        lcd.write(trunc(message).ljust(LCD_W))
        time.sleep(0.8)
        lcd.clear()
        set_backlight(0, 0, 0)
    except Exception:
        pass


# --- log (no per-line fsync — keeps MIDI loop responsive) ---
def _get_log_file():
    global _log_file, _log_day
    day = datetime.now().strftime("%Y%m%d")
    if _log_file is None or _log_day != day:
        if _log_file is not None:
            try:
                _log_file.close()
            except Exception:
                pass
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = LOG_DIR / f"midi-{day}.log"
        _log_file = open(path, "a", buffering=1)
        _log_day = day
    return _log_file


def log_event(port_name: str, msg):
    ts = stamp_iso()
    _get_log_file().write(f"{ts}\t{port_name}\t{fmt_msg(msg)}\n")
    return ts


def log_system(text: str):
    ts = stamp_iso()
    line = f"{ts}\t-\t{text}\n"
    try:
        _get_log_file().write(line)
    except Exception:
        pass
    print(text)


def log_header(ports):
    names = [p.name for p in ports] if ports else []
    log_system(f"sanddisp_log start ports={names}")


def close_log():
    global _log_file, _log_day
    if _log_file is not None:
        try:
            _log_file.flush()
            _log_file.close()
        except Exception:
            pass
        _log_file = None
        _log_day = None


# --- midi ---
def open_usb_inputs():
    ports = []
    for name in usbish_names():
        try:
            ports.append(mido.open_input(name))
            log_system(f"MIDI port connected: {name}")
        except Exception as e:
            log_system(f"MIDI port open failed: {name} ({e})")
    return ports


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


_last_stamp_t = None


def apply_msg_ui(port_name, msg, now, flash_until):
    """Bottom row: ordinary MIDI. Middle row: stamp SysEx only (not the port name)."""
    global _last_stamp_t
    from sanddisp_stamp import banner_text, decode_mido, is_clock
    stamp = decode_mido(msg)
    if stamp is not None:
        show_device(trunc(banner_text(stamp, _last_stamp_t)))
        if is_clock(stamp):
            set_backlight(0, 160, 160)
        else:
            set_backlight(200, 120, 0)
        flash_bar(True)
        _last_stamp_t = stamp[2]
        return now + FLASH_SEC
    show_msg(fmt_msg(msg))
    if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
        set_backlight(200, 0, 0)
        flash_bar(True)
        return now + FLASH_SEC
    if msg.type == "note_off" or (
        msg.type == "note_on" and getattr(msg, "velocity", 0) == 0
    ):
        set_backlight(0, 180, 0)
        flash_bar(True)
        return now + FLASH_SEC
    if msg.type == "control_change":
        set_backlight(0, 80, 200)
        flash_bar(True)
        return now + FLASH_SEC
    if msg.type == "program_change":
        set_backlight(200, 0, 200)
        flash_bar(True)
        return now + FLASH_SEC
    return flash_until


def sync_ports(ports):
    """
    Hotplug reconciliation.
    - Names in ALSA/Mido but not open  → open + log "connected"
    - Open ports missing from ALSA       → close + log "disconnected"
    """
    wanted = set(usbish_names())
    changed = False

    still = []
    for p in ports:
        if p.name in wanted:
            still.append(p)
        else:
            name = p.name
            try:
                p.close()
            except Exception:
                pass
            log_system(f"MIDI port disconnected: {name}")
            changed = True
    ports[:] = still

    have = {p.name for p in ports}
    for name in wanted:
        if name not in have:
            try:
                ports.append(mido.open_input(name))
                log_system(f"MIDI port connected: {name}")
                changed = True
            except Exception as e:
                log_system(f"MIDI port open failed: {name} ({e})")
    return changed


# --- control ---
def install_stop_handlers(stop):
    def request_stop(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


def poll_ports(ports, now, flash_until):
    """Log every pending message; update UI only for the last per port."""
    for inport in ports:
        last = None
        for msg in inport.iter_pending():
            log_event(inport.name, msg)
            last = msg
        if last is not None:
            flash_until = apply_msg_ui(inport.name, last, now, flash_until)
    return flash_until


def tick_flash(now, flash_until):
    if flash_until and now >= flash_until:
        flash_bar(False)
        return 0.0
    return flash_until


def tick_clock(now, last_clock):
    if now - last_clock >= CLOCK_SEC:
        show_clock()
        return now
    return last_clock


def run_idle_no_ports(ports):
    """
    No device at start: still run the loop so hotplug can attach later.
    ports is a shared list (mutated by sync_ports).
    """
    show_device("")
    show_msg("waiting...")
    stop = {"flag": False}
    install_stop_handlers(stop)
    last_clock = 0.0
    last_hotplug = 0.0
    log_header(ports)
    try:
        while not stop["flag"]:
            now = time.time()
            if now - last_hotplug >= HOTPLUG_SEC:
                if sync_ports(ports) and ports:
                    show_device("")
                    show_msg("")
                    # fall through to full loop in main via return
                    return "ports"
                last_hotplug = now
            last_clock = tick_clock(now, last_clock)
            time.sleep(POLL_SEC)
    finally:
        if not ports:
            shutdown_display("Shutting down...")
            close_log()
    return "stop"


def run_main_loop(ports):
    if ports:
        show_device("")
    else:
        show_device("")
        show_msg("waiting...")

    flash_until = 0.0
    last_clock = 0.0
    last_hotplug = 0.0
    stop = {"flag": False}
    install_stop_handlers(stop)
    log_header(ports)

    try:
        while not stop["flag"]:
            now = time.time()

            if now - last_hotplug >= HOTPLUG_SEC:
                if sync_ports(ports):
                    if ports:
                        show_device("")
                    else:
                        show_device("")
                        show_msg("waiting...")
                last_hotplug = now

            flash_until = poll_ports(ports, now, flash_until)
            flash_until = tick_flash(now, flash_until)
            last_clock = tick_clock(now, last_clock)
            time.sleep(POLL_SEC)
    finally:
        print("Closing...")
        shutdown_display("Shutting down...")
        close_log()
        for p in list(ports):
            try:
                p.close()
            except Exception:
                pass
        ports.clear()


def main():
    lcd.clear()
    set_backlight(0, 0, 80)
    show_clock()
    show_device("")
    show_msg("")

    ports = open_usb_inputs()
    # Single loop path: always main loop (handles empty + hotplug)
    run_main_loop(ports)


if __name__ == "__main__":
    main()
