from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from housing_review.schemas.analyst import AnalystAssessment
from housing_review.schemas.common import STRICT_CONFIG, AnalystName, NonEmptyStr, Typology, coerce_agent

ROUND1 = "1"
AGENT_ORDER: tuple[AnalystName, ...] = (
    AnalystName.zoning_analyst,
    AnalystName.demographic_analyst,
    AnalystName.pro_forma_analyst,
    AnalystName.equity_analyst,
    AnalystName.sustainability_analyst,
)


class Round1Transcript(BaseModel):
    """Independent Round 1 outputs. Agents must not see each other's assessments."""

    model_config = STRICT_CONFIG

    site_id: NonEmptyStr
    round: str = ROUND1
    independent: bool = True
    agents_in_order: list[AnalystName]
    assessments: list[AnalystAssessment]
    notes: list[str] = Field(default_factory=list)

    @field_validator("agents_in_order", mode="before")
    @classmethod
    def _agents(cls, value: object) -> list[AnalystName]:
        if not isinstance(value, list):
            raise TypeError("agents_in_order must be a list")
        return [coerce_agent(item) if not isinstance(item, AnalystName) else item for item in value]

    def by_agent(self) -> dict[AnalystName, list[AnalystAssessment]]:
        grouped: dict[AnalystName, list[AnalystAssessment]] = {name: [] for name in self.agents_in_order}
        for item in self.assessments:
            grouped.setdefault(item.agent, []).append(item)
        return grouped

    def typologies(self) -> list[Typology]:
        seen: list[Typology] = []
        for item in self.assessments:
            if item.typology not in seen:
                seen.append(item.typology)
        return seen
