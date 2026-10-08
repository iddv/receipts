"""Config file handling (~/.config/receipts/config.toml or $RECEIPTS_CONFIG)."""
import os
import tomllib

# key: (default, allowed values or type, description)
SETTINGS = {
    "capture.output": ("tail", ("tail", "none"), "Store command output tails, or only metadata (for sensitive repos)."),
    "capture.tail_lines": (200, int, "Max lines of output tail stored per command."),
    "capture.tail_bytes": (65536, int, "Max bytes of output tail stored per command."),
    "files.gitignored": ("exclude", ("exclude", "include"), "Whether gitignored files are part of snapshots."),
    "files.exclude": ([".git/", "node_modules/", ".venv/", "venv/", "__pycache__/", "target/", "dist/",
                       "build/", ".next/", ".aider*"], list,
                      "Snapshot exclusions. 'name/' excludes a directory at any depth; other entries are glob patterns on the file name."),
    "files.max_file_mb": (5, int, "Files larger than this are hashed, not diffed."),
    "files.max_files": (50000, int, "Workspace file limit; files beyond it are hashed only (no diff)."),
    "verify.rerun_tests": ("off", ("on", "off"), "Run the test command independently after the agent exits."),
    "verify.test_cmd": ("", str, "Default test command when --test-cmd is not given."),
    "report.unverified_tests": ("flag", ("flag", "ignore"), "Raise a high flag for 'tests pass' with no recorded test run."),
    "report.fail_on": ("high", ("high", "any"), "'report' exits 1 on open high flags only, or on any open flag."),
    "run.block_unclosed_same_dir": ("allowed", ("allowed", "refused"),
                                    "refused: a new recording is refused while an unclosed session exists for the directory; "
                                    "allowed: refused only while another recording of it is running."),
    "run.block_unclosed_same_dir_dirs": ([], list,
                                         "Per-directory values for run.block_unclosed_same_dir, as \"<dir>=allowed|refused\" entries."),
    "run.nested_dirs": ("refused", ("refused", "allowed"),
                        "refused: a recording is refused while an active recording covers a parent or child directory; "
                        "allowed: only the exact same directory is locked."),
    "list.since_timezone": ("local", ("local", "utc"),
                            "Time zone defining the calendar day of a --since <date> filter: local midnight or UTC midnight."),
    "lock.timeout_s": (5, int, "Seconds to wait for a busy session lock."),
    "notes.max_chars": (500, int, "Maximum length of an ack note."),
}


class ConfigError(Exception):
    pass


def config_path():
    return os.environ.get("RECEIPTS_CONFIG") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "receipts", "config.toml")


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(values):
    out = ["# Receipts configuration. Every key is listed with its default; edit or use",
           "# `receipts config set <key> <value>`.", ""]
    section = None
    for key, (default, allowed, desc) in SETTINGS.items():
        sec, name = key.split(".", 1)
        if sec != section:
            out.append("[%s]" % sec)
            section = sec
        allowed_s = " | ".join(allowed) if isinstance(allowed, tuple) else allowed.__name__
        out.append("# %s  (%s; default %s)" % (desc, allowed_s, _toml_value(default)))
        out.append("%s = %s" % (name, _toml_value(values.get(key, default))))
        out.append("")
    return "\n".join(out)


def validate(key, value):
    if key not in SETTINGS:
        raise ConfigError("unknown config key %r; expected one of: %s" % (key, ", ".join(SETTINGS)))
    default, allowed, _ = SETTINGS[key]
    if isinstance(allowed, tuple):
        if value not in allowed:
            raise ConfigError("invalid value %r for %s; expected one of: %s" % (value, key, ", ".join(allowed)))
        return value
    if allowed is int:
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ConfigError("invalid value %r for %s; expected a positive integer" % (value, key))
        if v <= 0:
            raise ConfigError("invalid value %r for %s; expected a positive integer" % (value, key))
        return v
    if allowed is list:
        if isinstance(value, str):
            value = [x.strip() for x in value.split(",") if x.strip()]
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ConfigError("invalid value for %s; expected a comma-separated list of patterns" % key)
        return value
    if not isinstance(value, str):
        raise ConfigError("invalid value %r for %s; expected a string" % (value, key))
    return value


# Environment variables that override a setting everywhere when set.
ENV_OVERRIDES = {
    "list.since_timezone": "LIST_SINCE_TIMEZONE",
    "run.nested_dirs": "RUN_NESTED_DIRS",
    "run.block_unclosed_same_dir": "RUN_BLOCK_UNCLOSED_SAME_DIR",
}


def load():
    values = {k: v[0] for k, v in SETTINGS.items()}
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError("config file %s is not valid TOML: %s" % (path, e))
        for sec, items in data.items():
            if not isinstance(items, dict):
                raise ConfigError("config file %s: %r must be a [section]" % (path, sec))
            for name, v in items.items():
                key = "%s.%s" % (sec, name)
                try:
                    values[key] = validate(key, v)
                except ConfigError as e:
                    raise ConfigError("config file %s: %s" % (path, e))
    for key, env in ENV_OVERRIDES.items():
        if os.environ.get(env):
            try:
                values[key] = validate(key, os.environ[env])
            except ConfigError as e:
                raise ConfigError("environment variable %s: %s" % (env, e))
    return values


def per_dir(values, key, cwd):
    """Value of ``key`` for directory ``cwd``: a matching ``<key>_dirs`` entry, else the global value.
    An environment override applies everywhere."""
    env = ENV_OVERRIDES.get(key)
    if env and os.environ.get(env):
        return values[key]
    cwd = os.path.realpath(cwd)
    for entry in values.get(key + "_dirs") or []:
        d, sep, v = entry.rpartition("=")
        if sep and os.path.realpath(os.path.expanduser(d)) == cwd:
            return validate(key, v)
    return values[key]


def write(values):
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(render(values))
    os.replace(tmp, path)
    return path


def set_value(key, raw):
    values = load()
    values[key] = validate(key, raw)
    write(values)
    return values[key]
