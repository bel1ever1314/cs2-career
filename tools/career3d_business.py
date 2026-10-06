"""Compatibility import; implementation lives in cs2career.services.business."""
import sys
from cs2career.services import business as _implementation

sys.modules[__name__] = _implementation
