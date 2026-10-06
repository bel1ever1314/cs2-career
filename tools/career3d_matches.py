"""Compatibility import; implementation lives in cs2career.services.matches."""
import sys
from cs2career.services import matches as _implementation

sys.modules[__name__] = _implementation
