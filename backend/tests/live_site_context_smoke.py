"""Non-blocking REAL public Overpass check, no synthetic fallback."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from app.site_context import fetch_context

# Public Meru Raya reference square, NOT a confidential/private user parcel.
SITE={"type":"Polygon","coordinates":[[
  [101.073,4.669],[101.076,4.669],[101.076,4.672],
  [101.073,4.672],[101.073,4.669]
]]}
OUTPUT=Path("source_osm_live_evidence.json")

def main():
    audit={
      "checked_at_utc":datetime.now(timezone.utc).isoformat(),
      "purpose":"public reference location, third-party source availability only",
      "source":"OpenStreetMap / Overpass community data",
      "field_verified":False,"official_pbt_data":False,
    }
    try:
        result=fetch_context(SITE,radius_m=700)
        audit.update({
           "status":"retrieved",
           "retrieval_timestamp":result["retrieved_at_utc"],
           "source_url":result["source_url"],
           "returned_feature_count":result["returned_feature_count"],
           "category_counts":result["counts"],
           "named_place_count":len(result["named_places"]),
           "licence":result["licence"],
           "warning":"Feature presence/absence is NOT an official infrastructure inventory.",
        })
    except Exception as exc:
        audit.update({"status":"unavailable_or_failed",
                      "error_type":type(exc).__name__,
                      "error":str(exc)[:400]})
    OUTPUT.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(audit,indent=2,ensure_ascii=False))
    if audit["status"]!="retrieved":
        raise SystemExit(1)

if __name__=="__main__":
    main()
