"""Session lock busy: wait ~5s then 'session busy'.

Expected: The command waits about 5 s and then fails with "session busy" without recording anything. If the lock is released within 5 s, it succeeds
Source: "If it is held, the second caller waits up to 5 s (default), then fails with "session busy"."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_session_lock_busy_wait_5s_session_busy():
    import fcntl, glob
    e = Env(); e.init(); p = e.record("true"); (fid, *_), = e.flags(p.sid)
    locks = [f for f in glob.glob(os.path.join(e.home, "**", "*lock*"), recursive=True) if p.sid in f]
    assert locks, os.listdir(os.path.join(e.home))
    fh = open(locks[0], "a"); fcntl.flock(fh, fcntl.LOCK_EX)
    t0 = time.time(); r = e.cli("ack", p.sid, fid, "--note", "x"); dt = time.time() - t0
    fh.close()
    assert "session busy" in r.out and 4 <= dt <= 8 and e.flags(p.sid)[0][3] is False, (r.out, dt)
