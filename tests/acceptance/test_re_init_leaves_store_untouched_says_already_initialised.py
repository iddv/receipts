"""Re-init leaves store untouched and says already initialised with count.

Expected: Nothing in the store changes (the sessions and config are untouched) and the output says "already initialised" with a count of 3 sessions
Source: "The store already exists: it is left untouched and the system prints "already initialised" with the session count."
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_re_init_leaves_store_untouched_says_already_initialised():
    e = Env(); e.init()
    for i in range(3): e.record("true", "--name", "s%d" % i, cwd=e.tmp if i else None) if False else e.record("true"); 
    before = sorted(os.listdir(os.path.join(e.home)))
    cfg = open(e.cfg).read()
    p = e.cli("init")
    assert "already initialised" in p.out and "3 sessions" in p.out, p.out
    assert open(e.cfg).read() == cfg and sorted(os.listdir(e.home)) == before
