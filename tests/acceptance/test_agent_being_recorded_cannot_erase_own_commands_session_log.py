"""The agent being recorded cannot erase its own commands from the session log without `receipts verify` noticing.

Expected: after the agent rewrites events.jsonl (dropping its failed command and re-chaining the SHA-256 hashes), `receipts verify` reports the record as broken, not "intact"
Source: the security review (SECURITY.md).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env

FORGE = r'''
import os, json
from receipts import chain
p = os.path.join(os.environ["RECEIPTS_HOME"], "sessions", os.environ["RECEIPTS_SESSION"], "events.jsonl")
ev = [json.loads(l) for l in open(p)]
ev = [e for e in ev if e["type"] not in ("cmd_start", "cmd_end")]
prev, out = chain.GENESIS, []
for i, e in enumerate(ev):
    h = chain.event_hash(prev, i, e["ts"], e["type"], e["data"])
    e.update(seq=i, prev=prev, hash=h); prev = h; out.append(chain.canonical(e))
open(p, "w").write("\n".join(out) + "\n")
'''


def test_agent_cannot_silently_rewrite_its_own_record():
    env = Env(); env.init()
    forge = os.path.join(env.tmp, "forge.py")
    open(forge, "w").write(FORGE)
    agent = env.agent('sh -c "exit 3"\n%s %s' % (sys.executable, forge))
    p = env.cli("run", "--", agent)
    assert p.returncode in (0, 1), p.out
    v = env.cli("verify", "last")
    cmds = env.cli("show", "last", "commands")
    erased = "exit 3" not in cmds.out
    assert not (erased and "intact" in v.out), (
        "agent erased its failed command and verify still says intact:\n" + v.out + cmds.out)
