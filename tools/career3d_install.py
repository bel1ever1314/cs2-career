"""Compatibility import; implementation lives in cs2career.services.installation."""
import sys
from cs2career.services import installation as _implementation

sys.modules[__name__] = _implementation
