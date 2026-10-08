"""Agent-written summary text is neutralised in the Markdown export, so it cannot hide the rest of the report (e.g. with an HTML comment opener) when pasted into a PR.

Expected: the raw sequence "<!--" from the summary does not appear unescaped in the exported Markdown
Source: the security review (SECURITY.md).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env


def test_summary_cannot_inject_html_comment_into_markdown():
    env = Env(); env.init()
    env.write("test_b.py", "x\n")
    agent = env.agent('sh -c "exit 3"\nrm test_b.py')
    env.cli("run", "--", agent)
    s = env.cli("summary", "last", input="All tests pass. <!--\n")
    out = os.path.join(env.tmp, "r.md")
    e = env.cli("export", "last", "--format", "md", "--out", out)
    assert e.returncode == 0, e.out + s.out
    md = open(out).read()
    assert "Tests claimed passing" in md, md
    assert "<!--" not in md, md
