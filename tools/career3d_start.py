"""Compatibility import; implementation lives in cs2career.services.start."""
import sys
from cs2career.services import start as _implementation

sys.modules[__name__] = _implementation
