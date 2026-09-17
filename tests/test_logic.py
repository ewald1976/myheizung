"""Tests der reinen Zeitplan-Logik: python3 -m unittest discover tests"""

import importlib.util
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_spec = importlib.util.spec_from_file_location(
    "logic", Path(__file__).parents[1] / "custom_components" / "heizplan" / "logic.py"
)
logic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(logic)

TZ = ZoneInfo("Europe/Berlin")
WEEK = logic.normalize_week(
    {
        "mon": [{"from": "17:00", "to": "22:00"}, {"from": "06:00", "to": "08:00"}],
        "tue": [{"from": "06:00", "to": "08:00"}],
        "fri": [{"from": "20:00", "to": "24:00"}],
        "sat": [{"from": "00:00", "to": "01:00"}],
    }
)


def at(day, hhmm):  # 2026-09-14 ist ein Montag
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 9, 14 + day, h, m, tzinfo=TZ)


class LogicTest(unittest.TestCase):
    def test_normalize_sorts_and_merges(self):
        week = logic.normalize_week({"mon": [{"from": "09:00", "to": "12:00"}, {"from": "07:00", "to": "10:00"}]})
        self.assertEqual(week["mon"], [{"from": "07:00", "to": "12:00"}])
        self.assertEqual(week["sun"], [])

    def test_normalize_rejects_invalid(self):
        with self.assertRaises(ValueError):
            logic.normalize_week({"mon": [{"from": "10:00", "to": "09:00"}]})
        with self.assertRaises(ValueError):
            logic.normalize_week({"mon": [{"from": "10:00", "to": "25:00"}]})

    def test_plan_mode(self):
        self.assertEqual(logic.plan_mode(WEEK, at(0, "06:00")), logic.MODE_COMFORT)
        self.assertEqual(logic.plan_mode(WEEK, at(0, "07:59")), logic.MODE_COMFORT)
        self.assertEqual(logic.plan_mode(WEEK, at(0, "08:00")), logic.MODE_ECO)
        self.assertEqual(logic.plan_mode(WEEK, at(4, "23:59")), logic.MODE_COMFORT)

    def test_exception_overrides_plan_and_latest_wins(self):
        exceptions = [
            {"id": "a", "rooms": ["buro"], "start": at(0, "05:00"), "end": at(0, "09:00"), "mode": "eco"},
            {"id": "b", "rooms": ["buro"], "start": at(0, "07:00"), "end": at(0, "07:30"), "mode": "comfort"},
        ]
        self.assertEqual(logic.desired_mode(WEEK, exceptions, "buro", at(0, "06:30"))[0], "eco")
        mode, exc = logic.desired_mode(WEEK, exceptions, "buro", at(0, "07:10"))
        self.assertEqual((mode, exc["id"]), ("comfort", "b"))
        self.assertEqual(logic.desired_mode(WEEK, exceptions, "wohnzimmer", at(0, "06:30"))[0], "comfort")

    def test_next_change_plan(self):
        self.assertEqual(logic.next_change(WEEK, [], "buro", at(0, "07:00")), (at(0, "08:00"), "eco"))
        self.assertEqual(logic.next_change(WEEK, [], "buro", at(0, "23:00")), (at(1, "06:00"), "comfort"))

    def test_next_change_skips_seamless_midnight(self):
        # Fr 20:00–24:00 und Sa 00:00–01:00 sind durchgehend warm.
        self.assertEqual(logic.next_change(WEEK, [], "buro", at(4, "21:00")), (at(5, "01:00"), "eco"))

    def test_next_change_with_exception(self):
        exceptions = [{"id": "x", "rooms": ["buro"], "start": at(0, "07:00"), "end": at(0, "12:00"), "mode": "comfort"}]
        self.assertEqual(logic.next_change(WEEK, exceptions, "buro", at(0, "06:30")), (at(0, "12:00"), "eco"))

    def test_next_change_none_for_empty_plan(self):
        self.assertIsNone(logic.next_change(logic.normalize_week({}), [], "buro", at(0, "06:30")))


if __name__ == "__main__":
    unittest.main()
