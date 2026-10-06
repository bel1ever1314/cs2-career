"""Compatibility import; implementation lives in cs2career.services.environment."""
import sys
from cs2career.services import environment as _implementation

sys.modules[__name__] = _implementation
