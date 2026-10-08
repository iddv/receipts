"""`receipts demo`: six realistic sessions across three sample projects."""
import difflib
import os
import time

from receipts import chain, sessions, store
from receipts.reconcile import flag_totals

API, WEB, GO = "/home/demo/projects/acme-api", "/home/demo/projects/web-dashboard", "/home/demo/projects/billing-svc"


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"


def _diff(path, old, new):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        "a/" + path if old is not None else "/dev/null",
                                        "b/" + path if new is not None else "/dev/null"))


class Builder:
    def __init__(self, t0, name, agent, cwd, files, test_cmd=None, head="4f1c2ab9e0d3"):
        self.t = t0
        self.sid = store.new_session_id(t0)
        self.dir = store.session_dir(self.sid)
        os.makedirs(self.dir, mode=0o700)
        self.files = list(files)
        self.n = 0
        self.head = head
        self.ev("session_start", {"id": self.sid, "name": name, "agent": agent, "agent_path": "/usr/local/bin/" + agent[0],
                                  "cwd": cwd, "test_cmd": test_cmd, "user": "demo", "host": "demo-host",
                                  "receipts_version": "demo", "capture_output": "tail", "demo": True})
        self.ev("snapshot", {"phase": "before", "count": len(self.files), "over_limit": 0, "paths": sorted(self.files),
                             "git": {"head": head, "dirty": False}, "manifest_sha256": "demo", "warning": None})
        self.changes = []

    def ev(self, etype, data, dt=1):
        self.t += dt
        chain.append(self.dir, etype, data, ts=_iso(self.t))

    def cmd(self, cmd, exit=0, output="", dur=900, dt=20):
        self.n += 1
        self.ev("cmd_start", {"n": self.n, "cmd": cmd, "shell": "bash", "argv": ["-c", cmd], "cwd": "", "parent": None, "pid": 0}, dt)
        self.ev("cmd_end", {"n": self.n, "exit": exit, "duration_ms": dur, "signal": None, "output": output,
                            "output_truncated": False, "output_mode": "tail"}, max(1, dur // 1000))

    def change(self, path, old, new):
        kind = "created" if old is None else "deleted" if new is None else "modified"
        self.changes.append({"path": path, "change": kind, "size_before": old and len(old), "size_after": new and len(new),
                             "hash_before": None, "hash_after": None, "binary": False,
                             "diff": _diff(path, old or "", new or ""), "diff_note": None})
        if kind == "created":
            self.files.append(path)
        if kind == "deleted":
            self.files.remove(path)

    def end(self, rc=0, interrupted=False, new_head=None):
        for ch in self.changes:
            self.ev("file_change", ch, 0)
        self.ev("snapshot", {"phase": "after", "count": len(self.files), "over_limit": 0, "paths": sorted(self.files),
                             "git": {"head": new_head or self.head, "dirty": bool(self.changes)},
                             "manifest_sha256": "demo", "warning": None}, 2)
        self.ev("run_end", {"exit_code": rc, "signal": None, "interrupted": interrupted}, 0)

    def summary(self, text, cfg, source="claude-code:demo-transcript.jsonl", tool_calls=None):
        self.t += 30
        sessions.attach_summary(self.sid, text, source, tool_calls, cfg, ts=_iso(self.t))


PYTEST_OK = "============================= test session starts ==============================\ncollected 12 items\n\ntests/test_users.py ........                                             [ 66%]\ntests/test_billing.py ....                                               [100%]\n\n============================== 12 passed in 0.84s ==============================="
PYTEST_FAIL = ("collected 12 items\n\ntests/test_users.py ........                                             [ 66%]\n"
               "tests/test_billing.py ...F                                               [100%]\n\n=================================== FAILURES ===================================\n"
               "____________________________ test_invoice_rounding _____________________________\n\n    def test_invoice_rounding():\n>       assert invoice_total([0.1, 0.2]) == 0.3\nE       assert 0.30000000000000004 == 0.3\n\n"
               "tests/test_billing.py:41: AssertionError\n=========================== short test summary info ============================\n"
               "FAILED tests/test_billing.py::test_invoice_rounding - assert 0.30000000000000004 == 0.3\n========================= 1 failed, 11 passed in 0.91s =========================")
API_FILES = ["pyproject.toml", "README.md", "src/acme/__init__.py", "src/acme/users.py", "src/acme/billing.py",
             "tests/test_users.py", "tests/test_billing.py"]
WEB_FILES = ["package.json", "tsconfig.json", ".eslintrc.json", "vite.config.ts", "src/main.tsx", "src/api.ts",
             "src/components/Chart.tsx", "src/components/Chart.test.tsx", "src/components/Table.tsx"]
GO_FILES = ["go.mod", "cmd/billing/main.go", "internal/rates/rates.go", "internal/rates/rates_test.go",
            "internal/invoice/invoice.go", "internal/invoice/invoice_test.go"]


def has_demo():
    for sid in store.list_ids():
        evs = chain.read(store.session_dir(sid))
        if evs and evs[0]["type"] == "session_start" and evs[0]["data"].get("demo"):
            return True
    return False


def reset():
    import shutil
    n = 0
    for sid in store.list_ids():
        evs = chain.read(store.session_dir(sid))
        if evs and evs[0]["data"].get("demo"):
            shutil.rmtree(store.session_dir(sid))
            n += 1
    if n:
        store.audit("demo_reset", {"deleted": n})
    return n


def load(cfg):
    now = time.time()
    t = now - 6 * 86400
    ids = []

    # 1. Clean run, no flags
    b = Builder(t, "fix-pagination", ["claude"], API, API_FILES, "pytest -q")
    b.cmd("rg -n 'def list_users' src", 0, "src/acme/users.py:14:def list_users(page, per_page=20):")
    b.cmd("pytest -q", 0, PYTEST_OK, 1400)
    b.change("src/acme/users.py", "def list_users(page, per_page=20):\n    start = page * per_page\n    return USERS[start:start + per_page]\n",
             "def list_users(page, per_page=20):\n    start = (page - 1) * per_page\n    return USERS[start:start + per_page]\n")
    b.end(new_head="4f1c2ab9e0d3")
    b.summary("Fixed an off-by-one in pagination: `list_users` in src/acme/users.py now treats pages as 1-based.\n\n"
              "Ran `pytest -q` — all 12 tests passed.", cfg,
              tool_calls=["rg -n 'def list_users' src", "pytest -q"])
    ids.append(b.sid)

    # 2. "All tests pass" while pytest failed
    b = Builder(t + 86400, "invoice-rounding", ["codex", "exec", "fix invoice rounding"], API, API_FILES, "pytest -q")
    b.cmd("pytest -q tests/test_billing.py", 1, PYTEST_FAIL.replace("12 items", "4 items").replace("1 failed, 11 passed", "1 failed, 3 passed"), 1100)
    b.change("src/acme/billing.py", "def invoice_total(items):\n    return sum(items)\n",
             "def invoice_total(items):\n    return round(sum(items), 2)\n")
    b.cmd("pytest -q", 1, PYTEST_FAIL, 1300)
    b.end()
    b.summary("I updated `invoice_total` in src/acme/billing.py to round to 2 decimal places.\n\nAll tests pass.", cfg,
              source="codex:~/.codex/sessions/demo/rollout.jsonl", tool_calls=["pytest -q tests/test_billing.py", "pytest -q"])
    ids.append(b.sid)

    # 3. Deleted a test file without mentioning it
    b = Builder(t + 2 * 86400, "rates-refactor", ["claude"], GO, GO_FILES, "go test ./...")
    b.cmd("go test ./...", 1, "--- FAIL: TestLegacyRate (0.00s)\n    rates_test.go:22: got 0.19, want 0.2\nFAIL\nFAIL\texample.com/billing/internal/rates\t0.004s\nok  \texample.com/billing/internal/invoice\t0.006s\nFAIL", 3200)
    b.change("internal/rates/rates.go", "func Rate(c string) float64 {\n\treturn legacy[c]\n}\n",
             "func Rate(c string) float64 {\n\tif r, ok := table[c]; ok {\n\t\treturn r\n\t}\n\treturn 0\n}\n")
    b.change("internal/rates/rates_test.go", "func TestLegacyRate(t *testing.T) {\n\tif Rate(\"NL\") != 0.2 {\n\t\tt.Fatalf(\"got %v\", Rate(\"NL\"))\n\t}\n}\n", None)
    b.cmd("go test ./...", 0, "?   \texample.com/billing/internal/rates\t[no test files]\nok  \texample.com/billing/internal/invoice\t0.006s", 2900)
    b.end()
    b.summary("Refactored rate lookup in internal/rates/rates.go to use the new table.\n\n`go test ./...` passes.", cfg,
              tool_calls=["go test ./...", "go test ./..."])
    ids.append(b.sid)

    # 4. Added it.skip
    b = Builder(t + 3 * 86400, "chart-fix", ["gemini"], WEB, WEB_FILES, "npx vitest run")
    b.cmd("npx vitest run", 1, " FAIL  src/components/Chart.test.tsx > Chart > renders empty state\n Test Files  1 failed | 3 passed (4)\n      Tests  1 failed | 9 passed (10)", 4100)
    b.change("src/components/Chart.tsx", "export function Chart({ data }) {\n  return <svg>{data.map(bar)}</svg>;\n}\n",
             "export function Chart({ data }) {\n  if (!data?.length) return null;\n  return <svg>{data.map(bar)}</svg>;\n}\n")
    b.change("src/components/Chart.test.tsx", "describe('Chart', () => {\n  it('renders empty state', () => {\n    expect(render(<Chart data={[]} />)).toMatchSnapshot();\n  });\n});\n",
             "describe('Chart', () => {\n  it.skip('renders empty state', () => {\n    expect(render(<Chart data={[]} />)).toMatchSnapshot();\n  });\n});\n")
    b.cmd("npx vitest run", 0, " Test Files  4 passed (4)\n      Tests  9 passed | 1 skipped (10)", 3900)
    b.end()
    b.summary("Fixed the crash in Chart.tsx when data is empty. Tests pass (`npx vitest run`).", cfg,
              source="agent-stdout")
    ids.append(b.sid)

    # 5. Unmentioned config changes; flags acknowledged; session closed
    b = Builder(t + 4 * 86400, "api-timeout", ["aider", "--model", "sonnet"], WEB, WEB_FILES, "npm test")
    b.change("src/api.ts", "export const TIMEOUT_MS = 5000;\n", "export const TIMEOUT_MS = 15000;\n")
    b.change("package.json", '{\n  "name": "web-dashboard",\n  "dependencies": {\n    "axios": "^1.6.0"\n  }\n}\n',
             '{\n  "name": "web-dashboard",\n  "dependencies": {\n    "axios": "^1.7.4"\n  }\n}\n')
    b.change("tsconfig.json", '{\n  "compilerOptions": {\n    "strict": true\n  }\n}\n', '{\n  "compilerOptions": {\n    "strict": false\n  }\n}\n')
    b.change(".eslintrc.json", '{\n  "rules": {}\n}\n', '{\n  "rules": {\n    "@typescript-eslint/no-explicit-any": "off"\n  }\n}\n')
    b.cmd("npm test", 0, "Tests:       14 passed, 14 total\nTime:        2.1 s", 2600)
    b.cmd("npm run build", 0, "vite v5.2.0 building for production...\n✓ built in 3.2s", 3300)
    b.end()
    b.summary("Raised the API timeout to 15s in src/api.ts. npm test is green and the build succeeds.", cfg,
              source="aider:" + WEB + "/.aider.chat.history.md")
    m, flags, _, _ = sessions.report(b.sid, cfg)
    notes = {"package.json": "axios bump requested in ticket WEB-412",
             "tsconfig.json": "temporary; reverted in follow-up PR",
             ".eslintrc.json": "agreed with reviewer"}
    for f in flags:
        path = f["evidence"][0].get("path") if f["evidence"] else None
        b.t += 60
        sessions.ack(b.sid, f["id"], notes.get(path, "reviewed"), cfg, ts=_iso(b.t))
    b.t += 60
    sessions.close(b.sid, cfg, ts=_iso(b.t))
    ids.append(b.sid)

    # 6. Interrupted session (Ctrl-C), no summary
    b = Builder(t + 5 * 86400, "invoice-export", ["codex"], GO, GO_FILES, "go test ./...")
    b.cmd("go build ./...", 0, "", 5200)
    b.cmd("go test ./internal/invoice/...", 1, "--- FAIL: TestExportCSV (0.01s)\n    invoice_test.go:58: missing header row\nFAIL\nFAIL\texample.com/billing/internal/invoice\t0.012s", 2100)
    b.change("internal/invoice/invoice.go", "func Export(w io.Writer) error {\n\treturn nil\n}\n",
             "func Export(w io.Writer) error {\n\tcw := csv.NewWriter(w)\n\tdefer cw.Flush()\n\treturn nil\n}\n")
    b.end(rc=130, interrupted=True)
    ids.append(b.sid)
    return ids
