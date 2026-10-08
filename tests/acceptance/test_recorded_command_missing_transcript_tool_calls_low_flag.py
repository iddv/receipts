"""Recorded command missing from transcript tool calls -> low flag.

Expected: A low flag is shown for the recorded command missing from the transcript
Source: "commands recorded that are absent from the transcript's tool calls"
"""

from _helpers.driver import Env, cli_tty
import os, json, re, time, subprocess

def test_recorded_command_missing_transcript_tool_calls_low_flag():
    e = Env(); e.init(); ws = os.path.realpath(e.ws); key = "".join(c if c.isalnum() else "-" for c in ws)
    d = os.path.join(e.userhome, ".claude", "projects", key); os.makedirs(d)
    w = os.path.join(e.tmp, "w.py")
    open(w, "w").write("import json,time\nnow=time.strftime('%%Y-%%m-%%dT%%H:%%M:%%S.000Z',time.gmtime())\nL=[{'type':'assistant','timestamp':now,'cwd':%r,'message':{'content':[{'type':'tool_use','name':'Bash','input':{'command':'echo one'}}]}},{'type':'assistant','timestamp':now,'cwd':%r,'message':{'content':[{'type':'text','text':'Done.'}]}}]\nopen(%r,'w').write(chr(10).join(json.dumps(x) for x in L))\n" % (ws, ws, os.path.join(d, "s.jsonl")))
    p = e.record("bash -c 'echo one'; bash -c 'echo two'; python3 %s" % w)
    if "Done." not in json.dumps(e.export_json(p.sid)["summary"] or {}): e.cli("summary", p.sid, "--yes")
    assert len(e.kinds(p.sid, "low")) == 1 and "echo two" in json.dumps(e.export_json(p.sid)["flags"]), e.flags(p.sid)
