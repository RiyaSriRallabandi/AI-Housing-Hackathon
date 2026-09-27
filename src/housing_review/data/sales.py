from __future__ import annotations

import json
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict

SALES_DATASET = "https://data.wprdc.org/dataset/real-estate-sales"
SALES_RESOURCE_ID = "5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1"
SALES_API = "https://data.wprdc.org/api/3/action/datastore_search"
VALID_SALE_CODE = "0"
VALID_SALE_DESC = "VALID SALE"


class SaleRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parid: str
    sale_date: str | None
    price: float | None
    sale_code: str | None
    sale_desc: str | None
    address: str | None
    zip_code: str | None
    munidesc: str | None
    likely_arms_length: bool


class SalesSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parcel_sales: list[SaleRecord]
    comparable_valid_sales: list[SaleRecord]
    comparable_filter: dict
    source_url: str
    retrieved_on: str
    caveat: str


def _row(item: dict) -> SaleRecord:
    code = str(item.get("SALECODE") or "")
    desc = item.get("SALEDESC")
    price = item.get("PRICE")
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_f = None
    zip_val = item.get("PROPERTYZIP")
    return SaleRecord(
        parid=str(item.get("PARID") or ""),
        sale_date=item.get("SALEDATE"),
        price=price_f,
        sale_code=code,
        sale_desc=desc,
        address=item.get("FULL_ADDRESS"),
        zip_code=str(zip_val) if zip_val is not None else None,
        munidesc=(item.get("MUNIDESC") or "").strip() or None,
        likely_arms_length=code == VALID_SALE_CODE and desc == VALID_SALE_DESC,
    )


def _search(filters: dict, *, limit: int, sort: str | None, timeout: int) -> dict:
    params: dict = {
        "resource_id": SALES_RESOURCE_ID,
        "filters": json.dumps(filters),
        "limit": limit,
    }
    if sort:
        params["sort"] = sort
    url = SALES_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_sales_slice(
    parid: str,
    *,
    zip_code: str | int,
    timeout: int = 60,
    retrieved_on: str = "2026-09-26",
    comparable_limit: int = 12,
) -> SalesSlice:
    parcel_payload = _search({"PARID": parid}, limit=20, sort="SALEDATE desc", timeout=timeout)
    parcel_sales = [_row(item) for item in (parcel_payload.get("result") or {}).get("records") or []]
    zip_int = int(str(zip_code).split(".")[0])
    comps_payload = _search(
        {"PROPERTYZIP": zip_int, "SALECODE": VALID_SALE_CODE},
        limit=comparable_limit,
        sort="SALEDATE desc",
        timeout=timeout,
    )
    comps = [_row(item) for item in (comps_payload.get("result") or {}).get("records") or []]
    return SalesSlice(
        parcel_sales=parcel_sales,
        comparable_valid_sales=comps,
        comparable_filter={
            "PROPERTYZIP": zip_int,
            "SALECODE": VALID_SALE_CODE,
            "SALEDESC": VALID_SALE_DESC,
            "sort": "SALEDATE desc",
            "limit": comparable_limit,
        },
        source_url=SALES_DATASET,
        retrieved_on=retrieved_on,
        caveat=(
            "Filter using sale-validation codes; many transfers are not arm's-length sales. "
            f"Only SALECODE={VALID_SALE_CODE} ({VALID_SALE_DESC}) is treated as a comparable. "
            "Quit-claim, sheriff, love-and-affection, and multi-parcel sales are excluded from comps."
        ),
    )
