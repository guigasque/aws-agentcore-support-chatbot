"""Shared pytest setup: make the starter scripts importable.

The starter scripts live in project/starter/ and are run from there, so they
import each other as top-level modules (e.g. multiturn_bug_test imports chat).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

STARTER_DIR = Path(__file__).resolve().parent.parent / "starter"

if str(STARTER_DIR) not in sys.path:
    sys.path.insert(0, str(STARTER_DIR))


def load_module(name, filename):
    """Import a starter file by path.

    Needed for files whose names are not valid module names, such as
    generate-eval-dataset.py.
    """
    path = STARTER_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def starter_dir():
    return STARTER_DIR
