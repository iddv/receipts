"""--since day boundary is 00:00 UTC.

Expected: session included by its UTC date
Source: "operator setting list.since_timezone"
Runs with the operator setting `list.since_timezone` = `utc` (environment variable LIST_SINCE_TIMEZONE).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('LIST_SINCE_TIMEZONE', 'utc')


import time, calendar
from _helpers.driver import Env

def test_since_day_boundary_00_00_utc(monkeypatch):
    monkeypatch.setenv("LIST_SINCE_TIMEZONE", "utc")
    e = Env(); e.init(); e.env["LIST_SINCE_TIMEZONE"] = "utc"
    # pick a zone whose calendar day differs from UTC's right now
    tz = "Pacific/Kiritimati" if time.gmtime().tm_hour >= 10 else "Pacific/Pago_Pago"
    e.env["TZ"] = tz
    p = e.record("true")
    started = calendar.timegm(time.strptime(e.export_json(p.sid)["started"][:19], "%Y-%m-%dT%H:%M:%S"))
    utc_day = time.strftime("%Y-%m-%d", time.gmtime(started))
    lt = __import__("subprocess").run(["date", "-d", "@%d" % started, "+%Y-%m-%d"], env={"TZ": tz}, capture_output=True, text=True).stdout.strip()
    assert lt != utc_day
    in_utc = p.sid in e.cli("list", "--since", utc_day).stdout and p.sid not in e.cli("list", "--since", max(utc_day, lt) if lt > utc_day else utc_day[:8] + "%02d" % (int(utc_day[8:]) + 1)).stdout
    in_local = p.sid in e.cli("list", "--since", lt).stdout and p.sid not in e.cli("list", "--since", time.strftime("%Y-%m-%d", time.gmtime(calendar.timegm(time.strptime(lt, "%Y-%m-%d")) + 86400))).stdout
    assert in_utc, e.cli("list").stdout
