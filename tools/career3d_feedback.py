"""Compatibility import; implementation lives in cs2career.services.feedback."""
import sys
from cs2career.services import feedback as _implementation

sys.modules[__name__] = _implementation
