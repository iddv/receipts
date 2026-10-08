import fnmatch
import os


def load_tests(loader, standard_tests, pattern):
    """Discover only this directory's own test modules.

    Subdirectories such as tests/acceptance/ are pytest suites with their own
    helpers; run them with `python -m pytest tests/acceptance`.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for name in sorted(os.listdir(here)):
        if name.endswith(".py") and fnmatch.fnmatch(name, pattern or "test*.py"):
            standard_tests.addTests(loader.loadTestsFromName(__name__ + "." + name[:-3]))
    return standard_tests
