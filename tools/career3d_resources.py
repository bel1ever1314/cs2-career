"""Compatibility import; implementation lives in cs2career.services.resources."""
import sys
from cs2career.services import resources as _implementation

sys.modules[__name__] = _implementation
