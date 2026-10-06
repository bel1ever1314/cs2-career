"""Small handler-only double; persistence is covered by real-state tests.

Old HTTP unit tests deliberately provide no Season/Career implementation.
They implement the new operation/reconciliation protocol without pretending to
exercise a disk transaction. Integration tests must use ApplicationState.
"""
from contextlib import nullcontext
from types import SimpleNamespace


class ApplicationDouble(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if hasattr(self, 'career') and not hasattr(self.career, 'incident_state'):
            self.career.incident_state = {}

    def operation(self):
        return nullcontext()

    def settle(self):
        return self.persist()
