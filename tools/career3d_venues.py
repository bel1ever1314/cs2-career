"""Compatibility import; implementation lives in cs2career.services.venues."""
import sys
from cs2career.services import venues as _implementation

sys.modules[__name__] = _implementation
