"""Competition format shared with RTS resources and the CS2 launch adapter.

Only scores/rules live here; simulation, RTS and CS2 keep their own execution.
Historical reports are never rewritten when these rules change.
"""
from dataclasses import dataclass
import json

from ..paths import data_file


@dataclass(frozen=True)
class MatchRules:
    id: str
    regulation_half: int
    overtime_half: int
    overtime_money: int

    def decided(self, a: int, b: int, *, overtime: bool = True) -> bool:
        rounds = a + b
        regulation = self.regulation_half * 2
        if rounds <= regulation:
            return max(a, b) > self.regulation_half or (rounds == regulation and not overtime)
        if not overtime:
            return True
        block = (rounds - regulation - 1) // (2 * self.overtime_half)
        target = self.regulation_half + (block + 1) * self.overtime_half + 1
        return max(a, b) >= target

    def final_score(self, a: int, b: int) -> bool:
        if type(a) is not int or type(b) is not int or min(a, b) < 0 or a == b:
            return False
        winner, loser = max(a, b), min(a, b)
        if winner == self.regulation_half + 1 and loser < self.regulation_half:
            return True
        offset = winner - self.regulation_half - 1
        if offset < self.overtime_half or offset % self.overtime_half:
            return False
        base = winner - self.overtime_half - 1
        return base <= loser <= winner - 2

    def cs2_commands(self) -> list[str]:
        return [f'mp_maxrounds {self.regulation_half * 2}', 'mp_overtime_enable 1',
                f'mp_overtime_maxrounds {self.overtime_half * 2}',
                f'mp_overtime_startmoney {self.overtime_money}', 'mp_match_can_clinch 1']


def load_rules() -> MatchRules:
    value = json.loads(data_file('match_rules.json').read_text('utf-8'))
    return MatchRules(**{name: value[name] for name in MatchRules.__dataclass_fields__})


COMPETITIVE = load_rules()
