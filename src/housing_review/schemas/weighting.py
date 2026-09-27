from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from housing_review.schemas.chair import FactualDispute, Limitation, ValueDispute
from housing_review.schemas.common import (
    STRICT_CONFIG,
    AnalystName,
    NonEmptyStr,
    Score,
    Typology,
    coerce_agent,
    coerce_typology,
)

ViewLabel = Literal["equal-weight view", "user-weighted view"]


class AgentContribution(BaseModel):
    """How much one agent's score added to this typology's weighted score."""

    model_config = STRICT_CONFIG

    agent: AnalystName
    score: Score
    weight: float = Field(ge=0.0)
    contribution: float = Field(ge=0.0)

    @field_validator("agent", mode="before")
    @classmethod
    def _agent(cls, value: object) -> AnalystName:
        if not isinstance(value, (AnalystName, str)):
            raise TypeError("agent must be a string")
        return coerce_agent(value)


class AgentGaps(BaseModel):
    model_config = STRICT_CONFIG

    agent: AnalystName
    cannot_determine: list[str]

    @field_validator("agent", mode="before")
    @classmethod
    def _agent(cls, value: object) -> AnalystName:
        if not isinstance(value, (AnalystName, str)):
            raise TypeError("agent must be a string")
        return coerce_agent(value)


class TypologyWeightedResult(BaseModel):
    """One typology in a human-weighted view."""

    model_config = STRICT_CONFIG

    typology: Typology
    weighted_score: float
    rank: int = Field(ge=1)
    contributions: list[AgentContribution]
    cannot_determine: list[AgentGaps]
    factual_disputes: list[FactualDispute]
    value_disputes: list[ValueDispute]

    @field_validator("typology", mode="before")
    @classmethod
    def _typology(cls, value: object) -> Typology:
        if not isinstance(value, (Typology, str)):
            raise TypeError("typology must be a string")
        return coerce_typology(value)


class WeightedView(BaseModel):
    """User-assigned weights over cached Round 1 scores. Not a preferred typology."""

    model_config = STRICT_CONFIG

    site_id: NonEmptyStr
    view_label: ViewLabel
    weights: dict[AnalystName, float]
    ranking: list[TypologyWeightedResult]
    precision_notes: list[str]
    limitations: list[Limitation]
    responsible_use_note: NonEmptyStr

    @field_validator("weights", mode="before")
    @classmethod
    def _weights(cls, value: object) -> dict[AnalystName, float]:
        if not isinstance(value, dict):
            raise TypeError("weights must be an object")
        return {coerce_agent(key): float(weight) for key, weight in value.items()}
