"""Rule-based claim extraction from an agent's summary.

All patterns are case-insensitive. Claim kinds:

  tests_pass   "all tests pass", "tests are passing", "42 tests passed", "test suite is green"
               (optional ``count`` when a number of passing tests is stated)
  tests_run    "ran the tests", "tests were run/executed"
  tests_added  "added tests", "wrote 3 new tests"
  build_ok     "build succeeds", "builds successfully", "compiles cleanly"
  file         a path next to a verb: created/added/new/wrote -> created,
               modified/updated/changed/edited/fixed/refactored -> modified,
               deleted/removed -> deleted.  A heading such as "Files changed:" carries
               its verb to the bullet lines below it.
  command      text in backticks (or a ``$ cmd`` line in a code block) whose first word
               is a known program or starts with ./ — e.g. `npm test`.

Separately, *any* occurrence of a file's relative path, or of its basename when that
basename is unique among the changed files, counts as a mention of that file.
"""
import re

NEG = re.compile(r"\b(not|n't|never|no longer|cannot|can't|unable|couldn't|didn't|won't|wasn't|weren't|aren't|isn't)\b", re.I)

TESTS_PASS = [
    re.compile(r"\b(?:all\s+)?(?:the\s+)?(?:(\d+)\s+)?(?:\w+\s+)?(?:unit\s+|integration\s+|e2e\s+)?tests?(?:\s+suite)?\s+(?:now\s+|still\s+|all\s+|are\s+|is\s+)*(?:pass(?:es|ed|ing)?|succeed(?:s|ed)?|green|ok)\b", re.I),
    re.compile(r"\b(\d+)\s+(?:tests?\s+)?passed\b", re.I),
    re.compile(r"\b(\d+)\s*/\s*\1\s+tests?\b", re.I),
    re.compile(r"\ball\s+(\d+)\s+tests?\b.{0,20}\bpass", re.I),
    re.compile(r"\b(?:all\s+)?tests?\s+(?:are\s+)?(?:now\s+)?passing\b|\ball green\b|\bpassing tests?\b", re.I),
]
COUNT_RE = re.compile(r"\b(?:all\s+)?(\d+)\s+(?:\w+\s+)?(?:tests?\s+)?(?:pass(?:ed|ing|es)?)\b|\ball\s+(\d+)\s+tests?\b|\b(\d+)\s*/\s*\3\s+tests?\b", re.I)
FAILED_N = re.compile(r"\b([1-9]\d*)\s+(?:tests?\s+)?(?:fail(?:ed|ing|ures?)?|errors?)\b", re.I)
TESTS_RUN = re.compile(r"\b(?:ran|run|running|re-?ran|executed|executing)\b.{0,30}\btest|\btests?(?:\s+suite)?\s+(?:were|was|has been|have been)\s+(?:run|executed)", re.I)
TESTS_ADDED = re.compile(r"\b(?:added|wrote|written|created|adds|new)\b.{0,25}\btests?\b|\btests?\b.{0,10}\b(?:were|was)\s+added", re.I)
BUILD_OK = re.compile(r"\bbuild(?:s)?\b.{0,25}\b(?:succeeds|succeeded|successful(?:ly)?|passes|passed|is green|works|clean(?:ly)?|ok)\b|\b(?:builds|compiles|compiled|built)\s+(?:successfully|cleanly|fine|without (?:errors|warnings))", re.I)

VERBS = [
    ("deleted", re.compile(r"\b(deleted|deleting|removed|removing|deletes|removes|delete|remove|dropped)\b", re.I)),
    ("created", re.compile(r"\b(created|creating|creates|added|adding|adds|new file|wrote|written|introduced?)\b", re.I)),
    ("modified", re.compile(r"\b(modified|modifying|updated|updating|updates|changed|changes|changing|edited|editing|fixed|fixes|refactored|tweaked|adjusted|renamed|rewrote|rewritten|patched|touched|bumped)\b", re.I)),
]

PATH_RE = re.compile(r"(?<![\w/:.@-])((?:\.{0,2}/)?(?:[\w@.+-]+/)*[\w@+-][\w@.+-]*\.[A-Za-z][A-Za-z0-9]{0,7}|(?:[\w@.+-]+/)+[\w@.+-]+/?)(?![\w/])")
NOT_PATH = re.compile(r"^(e\.g|i\.e|etc|vs|v?\d+(\.\d+)+\w*|[\w-]+\.(com|org|io|net|dev))$", re.I)

KNOWN_CMDS = set("""npm npx yarn pnpm bun node deno python python3 pip pip3 pytest py.test go cargo rustc make cmake git mvn
mvnw gradle gradlew dotnet bundle rspec rake ruby php composer phpunit jest vitest mocha tsc eslint prettier ruff
black mypy flake8 pylint uv poetry tox nox docker kubectl bash sh zsh rm mv cp ls cat sed grep rg find curl
java javac swift xcodebuild terraform ansible helm sqlite3 psql echo touch mkdir chmod tar unzip""".split())
BACKTICK = re.compile(r"`([^`\n]+)`")
CMD_NEG = re.compile(r"\b(didn't|did not|couldn't|could not|unable to|not able to|haven't|have not|should|you can|please|to run|recommend)\b", re.I)


def find_paths(text):
    out = []
    for m in PATH_RE.finditer(text):
        p = m.group(1).rstrip(".,;:")
        if "://" in text[max(0, m.start() - 8):m.start() + 3] or NOT_PATH.match(p):
            continue
        if p.startswith("./"):
            p = p[2:]
        out.append((m.start(), p))
    return out


def looks_like_command(s):
    s = s.strip()
    if s.startswith("$ "):
        s = s[2:]
    toks = s.split()
    if not toks:
        return None
    first = toks[0]
    if re.match(r"^[A-Z_][A-Z0-9_]*=", first) and len(toks) > 1:
        first = toks[1]
    if first.startswith("./") and len(toks) > 1 or first.startswith("./") and not re.search(r"\.\w{1,6}$", first):
        return s
    if first.rsplit("/", 1)[-1] in KNOWN_CMDS and (len(toks) > 1 or first in ("pytest", "make", "jest", "vitest", "mocha", "rspec", "tsc", "ls")):
        return s
    return None


def _units(text):
    """Split into lines, then sentences, tracking heading-verb context for bullet lists."""
    heading_verb = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            heading_verb = None
            continue
        is_bullet = bool(re.match(r"^([-*+•]|\d+[.)])\s+", line))
        body = re.sub(r"^([-*+•]|\d+[.)])\s+|^#+\s*", "", line)
        if not is_bullet and not line.startswith("#"):
            heading_verb = None
        ctx = heading_verb if is_bullet else None
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z`])", body):
            yield sent, ctx
        if body.rstrip().endswith(":") or line.startswith("#"):
            hv = None
            for kind, rx in VERBS:
                if rx.search(body):
                    hv = kind
                    break
            heading_verb = hv


def extract(text):
    claims = []

    def add(kind, sent, **kw):
        c = {"id": "c%d" % (len(claims) + 1), "kind": kind, "text": sent.strip()[:300]}
        c.update(kw)
        claims.append(c)

    for sent, ctx in _units(text):
        # tests pass
        pass_m = None
        for rx in TESTS_PASS:
            m = rx.search(sent)
            if m:
                pass_m = m
                break
        if pass_m:
            before = sent[max(0, pass_m.start() - 25):pass_m.end()]
            if not NEG.search(before) and not FAILED_N.search(sent) and not re.search(r"\bfail(s|ed|ing)?\b(?!.*\bnow\b)", sent[pass_m.end():pass_m.end() + 15], re.I):
                cm = COUNT_RE.search(sent)
                count = None
                if cm:
                    count = int(next(g for g in cm.groups() if g))
                add("tests_pass", sent, count=count)
        if TESTS_RUN.search(sent) and not NEG.search(sent):
            add("tests_run", sent)
        if TESTS_ADDED.search(sent) and not NEG.search(sent):
            add("tests_added", sent)
        if BUILD_OK.search(sent) and not NEG.search(sent):
            add("build_ok", sent)
        # files
        verbs = []
        for kind, rx in VERBS:
            for m in rx.finditer(sent):
                verbs.append((m.start(), kind))
        verbs.sort()
        bt_spans = [(m.start(), m.end(), m.group(1)) for m in BACKTICK.finditer(sent)]
        cmd_spans = [(a, b) for a, b, s in bt_spans if looks_like_command(s)]
        for pos, path in find_paths(sent):
            if any(a <= pos < b for a, b in cmd_spans):
                continue
            prior = [k for p, k in verbs if p < pos]
            later = [k for p, k in verbs if p > pos]
            change = prior[-1] if prior else (later[0] if later else ctx)
            if change and not NEG.search(sent):
                add("file", sent, path=path, change=change)
        # commands
        for a, b, s in bt_spans:
            cmd = looks_like_command(s)
            if cmd and not CMD_NEG.search(sent[:a]):
                add("command", sent, command=cmd)
    # code-block "$ cmd" lines
    for m in re.finditer(r"^\s*\$ (.+)$", text, re.M):
        cmd = looks_like_command(m.group(1))
        if cmd and not any(c.get("command") == cmd for c in claims):
            add("command", m.group(0).strip(), command=cmd)
    return _dedupe(claims)


def _dedupe(claims):
    seen, out = set(), []
    for c in claims:
        key = (c["kind"], c.get("path"), c.get("change"), c.get("command"), c.get("count") if c["kind"] == "tests_pass" else None,
               c["text"] if c["kind"] not in ("file", "command") else None)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    for i, c in enumerate(out):
        c["id"] = "c%d" % (i + 1)
    return out


def mentioned(text, path, changed_paths):
    """A file is mentioned if its relative path appears, or its basename appears and is unique among changed files."""
    if not text:
        return False
    if re.search(r"(?<![\w.-])" + re.escape(path) + r"(?![\w-])", text):
        return True
    base = path.rsplit("/", 1)[-1]
    if sum(1 for p in changed_paths if p.rsplit("/", 1)[-1] == base) != 1:
        return False
    return bool(re.search(r"(?<![\w.-])" + re.escape(base) + r"(?![\w-])", text))
