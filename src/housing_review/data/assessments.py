from __future__ import annotations

import json
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict

ASSESSMENTS_DATASET = "https://data.wprdc.org/dataset/property-assessments"
ASSESSMENTS_RESOURCE_ID = "65855e14-549e-4992-b5be-d629afc676fa"
ASSESSMENTS_API = "https://data.wprdc.org/api/3/action/datastore_search"
ASSESSMENTS_ETL_NOTE = "API version resource; last_etl_update 2026-09-07 on WPRDC metadata."

KEEP_FIELDS = (
    "PARID",
    "PROPERTYHOUSENUM",
    "PROPERTYADDRESS",
    "PROPERTYCITY",
    "PROPERTYZIP",
    "MUNICODE",
    "MUNIDESC",
    "NEIGHCODE",
    "CLASSDESC",
    "USECODE",
    "USEDESC",
    "STYLEDESC",
    "LOTAREA",
    "FAIRMARKETLAND",
    "FAIRMARKETBUILDING",
    "FAIRMARKETTOTAL",
    "SALEDATE",
    "SALEPRICE",
    "SALECODE",
    "SALEDESC",
    "YEARBLT",
    "STORIES",
    "BEDROOMS",
    "FULLBATHS",
    "FINISHEDLIVINGAREA",
    "GRADE",
    "CONDITION",
    "CDU",
    "OWNERDESC",
    "HOMESTEADFLAG",
)


class AssessmentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parid: str
    fields: dict
    source_url: str
    retrieved_on: str
    caveat: str


class AssessmentNotFound(LookupError):
    pass


def fetch_assessment(parid: str, *, timeout: int = 60, retrieved_on: str = "2026-09-26") -> AssessmentRecord:
    params = {
        "resource_id": ASSESSMENTS_RESOURCE_ID,
        "filters": json.dumps({"PARID": parid}),
        "limit": 1,
    }
    url = ASSESSMENTS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    records = (payload.get("result") or {}).get("records") or []
    if not records:
        raise AssessmentNotFound(f"No assessment row for PARID={parid!r}")
    raw = records[0]
    fields = {key: raw.get(key) for key in KEEP_FIELDS}
    return AssessmentRecord(
        parid=str(fields["PARID"]),
        fields=fields,
        source_url=url.split("?")[0] + f"?resource_id={ASSESSMENTS_RESOURCE_ID}",
        retrieved_on=retrieved_on,
        caveat=(
            "Assessed value is not market value — do not conflate the two. "
            f"{ASSESSMENTS_ETL_NOTE} USEDESC is an assessment class, not a Title 9 use."
        ),
    )
