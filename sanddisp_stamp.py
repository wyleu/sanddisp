"""
sanddisp_stamp.py
=================
Decode the sandswing stamp SysEx for the Dot3K, with no hardware imports
(no dothat, no mido), so it can be tested anywhere.

Its own copy of the layout (sandswing src/midi_stamp.py and
docs/midi-stamp.md); sanddisp does not import sandswing.  One message,
13 bytes, every byte after F0 is 7-bit:

    F0 7D 53 vv sh sl cc t4 t3 t2 t1 t0 F7

    7D     STAMP_MFR_ID   MIDI non-commercial manufacturer ID
    53     STAMP_TAG      'S' (sandswing)
    vv     STAMP_VERSION  layout version, 1 = this table
    sh sl  seq, 14 bits, high 7 then low 7.  Stroke stamps count
           1 .. 16383, then 1 again; 0 = no stroke yet.
    cc     bell channel 1-8 (NOT the MIDI channel).  0 = clock message,
           sent while the tower is quiet (about every midi.clock_s, 10 s).
    t4..t0 Pico TickClock ms, 35 bits as 5 x 7 bits, most significant
           first.  A free-running count (starts near 2**29), so only the
           difference between two stamps is shown, never t itself.

mido gives a SysEx as msg.type "sysex" with msg.data = the bytes between
F0 and F7 (11 bytes here).

The Dot3K shows a decoded stamp on two rows (both at most LCD_W):
    port row     detail_text():  "#12 c2 +3172"  (stroke: seq, bell ch, ms
                                  since the previous decoded stamp)
                                 "#12 +10001"    (clock: seq, ms since)
    message row  kind_text():    "SX" (stroke) or "CLK" (clock)
fmt_msg() style, one line:       "SX  #12 c2" / "CLK #12"
"""

SYSEX_START = 0xF0
SYSEX_END = 0xF7
STAMP_MFR_ID = 0x7D
STAMP_TAG = 0x53
STAMP_VERSION = 1
STAMP_CH_CLOCK = 0                 # cc of a clock message
SEVEN_BITS = 7
STAMP_T_BYTES = 5
STAMP_T_MASK = (1 << (SEVEN_BITS * STAMP_T_BYTES)) - 1     # 35-bit ms wrap

# offsets in mido msg.data (the full message less F0 and F7)
D_MFR, D_TAG, D_VER, D_SEQ, D_CH = 0, 1, 2, 3, 5
D_T = D_CH + 1
STAMP_DATA_LEN = D_T + STAMP_T_BYTES                        # 11
STAMP_LEN = STAMP_DATA_LEN + 2                              # 13 with F0/F7

LCD_W = 16                         # Dot3K row width (as sanddisp_usb.LCD_W)
MS_PER_S = 1000

KIND_STROKE = "SX"
KIND_CLOCK = "CLK"


def decode_data(data):
    """(seq, ch, t_ms) from the 11 bytes between F0 and F7, or None
    (not a sandswing stamp, or not layout version 1)."""
    try:
        data = bytes(data)
    except (TypeError, ValueError):
        return None
    if (len(data) != STAMP_DATA_LEN or data[D_MFR] != STAMP_MFR_ID
            or data[D_TAG] != STAMP_TAG or data[D_VER] != STAMP_VERSION):
        return None
    if any(b > 0x7F for b in data):            # SysEx data bytes are 7-bit
        return None
    t = 0
    for i in range(D_T, D_T + STAMP_T_BYTES):
        t = (t << SEVEN_BITS) | data[i]
    return (data[D_SEQ] << SEVEN_BITS) | data[D_SEQ + 1], data[D_CH], t


def decode(raw):
    """Same, from the full 13-byte message including F0 and F7 (as
    sandswing midi_stamp.decode)."""
    raw = bytes(raw)
    if len(raw) != STAMP_LEN or raw[0] != SYSEX_START or raw[-1] != SYSEX_END:
        return None
    return decode_data(raw[1:-1])


def decode_mido(msg):
    """(seq, ch, t_ms) of a mido message, or None (not a stamp SysEx)."""
    if getattr(msg, "type", None) != "sysex":
        return None
    return decode_data(getattr(msg, "data", ()))


def is_clock(stamp):
    return stamp[1] == STAMP_CH_CLOCK


def delta_ms(stamp, prev_t):
    """ms from the previous decoded stamp's t (35-bit wrap), or None."""
    if prev_t is None:
        return None
    return (stamp[2] - prev_t) & STAMP_T_MASK


def kind_text(stamp):
    return KIND_CLOCK if is_clock(stamp) else KIND_STROKE


def detail_text(stamp, prev_t=None, width=LCD_W):
    """Port-row text: "#seq cCH +ms" (stroke) or "#seq +ms" (clock).
    The delta is added only if it fits in width: as ms, else as whole
    seconds ("+125s"); else left off.  First stamp: no delta."""
    seq, ch = stamp[0], stamp[1]
    base = "#%d" % seq if is_clock(stamp) else "#%d c%d" % (seq, ch)
    d = delta_ms(stamp, prev_t)
    if d is None:
        return base[:width]
    for tail in ("+%d" % d, "+%ds" % (d // MS_PER_S)):
        s = "%s %s" % (base, tail)
        if len(s) <= width:
            return s
    return base[:width]


def line_text(stamp, width=LCD_W):
    """One-line form for fmt_msg: "SX  #12 c2" or "CLK #12"."""
    if is_clock(stamp):
        return ("%-4s#%d" % (KIND_CLOCK, stamp[0]))[:width]
    return ("%-4s#%d c%d" % (KIND_STROKE, stamp[0], stamp[1]))[:width]

def headline_text(stamp, width=LCD_W):
    """Top row: "SX #12" or "CLK #12"."""
    return ("%s #%d" % (kind_text(stamp), stamp[0]))[:width]


def extra_text(stamp, prev_t=None, width=LCD_W):
    """Middle row: "c2 +3172" (stroke) or "+10001" (clock). First stamp has no delta."""
    base = "" if is_clock(stamp) else ("c%d" % stamp[1])
    d = delta_ms(stamp, prev_t)
    if d is None:
        return base[:width]
    for tail in ("+%d" % d, "+%ds" % (d // MS_PER_S)):
        s = ("%s %s" % (base, tail)).strip()
        if len(s) <= width:
            return s
    return base[:width]
