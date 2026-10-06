"""Compatibility import; implementation lives in cs2career.services.activities."""
import sys
from cs2career.services import activities as _implementation

sys.modules[__name__] = _implementation
