"""Flow F3: Attach the agent's summary.

Flow: F3 in SCOPE.md.
"""

import json, os, time
from _helpers.driver import Env

def test_flow_f3_attach_agent_summary():
    e = Env(); e.init(); e.write("a.py", "x=1\n")
    ws = os.path.realpath(e.ws)
    key = "".join(c if c.isalnum() else "-" for c in ws)
    d = os.path.join(e.userhome, ".claude", "projects", key); os.makedirs(d)
    # agent edits a file, runs a command, and writes its transcript at the end
    script = os.path.join(e.tmp, "w.py")
    open(script, "w").write(
        "import json,time,sys\nnow=time.strftime('%%Y-%%m-%%dT%%H:%%M:%%S.000Z',time.gmtime())\n"
        "L=[{'type':'assistant','timestamp':now,'cwd':%r,'message':{'content':[{'type':'tool_use','name':'Bash','input':{'command':'echo hi'}}]}},"
        "{'type':'assistant','timestamp':now,'cwd':%r,'message':{'content':[{'type':'text','text':'Done. I updated a.py and ran `echo hi`.'}]}}]\n"
        "open(%r,'w').write('\\n'.join(json.dumps(x) for x in L))\n" % (ws, ws, os.path.join(d, "s.jsonl")))
    p = e.record("bash -c 'echo hi'\necho x=2 > a.py\npython3 %s" % script, input="y\n")
    assert p.sid, p.out
    s = e.cli("summary", p.sid, "--yes")
    if "already has a summary" not in s.out:
        assert "Done. I updated a.py" in s.out, s.out
    rep = e.export_json(p.sid)
    assert rep["summary"] and "updated a.py" in rep["summary"]["text"]
    assert "claude" in rep["summary"]["source"].lower()
    kinds = [c["kind"] for c in rep["claims"]]
    assert "file" in kinds and "command" in kinds
    # paste fallback on another session
    p2 = e.record("echo y > a.py")
    s2 = e.cli("summary", p2.sid, input="Changed a.py. All tests pass.\n")
    rep2 = e.export_json(p2.sid)
    assert rep2["summary"]["text"].strip().startswith("Changed a.py"), s2.out
