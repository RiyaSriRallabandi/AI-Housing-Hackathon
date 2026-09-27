from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import ConfigDict, Field


class AnalystName(str, Enum):
    zoning_analyst = "zoning_analyst"
    demographic_analyst = "demographic_analyst"
    pro_forma_analyst = "pro_forma_analyst"
    equity_analyst = "equity_analyst"
    sustainability_analyst = "sustainability_analyst"


class Typology(str, Enum):
    duplex = "duplex"
    apartment = "apartment"
    townhome = "townhome"
    adu = "adu"
    senior_housing = "senior_housing"
    detached_single_family = "detached_single_family"


class ConfidenceBasis(str, Enum):
    measured = "measured"
    trend_inferred = "trend_inferred"
    estimated = "estimated"


STRICT_CONFIG = ConfigDict(extra="forbid", str_strip_whitespace=True)

Score = Annotated[int, Field(ge=0, le=10)]
NonEmptyStr = Annotated[str, Field(min_length=1)]

_AGENT_ALIASES: dict[str, AnalystName] = {
    "zoning_analyst": AnalystName.zoning_analyst,
    "zoning analyst": AnalystName.zoning_analyst,
    "zoning": AnalystName.zoning_analyst,
    "demographic_analyst": AnalystName.demographic_analyst,
    "demographic analyst": AnalystName.demographic_analyst,
    "demographic": AnalystName.demographic_analyst,
    "pro_forma_analyst": AnalystName.pro_forma_analyst,
    "pro forma analyst": AnalystName.pro_forma_analyst,
    "pro forma": AnalystName.pro_forma_analyst,
    "proforma_analyst": AnalystName.pro_forma_analyst,
    "proforma": AnalystName.pro_forma_analyst,
    "equity_analyst": AnalystName.equity_analyst,
    "equity analyst": AnalystName.equity_analyst,
    "equity": AnalystName.equity_analyst,
    "sustainability_analyst": AnalystName.sustainability_analyst,
    "sustainability analyst": AnalystName.sustainability_analyst,
    "sustainability": AnalystName.sustainability_analyst,
}

_TYPOLOGY_ALIASES: dict[str, Typology] = {
    "duplex": Typology.duplex,
    "apartment": Typology.apartment,
    "apartments": Typology.apartment,
    "townhome": Typology.townhome,
    "townhomes": Typology.townhome,
    "townhouse": Typology.townhome,
    "townhouses": Typology.townhome,
    "adu": Typology.adu,
    "accessory dwelling unit": Typology.adu,
    "senior_housing": Typology.senior_housing,
    "senior housing": Typology.senior_housing,
    "detached_single_family": Typology.detached_single_family,
    "detached single family": Typology.detached_single_family,
    "single-family": Typology.detached_single_family,
    "single family": Typology.detached_single_family,
}


def coerce_agent(value: AnalystName | str) -> AnalystName:
    if isinstance(value, AnalystName):
        return value
    key = " ".join(value.strip().lower().replace("-", " ").replace("_", " ").split())
    underscored = key.replace(" ", "_")
    if underscored in _AGENT_ALIASES:
        return _AGENT_ALIASES[underscored]
    if key in _AGENT_ALIASES:
        return _AGENT_ALIASES[key]
    raise ValueError(f"Unknown analyst name: {value!r}")


def coerce_typology(value: Typology | str) -> Typology:
    if isinstance(value, Typology):
        return value
    key = " ".join(value.strip().lower().replace("-", " ").replace("_", " ").split())
    underscored = key.replace(" ", "_")
    if underscored in _TYPOLOGY_ALIASES:
        return _TYPOLOGY_ALIASES[underscored]
    if key in _TYPOLOGY_ALIASES:
        return _TYPOLOGY_ALIASES[key]
    raise ValueError(f"Unknown typology: {value!r}")
