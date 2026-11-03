"""Non-blocking official source URL reachability audit.

No numerical GPP clause is confirmed by HTTP status alone.
Never download/copy/re-distribute official iPlan GIS layers.
"""
from __future__ import annotations
import json
import urllib.parse
from datetime import datetime,timezone
from pathlib import Path

import httpx
from app.policy_registry import catalog

OUTPUT=Path("official_source_reachability.json")
ALLOW_HOSTS={
    "planmalaysia.gov.my","www.planmalaysia.gov.my",
    "mytownnet.planmalaysia.gov.my","planmalaysia.perak.gov.my",
    "lphp.gov.my","www.lphp.gov.my",
}
def allowed(url):
    host=(urllib.parse.urlparse(url).hostname or "").lower()
    return host in ALLOW_HOSTS

def test():
    result={
      "checked_at_utc":datetime.now(timezone.utc).isoformat(),
      "description":"URL availability only: NOT numeric clause re-verification or land-zone permission.",
      "sources":[],
    }
    with httpx.Client(timeout=12.0,follow_redirects=False) as client:
        for src in catalog()["sources"]:
            url=src["url"]
            record={"id":src["id"],"title":src["title"],"url":url,
                    "curation":src["status"],"numeric_rules_rechecked":False}
            if not allowed(url):
                record.update({"status":"disallowed_host"})
                result["sources"].append(record)
                continue
            try:
                response=client.head(url)
                record.update({"status_code":response.status_code,
                               "content_type":response.headers.get("content-type"),
                               "redirect_location":response.headers.get("location") if 300<=response.status_code<400 else None,
                               "status":"responding" if 200<=response.status_code<400 else "blocked_or_unavailable"})
            except httpx.HTTPError as exc:
                record.update({"status":"unavailable","error_type":type(exc).__name__})
            result["sources"].append(record)
    result["summary"]={
        "responding":sum(x["status"]=="responding" for x in result["sources"]),
        "unavailable_or_blocked":sum(x["status"]!="responding" for x in result["sources"]),
        "numeric_rules_verified_by_this_probe":0,
    }
    OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result["summary"],indent=2))
    if result["summary"]["unavailable_or_blocked"]:
        raise SystemExit(1)
if __name__=="__main__":test()
