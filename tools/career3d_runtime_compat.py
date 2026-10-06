"""Compatibility import; implementation lives in cs2career.cs2.runtime_compat."""
import sys
from cs2career.cs2 import runtime_compat as _implementation

sys.modules[__name__] = _implementation
