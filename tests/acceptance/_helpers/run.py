"""Minimal pytest stand-in (pytest is not installed here). Usage: python3 -m _helpers.run [files...]"""
import glob, importlib, inspect, os, sys, time, traceback

class MP:
    def __init__(self): self.undo = []
    def setenv(self, k, v):
        self.undo.append((k, os.environ.get(k))); os.environ[k] = v
    def delenv(self, k, raising=False):
        self.undo.append((k, os.environ.get(k))); os.environ.pop(k, None)
    def restore(self):
        for k, v in reversed(self.undo):
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

files = sys.argv[1:] or sorted(glob.glob("_helpers/scenarios/test_*.py"))
res = {}
for f in files:
    mod = importlib.import_module(f[:-3].replace("/", "."))
    for n, fn in inspect.getmembers(mod, inspect.isfunction):
        if not n.startswith("test_"): continue
        mp = MP(); t = time.time()
        try:
            fn(*([mp] if "monkeypatch" in inspect.signature(fn).parameters else []))
            st = "pass"
        except Exception:
            st = "fail"; tb = traceback.format_exc()
        finally:
            mp.restore()
        res[f] = st
        print("%s %s %.1fs" % (st.upper(), f, time.time() - t))
        if st == "fail": print("   " + "\n   ".join(tb.strip().splitlines()[-6:]))
print("passed %d failed %d" % (list(res.values()).count("pass"), list(res.values()).count("fail")))
