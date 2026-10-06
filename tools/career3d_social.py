"""Compatibility import; implementation lives in cs2career.services.social."""
import sys
from cs2career.services import social as _implementation

sys.modules[__name__] = _implementation
