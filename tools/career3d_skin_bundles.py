"""Compatibility import; implementation lives in cs2career.services.skin_bundles."""
import sys
from cs2career.services import skin_bundles as _implementation

sys.modules[__name__] = _implementation
