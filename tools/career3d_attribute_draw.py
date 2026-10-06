"""Compatibility import; implementation lives in cs2career.services.attribute_draw."""
import sys
from cs2career.services import attribute_draw as _implementation

sys.modules[__name__] = _implementation
