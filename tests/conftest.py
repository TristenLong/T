"""Shared pytest configuration: put GOD_HAND_CORE modules on sys.path."""
import os
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GOD_HAND_CORE"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)