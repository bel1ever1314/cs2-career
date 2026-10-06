"""Compatibility import; implementation lives in cs2career.services.match_recovery."""
import sys
from cs2career.services import match_recovery as _implementation

sys.modules[__name__] = _implementation
