"""Compatibility import; implementation lives in cs2career.services.game_environment."""
import sys
from cs2career.services import game_environment as _implementation

sys.modules[__name__] = _implementation
