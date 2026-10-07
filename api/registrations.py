"""Vercel Function for /api/registrations. All logic lives in bb_core.py at the project root."""
import os
import sys

_root = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(_root, "bb_core.py")) and os.path.dirname(_root) != _root:
    _root = os.path.dirname(_root)
if _root not in sys.path:
    sys.path.insert(0, _root)

from bb_core import ApiHandler  # noqa: E402


class handler(ApiHandler):
    route = "registrations"
