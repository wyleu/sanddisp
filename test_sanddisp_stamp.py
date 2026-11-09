#!/usr/bin/env python3
"""Tests for sanddisp_stamp (no Dot3K, no mido needed).
Run: python3 test_sanddisp_stamp.py"""
import sys
import unittest

import sanddisp_stamp as st

# docs/midi-stamp.md example: bell ch 3, seq 1, t = 536810912
EXAMPLE = bytes([0xF0, 0x7D, 0x53, 0x01, 0x00, 0x01, 0x03,
                 0x01, 0x7F, 0x7C, 0x2B, 0x20, 0xF7])


def build(seq, ch, t, ver=st.STAMP_VERSION, mfr=st.STAMP_MFR_ID, tag=st.STAMP_TAG):
    """Full 13-byte message, the same way sandswing midi_stamp.fill does."""
    t_bytes = [(t >> (7 * i)) & 0x7F for i in range(4, -1, -1)]
    return bytes([0xF0, mfr, tag, ver, (seq >> 7) & 0x7F, seq & 0x7F, ch]
                 + t_bytes + [0xF7])


class FakeMido:
    """Just what decode_mido reads: type and data (bytes between F0/F7)."""
    def __init__(self, raw, type_="sysex"):
        self.type = type_
        self.data = tuple(raw[1:-1])


class TestDecode(unittest.TestCase):
    def test_example(self):
        self.assertEqual(st.decode(EXAMPLE), (1, 3, 536810912))
        self.assertEqual(st.decode_data(EXAMPLE[1:-1]), (1, 3, 536810912))
        self.assertEqual(st.decode_mido(FakeMido(EXAMPLE)), (1, 3, 536810912))

    def test_build_matches_example(self):
        self.assertEqual(build(1, 3, 536810912), EXAMPLE)

    def test_clock(self):
        s = st.decode(build(12, 0, 536900000))
        self.assertEqual(s, (12, 0, 536900000))
        self.assertTrue(st.is_clock(s))
        self.assertEqual(st.kind_text(s), "CLK")

    def test_seq_and_t_extremes(self):
        self.assertEqual(st.decode(build(16383, 8, st.STAMP_T_MASK)),
                         (16383, 8, st.STAMP_T_MASK))

    def test_rejects(self):
        self.assertIsNone(st.decode(EXAMPLE[:-1]))                  # short
        self.assertIsNone(st.decode(EXAMPLE + b"\x00"))             # long
        self.assertIsNone(st.decode_data(EXAMPLE[1:-2]))            # short data
        self.assertIsNone(st.decode(build(1, 3, 5, mfr=0x7E)))      # mfr
        self.assertIsNone(st.decode(build(1, 3, 5, tag=0x54)))      # tag
        self.assertIsNone(st.decode(build(1, 3, 5, ver=2)))         # version
        bad_end = EXAMPLE[:-1] + b"\x00"
        self.assertIsNone(st.decode(bad_end))
        self.assertIsNone(st.decode_mido(FakeMido(build(1, 3, 5, ver=0))))
        self.assertIsNone(st.decode_mido(FakeMido(EXAMPLE, "note_on")))

        class NoData:
            type = "sysex"
        self.assertIsNone(st.decode_mido(NoData()))


class TestText(unittest.TestCase):
    def test_stroke(self):
        s = (12, 2, 536810912)
        self.assertEqual(st.kind_text(s), "SX")
        self.assertEqual(st.detail_text(s), "#12 c2")
        self.assertEqual(st.detail_text(s, 536810912 - 3172), "#12 c2 +3172")
        self.assertEqual(st.line_text(s), "SX  #12 c2")

    def test_clock_text(self):
        s = (12, 0, 536820913)
        self.assertEqual(st.detail_text(s, 536810912), "#12 +10001")
        self.assertEqual(st.line_text(s), "CLK #12")

    def test_delta_wraps(self):
        s = (2, 1, 5)
        self.assertEqual(st.detail_text(s, st.STAMP_T_MASK), "#2 c1 +6")

    def test_long_delta_seconds_then_dropped(self):
        s = (16383, 8, 10 ** 9)
        self.assertEqual(st.detail_text(s, 10 ** 9 - 99999), "#16383 c8 +99999")
        self.assertEqual(st.detail_text(s, 10 ** 9 - 125000), "#16383 c8 +125s")
        self.assertEqual(st.detail_text(s, 0), "#16383 c8")

    def test_all_fit_lcd(self):
        prevs = [None, 0, 1, 10 ** 9, st.STAMP_T_MASK]
        for seq in (0, 1, 999, 16383):
            for ch in range(0, 9):
                for t in (0, 536810912, st.STAMP_T_MASK):
                    s = (seq, ch, t)
                    self.assertLessEqual(len(st.line_text(s)), st.LCD_W)
                    self.assertLessEqual(len(st.kind_text(s)), st.LCD_W)
                    for p in prevs:
                        self.assertLessEqual(len(st.detail_text(s, p)), st.LCD_W)

    def test_headline_and_extra(self):
        s = (12, 2, 536810912)
        self.assertEqual(st.headline_text(s), "SX #12")
        self.assertEqual(st.extra_text(s), "c2")
        self.assertEqual(st.extra_text(s, 536810912 - 3172), "c2 +3172")
        c = (12, 0, 536820913)
        self.assertEqual(st.headline_text(c), "CLK #12")
        self.assertEqual(st.extra_text(c, 536810912), "+10001")

    def test_banner_text(self):
        s = (12, 2, 536810912)
        self.assertEqual(st.banner_text(s), "SX #12 c2")
        self.assertEqual(st.banner_text(s, 536810912 - 3172), "SX #12 c2 +3172")
        c = (12, 0, 536820913)
        self.assertEqual(st.banner_text(c, 536810912), "CLK #12 +10001")


if __name__ == "__main__":
    r = unittest.main(exit=False, verbosity=1).result
    sys.exit(0 if r.wasSuccessful() else 1)
