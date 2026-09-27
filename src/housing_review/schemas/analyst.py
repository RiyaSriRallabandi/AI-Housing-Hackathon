from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from housing_review.schemas.common import (
    STRICT_CONFIG,
    AnalystName,
    ConfidenceBasis,
    NonEmptyStr,
    Score,
    Typology,
    coerce_agent,
    coerce_typology,
)


class Claim(BaseModel):
    """A single evidence-backed statement. No claim without a checkable source."""

    model_config = STRICT_CONFIG

    statement: NonEmptyStr
    basis: ConfidenceBasis
    source: NonEmptyStr
    confidence_note: str | None = None


class AnalystAssessment(BaseModel):
    """Shared Round 1 output every Analyst agent must return.

    Extra fields are rejected. `cannot_determine` is required even when empty.
    """

    model_config = STRICT_CONFIG

    agent: AnalystName
    site_id: NonEmptyStr
    typology: Typology
    score: Score
    basis: ConfidenceBasis
    claims: list[Claim]
    cannot_determine: list[str]
    summary: NonEmptyStr = Field(min_length=1)

    @field_validator("agent", mode="before")
    @classmethod
    def _agent(cls, value: object) -> AnalystName:
        if not isinstance(value, (AnalystName, str)):
            raise TypeError("agent must be a string")
        return coerce_agent(value)

    @field_validator("typology", mode="before")
    @classmethod
    def _typology(cls, value: object) -> Typology:
        if not isinstance(value, (Typology, str)):
            raise TypeError("typology must be a string")
        return coerce_typology(value)


class AnalystAssessmentRound2(AnalystAssessment):
    """Round 2 adds a required cross-examination note. Do not use for Round 1."""

    round_2_notes: NonEmptyStr
