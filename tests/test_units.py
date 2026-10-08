import json
import os
import tempfile
import threading
import time
import unittest

from receipts import chain, claims, render, config, detect, shim, snapshot, sources


class Parsers(unittest.TestCase):
    def check(self, runner, out, passed, failed, skipped=0):
        r = detect.parse_results(runner, out)
        self.assertIsNotNone(r, runner)
        self.assertEqual((r["passed"], r["failed"], r["skipped"]), (passed, failed, skipped), runner)

    def test_all_runners(self):
        self.check("pytest", "==== 1 failed, 11 passed, 2 skipped, 1 xfailed in 0.9s ====", 11, 1, 2)
        self.check("unittest", "Ran 5 tests in 0.01s\n\nFAILED (failures=1, errors=1, skipped=1)", 2, 2, 1)
        self.check("unittest", "Ran 3 tests in 0.0s\n\nOK", 3, 0)
        self.check("jest", "Tests:       1 failed, 1 skipped, 5 passed, 7 total", 5, 1, 1)
        self.check("vitest", "      Tests  1 failed | 9 passed | 2 skipped (12)", 9, 1, 2)
        self.check("mocha", "  5 passing (20ms)\n  1 pending\n  2 failing", 5, 2, 1)
        self.check("go", "--- PASS: TestA (0.00s)\n--- FAIL: TestB (0.00s)\n--- SKIP: TestC\nFAIL\tpkg\t0.1s", 1, 1, 1)
        self.check("cargo", "test result: FAILED. 3 passed; 1 failed; 2 ignored; 0 measured", 3, 1, 2)
        self.check("rspec", "10 examples, 2 failures, 1 pending", 7, 2, 1)
        self.check("phpunit", "OK (5 tests, 10 assertions)", 5, 0)
        self.check("phpunit", "Tests: 6, Assertions: 8, Failures: 1, Skipped: 1.", 4, 1, 1)
        self.check("maven", "[ERROR] Tests run: 8, Failures: 1, Errors: 1, Skipped: 2", 4, 2, 2)
        self.check("gradle", "10 tests completed, 2 failed, 1 skipped", 7, 2, 1)
        self.check("dotnet", "Failed!  - Failed:     1, Passed:     5, Skipped:     2, Total:     8", 5, 1, 2)
        self.check("npm", "Tests:       3 passed, 3 total", 3, 0)

    def test_outcome_fails_on_count_even_with_exit_zero(self):
        self.assertEqual(detect.test_outcome("pytest", 0, "=== 1 failed, 2 passed in 1s ===")["status"], "fail")
        self.assertEqual(detect.test_outcome("custom", 3, "")["status"], "fail")


class Detection(unittest.TestCase):
    def test_runners(self):
        cases = {"pytest -q": "pytest", "cd app && python -m pytest tests/": "pytest", "python3 -m unittest": "unittest",
                 "npx jest --ci": "jest", "npx vitest run": "vitest", "go test ./...": "go", "cargo test": "cargo",
                 "bundle exec rspec": "rspec", "vendor/bin/phpunit": "phpunit", "mvn -q test": "maven",
                 "./gradlew test": "gradle", "dotnet test": "dotnet", "npm test": "npm", "yarn run test:unit": "npm",
                 "CI=1 uv run pytest": "pytest", "ls -la": None, "git commit -m 'add tests'": None}
        for cmd, want in cases.items():
            self.assertEqual(detect.detect_runner(cmd), want, cmd)
        self.assertEqual(detect.detect_runner("make check-all", "make check-all"), "custom")

    def test_build(self):
        self.assertTrue(detect.is_build("npm run build"))
        self.assertTrue(detect.is_build("cargo build --release"))
        self.assertFalse(detect.is_build("npm test"))

    def test_test_files_and_skips(self):
        for p in ("tests/a.py", "test_x.py", "x_test.go", "a.test.ts", "b.spec.js", "src/__tests__/c.js", "spec/m_spec.rb"):
            self.assertTrue(detect.is_test_file(p), p)
        self.assertFalse(detect.is_test_file("src/latest.py"))
        diff = "+++ b/t.py\n+@pytest.mark.skip(reason='x')\n+  it.skip('a', () => {})\n+\tt.Skip(\"x\")\n+#[ignore]\n+@Disabled\n+[Fact(Skip=\"x\")]\n+$this->markTestSkipped();\n-@unittest.skip\n"
        self.assertEqual(len(detect.skip_markers_added(diff)), 7)
        self.assertEqual(len(detect.skip_markers_added("+  skip 'later'\n", "spec/a_spec.rb")), 1)
        self.assertEqual(len(detect.skip_markers_added("+  skip = True\n", "a.py")), 0)

    def test_claude_code_wrapper_unwrapped(self):
        raw = "source /home/u/.claude/shell-snapshots/snapshot-bash-1.sh && eval 'npm test' \\< /dev/null && pwd -P >| /tmp/claude-cwd"
        self.assertEqual(detect.normalize_command(raw), "npm test")


class Claims(unittest.TestCase):
    def kinds(self, text):
        return [(c["kind"], c.get("path") or c.get("command") or c.get("count")) for c in claims.extract(text)]

    def test_tests_pass(self):
        self.assertIn(("tests_pass", None), self.kinds("All tests pass."))
        self.assertIn(("tests_pass", 42), self.kinds("42 tests passed."))
        self.assertIn(("tests_pass", 12), self.kinds("Ran the suite — all 12 tests passed"))
        self.assertNotIn("tests_pass", [k for k, _ in self.kinds("The tests do not pass yet.")])
        self.assertNotIn("tests_pass", [k for k, _ in self.kinds("3 tests failed, 10 passed.")])

    def test_files_and_commands(self):
        k = self.kinds("Updated src/app.py and created `docs/guide.md`. Removed old/legacy.js.\nRan `npm run build`.")
        self.assertIn(("file", "src/app.py"), k)
        self.assertIn(("file", "docs/guide.md"), k)
        self.assertIn(("file", "old/legacy.js"), k)
        self.assertIn(("command", "npm run build"), k)
        c = {x.get("path"): x.get("change") for x in claims.extract("Created docs/guide.md. Removed old/legacy.js.")}
        self.assertEqual(c, {"docs/guide.md": "created", "old/legacy.js": "deleted"})

    def test_heading_list(self):
        c = claims.extract("Files changed:\n- src/a.py\n- src/b.py\n\nDone.")
        self.assertEqual([(x["path"], x["change"]) for x in c if x["kind"] == "file"], [("src/a.py", "modified"), ("src/b.py", "modified")])

    def test_build_and_no_urls(self):
        k = self.kinds("The build succeeds. See https://example.com/a.html for details, e.g. version 1.2.3.")
        self.assertIn(("build_ok", None), k)
        self.assertFalse([x for x in k if x[0] == "file"])

    def test_mentions(self):
        changed = ["src/a/util.py", "src/b/util.py", "src/main.py"]
        self.assertTrue(claims.mentioned("edited src/a/util.py", "src/a/util.py", changed))
        self.assertFalse(claims.mentioned("edited util.py", "src/a/util.py", changed))
        self.assertTrue(claims.mentioned("tweaked main.py", "src/main.py", changed))
        self.assertFalse(claims.mentioned("tweaked domain.py", "src/main.py", changed))


class Chain(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = self.t.name

    def tearDown(self):
        self.t.cleanup()

    def test_append_verify_tamper(self):
        for i in range(5):
            chain.append(self.d, "x", {"i": i})
        ev = chain.read(self.d)
        ok, final, bad, _ = chain.verify_events(ev)
        self.assertTrue(ok)
        self.assertEqual(final, ev[-1]["hash"])
        ev[2]["data"]["i"] = 99
        self.assertEqual(chain.verify_events(ev)[2], 2)
        ev = chain.read(self.d)
        del ev[1]
        self.assertFalse(chain.verify_events(ev)[0])

    def test_torn_tail_repaired(self):
        chain.append(self.d, "x", {})
        with open(os.path.join(self.d, "events.jsonl"), "a") as f:
            f.write('{"seq": 1, "partial')
        self.assertEqual(len(chain.read(self.d)), 1)
        chain.append(self.d, "y", {})
        self.assertTrue(chain.verify_events(chain.read(self.d))[0])

    def test_parallel_writers_serialised(self):
        ths = [threading.Thread(target=lambda k=k: [chain.append(self.d, "w", {"k": k, "j": j}) for j in range(20)])
               for k in range(4)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        ev = chain.read(self.d)
        self.assertEqual(len(ev), 80)
        self.assertTrue(chain.verify_events(ev)[0])

    def test_lock_timeout(self):
        p = os.path.join(self.d, "lock")
        with chain.Lock(p, 1):
            t0 = time.monotonic()
            with self.assertRaises(chain.BusyError):
                # flock is per open file description, so a second open contends
                with chain.Lock(p, 0.2):
                    pass
            self.assertGreaterEqual(time.monotonic() - t0, 0.2)


class Witness(unittest.TestCase):
    def test_rechained_rewrite_is_caught_by_witness(self):
        d = tempfile.mkdtemp()
        evs = [chain.append(d, "cmd_start", {"n": i}) for i in range(3)]
        chain.append(d, "witness", {"events": [[e["seq"], e["hash"]] for e in evs], "channel_ok": True})
        self.assertTrue(chain.verify_events(chain.read(d))[0])
        # Re-chain without event #1, as an agent rewriting the log would.
        kept = [e for e in chain.read(d) if e["seq"] != 1]
        prev, out = chain.GENESIS, []
        for i, e in enumerate(kept):
            e.update(seq=i, prev=prev, hash=chain.event_hash(prev, i, e["ts"], e["type"], e["data"]))
            prev = e["hash"]
            out.append(e)
        ok, _, bad, why = chain.verify_events(out)
        self.assertFalse(ok)
        self.assertEqual(bad, 1)
        self.assertIn("witnessed", why)

    def test_tampered_channel_is_reported(self):
        d = tempfile.mkdtemp()
        chain.append(d, "witness", {"events": [], "channel_ok": False})
        self.assertFalse(chain.verify_events(chain.read(d))[0])


class MarkdownEscaping(unittest.TestCase):
    def test_agent_text_cannot_open_comments_tags_or_code(self):
        t = render._md("All tests pass. <!-- `x` <b>[l](u)</b>")
        for bad in ("<!--", "<b>", "`", "[l]"):
            self.assertNotIn(bad, t)
        self.assertEqual(render._mdcode("a`b\nc"), "`a'b c`")


class Snapshots(unittest.TestCase):
    def test_diff_binary_exclusions(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as blobs:
            def w(rel, data):
                os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
                with open(os.path.join(root, rel), "wb") as f:
                    f.write(data)
            cfg = {k: v[0] for k, v in config.SETTINGS.items()}
            w("a.txt", b"one\ntwo\n")
            w("bin.dat", b"\0\1\2")
            w("gone.py", b"x = 1\n")
            w("node_modules/m/index.js", b"x")
            w("pkg/__pycache__/a.pyc", b"x")
            before = snapshot.take(root, cfg, blobs)
            self.assertEqual(set(before["files"]), {"a.txt", "bin.dat", "gone.py"})
            w("a.txt", b"one\nTWO\n")
            w("bin.dat", b"\0\1\3")
            w("new.md", b"hi\n")
            os.remove(os.path.join(root, "gone.py"))
            after = snapshot.take(root, cfg)
            ch = {c["path"]: c for c in snapshot.compare(before, after, root, blobs)}
            self.assertEqual({p: c["change"] for p, c in ch.items()},
                             {"a.txt": "modified", "bin.dat": "modified", "new.md": "created", "gone.py": "deleted"})
            self.assertIn("+TWO", ch["a.txt"]["diff"])
            self.assertIsNone(ch["bin.dat"]["diff"])
            self.assertIn("-x = 1", ch["gone.py"]["diff"])

    def test_file_limit(self):
        with tempfile.TemporaryDirectory() as root:
            for i in range(5):
                open(os.path.join(root, "f%d" % i), "w").write("x")
            cfg = dict({k: v[0] for k, v in config.SETTINGS.items()}, **{"files.max_files": 3})
            s = snapshot.take(root, cfg)
            self.assertEqual((s["count"], s["over_limit"]), (5, 2))


class ShimParse(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(shim._parse(["-c", "ls"]), "ls")
        self.assertEqual(shim._parse(["-lc", "npm test"]), "npm test")
        self.assertEqual(shim._parse(["-c", "-l", "echo hi"]), "echo hi")
        self.assertEqual(shim._parse(["-o", "pipefail", "-c", "x"]), "x")
        self.assertEqual(shim._parse(["script.sh", "a"]), "script.sh a")
        self.assertIsNone(shim._parse([]))
        self.assertIsNone(shim._parse(["-i"]))
        self.assertIsNone(shim._parse(["-s"]))


class Sources(unittest.TestCase):
    def test_claude_and_codex(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
            cwd = os.path.realpath(cwd)
            key = "".join(c if c.isalnum() else "-" for c in cwd)
            d = os.path.join(home, ".claude", "projects", key)
            os.makedirs(d)
            now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
            lines = [{"type": "assistant", "timestamp": now, "cwd": cwd, "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}}]}},
                {"type": "assistant", "timestamp": now, "cwd": cwd, "message": {"content": [
                    {"type": "text", "text": "Done. All tests pass."}]}}]
            with open(os.path.join(d, "s.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(x) for x in lines))
            r = sources.claude_code(cwd, time.time() - 10, time.time(), home=home)
            self.assertEqual(r["text"], "Done. All tests pass.")
            self.assertEqual(r["tool_calls"], ["pytest -q"])

            cd = os.path.join(home, ".codex", "sessions", "2026", "10", "08")
            os.makedirs(cd)
            items = [{"type": "session_meta", "payload": {"cwd": cwd}},
                     {"type": "response_item", "payload": {"type": "function_call", "name": "shell",
                                                           "arguments": json.dumps({"command": ["bash", "-lc", "go test ./..."]})}},
                     {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                           "content": [{"type": "output_text", "text": "Fixed it."}]}}]
            with open(os.path.join(cd, "rollout-x.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(x) for x in items))
            r = sources.codex(cwd, time.time() - 10, time.time(), home=home)
            self.assertEqual((r["text"], r["tool_calls"]), ("Fixed it.", ["go test ./..."]))


if __name__ == "__main__":
    unittest.main()
