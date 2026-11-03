"""Operator-only weekly Geofabrik ZIP download and atomic PostGIS refresh.

Not an API endpoint: never download 500MB when a planner clicks a button.
The public extract's HTTP Last-Modified is an *archive publication time*;
actual OSM feature freshness may differ. No source data is stored in Git.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

import httpx

from .osm_import import import_snapshot
from .postgis_context import readiness

GEOFABRIK_ZIP=(
    "https://download.geofabrik.de/asia/"
    "malaysia-singapore-brunei-latest-free.gpkg.zip"
)
MAX_ZIP_BYTES=1_500_000_000
MAX_UNCOMPRESSED_BYTES=9_000_000_000
MAX_MEMBER_FILES=80


def extract_verified(archive: Path, destination: Path)->list[Path]:
    destination.mkdir(parents=True,exist_ok=True)
    extracted=[]
    with zipfile.ZipFile(archive) as source:
        members=source.infolist()
        if not members or len(members)>MAX_MEMBER_FILES:
            raise ValueError("Unexpected Geofabrik ZIP member count.")
        if sum(m.file_size for m in members)>MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Uncompressed regional extract exceeds safe bound.")
        for member in members:
            if member.is_dir():continue
            # Reject ZIP slip, symlinks and unrelated scripts, and flatten
            # nested directory names into an isolated temporary folder.
            if member.flag_bits & 0x1:
                raise ValueError("Encrypted Geofabrik ZIP is not supported.")
            if ((member.external_attr>>16)&0o170000)==0o120000:
                raise ValueError("Geofabrik ZIP contains a symlink.")
            if Path(member.filename).is_absolute() or ".." in Path(member.filename).parts:
                raise ValueError("Unsafe archive member.")
            if not member.filename.lower().endswith(".gpkg"):
                continue
            filename=Path(member.filename).name
            if (destination/filename).exists():
                raise ValueError("Duplicate GeoPackage member name.")
            with source.open(member) as src, (destination/filename).open("wb") as dst:
                shutil.copyfileobj(src,dst,length=1024*1024)
            extracted.append(destination/filename)
    if not extracted:
        raise ValueError("Geofabrik ZIP contains no GeoPackage files.")
    return extracted


def update_from_geofabrik(*,workdir:Path,force:bool=False)->dict[str,object]:
    workdir=workdir.expanduser().resolve()
    workdir.mkdir(parents=True,exist_ok=True)
    # Space for one compressed archive and unpacked free GIS layers is needed.
    with tempfile.TemporaryDirectory(prefix="planexus-osm-",dir=workdir) as temporary:
        temp=Path(temporary)
        archive=temp/"source.gpkg.zip"
        headers={"User-Agent":"PLANEXUS-AI-operator-geodata-refresh/1.0"}
        size=0
        with httpx.stream("GET",GEOFABRIK_ZIP,headers=headers,
                          follow_redirects=False,
                          timeout=httpx.Timeout(120.0,connect=12.0)) as response:
            response.raise_for_status()
            if int(response.headers.get("content-length","0"))>MAX_ZIP_BYTES:
                raise ValueError("Published Geofabrik ZIP exceeds safe download size.")
            modified=response.headers.get("last-modified")
            if not modified:
                raise ValueError("Geofabrik response has no archive Last-Modified; cannot establish source date.")
            published=parsedate_to_datetime(modified)
            if published.tzinfo is None:
                published=published.replace(tzinfo=timezone.utc)
            published=published.astimezone(timezone.utc)
            if published>datetime.now(timezone.utc):
                raise ValueError("Archive publication time lies in the future.")
            prior=readiness()
            if (not force and prior.get("ready") and
                    prior.get("dataset_timestamp_utc") and
                    datetime.fromisoformat(str(prior["dataset_timestamp_utc"]))>=published):
                return {"status":"already_current",
                        "archive_published_at_utc":published.isoformat()}
            with archive.open("wb") as dst:
                for chunk in response.iter_bytes(chunk_size=1024*1024):
                    size+=len(chunk)
                    if size>MAX_ZIP_BYTES:
                        raise ValueError("Geofabrik ZIP exceeded download safety bound.")
                    dst.write(chunk)
        if size<100:
            raise ValueError("Unexpectedly short Geofabrik ZIP.")
        extracted=extract_verified(archive,temp/"extracted")
        imported=import_snapshot(temp/"extracted",published.isoformat())
        return {"status":"updated","imported_feature_count":imported,
                "archive_published_at_utc":published.isoformat(),
                "gpkg_layers":len(extracted),
                "note":"Date represents HTTP archive publication, not exact OSM edit cutoff."}


def main()->None:
    parser=argparse.ArgumentParser(description="Refresh private OSM PostGIS from regional open data.")
    parser.add_argument("--workdir",default="/osm-work",
                        help="Private temporary disk with enough space for regional archive")
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    print(update_from_geofabrik(workdir=Path(args.workdir),force=args.force))


if __name__=="__main__":
    main()
