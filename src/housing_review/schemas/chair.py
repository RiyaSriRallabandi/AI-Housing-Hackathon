from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from housing_review.schemas.common import (
    STRICT_CONFIG,
    AnalystName,
    NonEmptyStr,
    Score,
    Typology,
    coerce_agent,
    coerce_typology,
)

RESPONSIBLE_USE_NOTE = (
    "Decision support only — not legal, financial, or zoning advice. "
    "Verify findings with the relevant office before acting."
)


class FactualDispute(BaseModel):
    model_config = STRICT_CONFIG

    issue: NonEmptyStr
    agents_involved: list[AnalystName]
    resolution_needed: NonEmptyStr

    @field_validator("agents_involved", mode="before")
    @classmethod
    def _agents(cls, value: object) -> list[AnalystName]:
        if not isinstance(value, list):
            raise TypeError("agents_involved must be a list")
        return [coerce_agent(item) if not isinstance(item, AnalystName) else item for item in value]


class ValueDispute(BaseModel):
    model_config = STRICT_CONFIG

    issue: NonEmptyStr
    agents_involved: list[AnalystName]
    framing: NonEmptyStr

    @field_validator("agents_involved", mode="before")
    @classmethod
    def _agents(cls, value: object) -> list[AnalystName]:
        if not isinstance(value, list):
            raise TypeError("agents_involved must be a list")
        return [coerce_agent(item) if not isinstance(item, AnalystName) else item for item in value]


class Limitation(BaseModel):
    model_config = STRICT_CONFIG

    question: NonEmptyStr
    raised_by: AnalystName
    next_step: NonEmptyStr

    @field_validator("raised_by", mode="before")
    @classmethod
    def _raised_by(cls, value: object) -> AnalystName:
        if not isinstance(value, (AnalystName, str)):
            raise TypeError("raised_by must be a string")
        return coerce_agent(value)


class TypologyComparison(BaseModel):
    model_config = STRICT_CONFIG

    typology: Typology
    scores_by_agent: dict[AnalystName, Score]
    factual_disputes: list[FactualDispute]
    value_disputes: list[ValueDispute]

    @field_validator("typology", mode="before")
    @classmethod
    def _typology(cls, value: object) -> Typology:
        if not isinstance(value, (Typology, str)):
            raise TypeError("typology must be a string")
        return coerce_typology(value)

    @field_validator("scores_by_agent", mode="before")
    @classmethod
    def _scores(cls, value: object) -> dict[AnalystName, int]:
        if not isinstance(value, dict):
            raise TypeError("scores_by_agent must be an object")
        return {coerce_agent(key): score for key, score in value.items()}


class ChairSynthesis(BaseModel):
    """Chair output. The Chair must not invent claims, sources, or numbers."""

    model_config = STRICT_CONFIG

    site_id: NonEmptyStr
    typology_comparison: list[TypologyComparison]
    limitations: list[Limitation]
    responsible_use_note: NonEmptyStr = Field(default=RESPONSIBLE_USE_NOTE)
