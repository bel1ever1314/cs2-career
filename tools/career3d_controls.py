"""Compatibility import; implementation lives in cs2career.services.controls."""
import sys
from cs2career.services import controls as _implementation

sys.modules[__name__] = _implementation
