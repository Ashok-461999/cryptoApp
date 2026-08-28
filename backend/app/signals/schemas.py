from dataclasses import dataclass, field
from typing import Any

T1_R = 2.0   # 1:2 R:R — ₹200 scalp win on ₹100 risk
T2_R = 2.5   # optional runner (~₹250)


@dataclass
class SetupResult:
    setup_name: str
    fired: bool
    direction: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    targets: list[float] = field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    sl_basis: str = "setup_structure"

    @property
    def risk_reward(self) -> float | None:
        if not self.entry or not self.stop_loss or not self.targets:
            return None
        risk = abs(self.entry - self.stop_loss)
        if risk <= 0:
            return None
        return abs(self.targets[0] - self.entry) / risk
