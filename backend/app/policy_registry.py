"""Curated, source-grounded PLANEXUS GPP policy registry (read-only, versioned).

This is NOT an indexed copy of all Malaysian planning policies. Only entries
manually checked against the stated official document/page are machine-readable.
Never infer a maximum where the source lists only a minimum, and never merge a
national reference with state/PBT regulations as a certified composite.
"""
from __future__ import annotations

import re
from typing import Any

REGISTRY_VERSION = "2026-11-02-gpp-housing-v5"

NATIONAL_SOURCE = {
    "id": "gp001a_2016",
    "title": "GP 001-A: Garis Panduan Perancangan Perumahan",
    "year": 2016,
    "issuer": "PLANMalaysia / Jabatan Perancangan Bandar dan Desa Semenanjung Malaysia",
    "jurisdiction": "Semenanjung Malaysia - national reference, subject to adoption and local plans",
    "url": "https://mytownnet.planmalaysia.gov.my/ver2/gp/GPP_PERUMAHAN.pdf",
    "alternate_official_url": "https://www.planmalaysia.gov.my/uploads/content-downloads/file_20251114202120.pdf",
    "evidence": "Bahagian C, 8.2.1, Jadual 2, printed pages 44-45",
    "scope": "Planning reference; do not infer that current PBT conditions are identical.",
    "status": "curated_rules",
}
PERAK_SOURCE = {
    "id": "perak_housing_2023",
    "title": "Garis Panduan Piawaian Perumahan Negeri Perak 2023",
    "year": 2023,
    "issuer": "PLANMalaysia Perak / Kerajaan Negeri Perak",
    "jurisdiction": "Negeri Perak; review applicable PBT and gazetted Rancangan Tempatan",
    "url": "https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file",
    "alternate_official_url": "https://planmalaysia.perak.gov.my/index.php/icon-media/muat-turun-borang/2-garis-panduan-perancangan?download=109%3Agaris-panduan-piawan-perumahan-negeri-perak-2023",
    "evidence": "PR1 p5 terrace, PR2 p7 semi-detached, PR3 p9 cluster, PR4 p11 detached, PR5 p13 zero lot, PR6 p15 townhouse; MMKN 5 September 2023",
    "scope": "State guidance; PR1-PR6 provide floor/height constraints; most do not list numerical lot frontage/depth minima. Road and setback dimensions are separate geometry references.",
    "status": "curated_rules",
}
CATALOG_ONLY = (
    {
        "id": "gpp_facilities_2022",
        "title": "GPP Kemudahan Masyarakat (Semakan Semula) 2022",
        "year": 2022,
        "issuer": "PLANMalaysia",
        "jurisdiction": "Malaysia - adoption and site-specific rules to verify",
        "url": "https://www.planmalaysia.gov.my/main/latest-news-details?id=999087c8-ffc9-11ef-bf69-fa163eda1aa9",
        "evidence": "Official publication notice (numeric requirements not entered)",
        "scope": "Source catalog only; no numeric facility ratios have been extracted.",
        "status": "catalog_only",
    },
    {
        "id": "gpp_parking_gp011a",
        "title": "GP011-A: GPP Tempat Letak Kenderaan",
        "year": None,
        "issuer": "PLANMalaysia",
        "jurisdiction": "Malaysia - local adoption and ratios to verify",
        "url": "https://www.planmalaysia.gov.my/main/garis-panduan-perancangan",
        "evidence": "PLANMalaysia official GPP document index",
        "scope": "Source catalog only; do not assert parking ratios.",
        "status": "catalog_only",
    },
    {
        "id": "gpp_hills_gp007a11",
        "title": "GP007-A(11): GPP Pembangunan Kawasan Bukit dan Tanah Tinggi",
        "year": None,
        "issuer": "PLANMalaysia",
        "jurisdiction": "Malaysia - local adoption and slopes to verify",
        "url": "https://www.planmalaysia.gov.my/main/garis-panduan-perancangan",
        "evidence": "PLANMalaysia official GPP document index",
        "scope": "Source catalog only; no statutory slope thresholds are encoded.",
        "status": "catalog_only",
    },
    {
        "id": "gpp_commercial_gp003a",
        "title": "GP003-A: GPP Kawasan Perdagangan (Addendum 2017)",
        "year": 2017,
        "issuer": "PLANMalaysia",
        "jurisdiction": "Malaysia - local adoption and lot standards to verify",
        "url": "https://www.planmalaysia.gov.my/main/garis-panduan-perancangan",
        "evidence": "PLANMalaysia official GPP document index",
        "scope": "Source catalog only; shoplot sizes are NOT configured.",
        "status": "catalog_only",
    },
)

# DESIGN STARTING POINTS - NOT A NEW GPP MINIMUM TABLE.
# Source categories do not align exactly with user-friendly Low/Mid/High labels:
# GP001-A lists low, lower-middle and middle terraces, NOT high-cost terrace.
# Perak PR1 specifies floor area, not frontage/depth. Product examples below
# must never be reported as legally required limits.
PRACTICAL_TERRACE_PRESETS: tuple[dict[str, Any], ...] = (
    {"id":"low","category":"terrace_low_cost","label":"Low cost — 20 × 55 kaki",
     "width_ft":20,"depth_ft":55,"storeys":1,"basis":"gpp001a_low_cost_1_storey",
     "status":"design_starting_point_not_approval",
     "source_url":NATIONAL_SOURCE["url"],"source_page":"GP001-A 2016 Jadual 2, ms. 44",
     "note":"20 × 55 ft ialah minimum rujukan kebangsaan untuk kos rendah 1 tingkat; Perak/PBT dan kategori rumah perlu disahkan."},
    {"id":"mid","category":"terrace_middle","label":"Mid cost — 20 × 70 kaki",
     "width_ft":20,"depth_ft":70,"storeys":1,"basis":"observed_mid_cost_project_example_not_national_gpp_min",
     "status":"design_starting_point_not_approval",
     "source_url":"https://hims.kpkt.gov.my/files/8502/8502-4/IKLAN_BROSUR_01.pdf",
     "source_page":"Brosur rumah teres kos sederhana 1 tingkat, 20 × 70 ft (contoh projek)",
     "note":"20 × 70 ft digunakan dalam contoh projek kos sederhana; GP001-A menyatakan MINIMUM 20 × 65 ft bagi 1 tingkat atau 18 × 65 ft bagi 2–3 tingkat. Ini pilihan reka bentuk, bukan wajib."},
    {"id":"high","category":"terrace_high","label":"High / Premium — 22 × 75 kaki (contoh)",
     "width_ft":22,"depth_ft":75,"storeys":2,"basis":"example_built_project_size_not_high_cost_gpp_class",
     "status":"design_starting_point_not_approval",
     "source_url":"https://www.kejora.gov.my/perkhidmatan/hartanah/projek-penswastaan-dan-pembangunan-bercampur-3/",
     "source_page":"Senarai komponen pembangunan Taman Desaru Utama: teres dua tingkat 22 × 75 ft",
     "note":"22 × 75 ft ialah contoh projek; GP001-A tidak memberikan satu baris minimum khusus rumah teres kos TINGGI. PBT/RT perlu disahkan."},
)


# Width/depth are explicit METRES as printed in Table 2, not approximate
# conversions of rounded imperial equivalents. None is NEVER zero or unlimited.
# Storey 1.5 is not represented in the product's integer floor input.
NATIONAL_LOT_RULES: tuple[dict[str, Any], ...] = (
    {"category":"terrace_low_cost", "storeys":[1], "min_width_ft":20, "min_depth_ft":55, "label":"Rumah teres kos rendah, 1 tingkat",
     "min_width_m":6.1, "min_depth_m":16.8, "min_floor_area_m2":65.0, "page":44},
    {"category":"terrace_low_cost", "storeys":[2], "min_width_ft":14, "min_depth_ft":55, "label":"Rumah teres kos rendah, 2 tingkat",
     "min_width_m":4.3, "min_depth_m":16.8, "min_floor_area_m2":None, "page":44},
    {"category":"terrace_lower_middle", "storeys":[1], "min_width_ft":20, "min_depth_ft":60, "label":"Rumah teres kos sederhana rendah, 1 tingkat",
     "min_width_m":6.1, "min_depth_m":18.3, "min_floor_area_m2":69.7, "page":44},
    {"category":"terrace_lower_middle", "storeys":[2], "min_width_ft":18, "min_depth_ft":55, "label":"Rumah teres kos sederhana rendah, 2 tingkat",
     "min_width_m":5.5, "min_depth_m":16.8, "min_floor_area_m2":None, "page":44},
    {"category":"terrace_middle", "storeys":[1], "min_width_ft":20, "min_depth_ft":65, "label":"Rumah teres kos sederhana, 1 tingkat",
     "min_width_m":6.1, "min_depth_m":19.8, "min_floor_area_m2":79.0, "page":44},
    {"category":"terrace_middle", "storeys":[2,3], "min_width_ft":18, "min_depth_ft":65, "label":"Rumah teres kos sederhana, 2-3 tingkat",
     "min_width_m":5.5, "min_depth_m":19.8, "min_floor_area_m2":None, "page":44},
    {"category":"cluster", "storeys":[1], "label":"Rumah kluster, 1 tingkat",
     "min_width_m":12.2, "min_depth_m":15.2, "min_floor_area_m2":83.6, "page":45},
    {"category":"cluster", "storeys":[2,3], "label":"Rumah kluster, 2-3 tingkat",
     "min_width_m":9.1, "min_depth_m":16.8, "min_floor_area_m2":None, "page":45},
    {"category":"semi_detached", "storeys":[1], "label":"Rumah berkembar, 1 tingkat",
     "min_width_m":12.2, "min_depth_m":19.8, "min_floor_area_m2":97.5, "page":45},
    {"category":"semi_detached", "storeys":[2,3], "label":"Rumah berkembar, 2–3 tingkat",
     "min_width_m":12.2, "min_depth_m":19.8, "min_floor_area_m2":None, "page":45},
    {"category":"detached", "storeys":[1], "label":"Rumah sesebuah biasa, 1 tingkat",
     "min_width_m":15.2, "min_depth_m":22.9, "min_floor_area_m2":125.4, "page":45},
    {"category":"detached", "storeys":[2,3], "label":"Rumah sesebuah biasa, 2–3 tingkat",
     "min_width_m":15.2, "min_depth_m":22.9, "min_floor_area_m2":None, "page":45},
    {"category":"zero_lot", "storeys":[1], "label":"Rumah sesebuah zero lot boundary, 1 tingkat",
     "min_width_m":13.7, "min_depth_m":21.3, "min_floor_area_m2":92.9, "page":45},
    {"category":"zero_lot", "storeys":[2,3], "label":"Rumah sesebuah zero lot boundary, 2–3 tingkat",
     "min_width_m":13.7, "min_depth_m":21.3, "min_floor_area_m2":None, "page":45},
)

PERAK_FLOOR_MIN_SQFT = {
    "perak_low_cost":900.0,
    "perak_middle":950.0,
    "perak_affordable":1000.0,
    "perak_open":1001.0,
}
# Perak PR1 p5 also lists layout geometry. These dimensions are shown as
# DOCUMENT REFERENCES only until road/lot/setback geometry can be measured.
# Never assume "stated" equals "minimum" or apply one price class to another.
PERAK_LAYOUT_REFERENCES: tuple[dict[str, Any], ...] = (
    {"id":"terrace_block_length", "label":"Panjang blok rumah teres", "value_ft":320,
     "value_type":"stated", "applicability":"PR1 terrace houses (all listed price classes)"},
    {"id":"service_road_width", "label":"Lebar jalan perkhidmatan", "value_ft":50,
     "value_type":"minimum", "applicability":"PR1 terrace houses (all listed price classes)"},
    {"id":"rear_lane_width", "label":"Lebar lorong belakang", "value_ft":15,
     "value_type":"stated", "applicability":"PR1 terrace houses"},
    {"id":"firebreak_side_lane", "label":"Lorong pemisah / lorong tepi (berturap)", "value_ft":20,
     "value_type":"stated", "applicability":"PR1 terrace houses"},
    {"id":"front_setback_low_cost", "label":"Anjakan hadapan (kos rendah)", "value_ft":15,
     "value_type":"stated", "applicability":"PR1 terrace kos rendah only"},
    {"id":"front_setback_other", "label":"Anjakan hadapan (kos sederhana/mampu milik/bebas)", "value_ft":20,
     "value_type":"stated", "applicability":"PR1 terrace other than low-cost"},
    {"id":"corner_lot_side_setback", "label":"Anjakan tepi lot sudut (corner lot)", "value_ft":20,
     "value_type":"stated", "applicability":"PR1 terrace corner lots"},
    {"id":"end_lot_setback", "label":"Anjakan sisi (end lot)", "value_ft":5,
     "value_type":"stated", "applicability":"PR1 terrace end lots"},
    {"id":"cul_de_sac_max_other", "label":"Panjang maks jalan buntu (bukan kos rendah)", "value_ft":320,
     "value_type":"maximum", "applicability":"PR1 terrace kos sederhana/mampu milik/bebas; table says TB for low cost"},
    {"id":"cul_de_sac_head", "label":"Dimensi hujung jalan buntu (bukan kos rendah)", "value_ft":50,
     "value_type":"stated_square", "applicability":"PR1 50 ft x 50 ft turning end, not a width/depth of a house"},
)

# Verified PR2-PR6 printed tables, sourced to the original state PDF.
# Perak states minimum FLOOR SPACE, NOT minimum plot frontage/depth.
PERAK_OTHER_HOUSING = {
    "semi_detached":{"code":"PR2","page":7,"min_floor_sqft":1000.0,
                     "max_storeys":3,"min_bedrooms":3,"max_height_ft":60.0},
    "cluster":{"code":"PR3","page":9,"min_floor_sqft":1000.0,
               "max_storeys":3,"min_bedrooms":3,"max_height_ft":60.0,
               "notes":"4 units per cluster (configuration not automatically checked)."},
    "detached":{"code":"PR4","page":11,"min_floor_sqft":1000.0,
                "max_storeys":3,"min_bedrooms":3,"max_height_ft":60.0},
    "zero_lot":{"code":"PR5","page":13,"min_floor_sqft":1000.0,
                "max_storeys":3,"min_bedrooms":3,"max_height_ft":60.0},
    "townhouse":{"code":"PR6","page":15,"min_floor_sqft":900.0,
                 "max_storeys":3,"min_bedrooms":3,"max_height_ft":60.0,
                 "notes":"2 owners per single lot, arrangement and strata conditions require separate review."},
}

PERAK_SEGMENT_LABELS = {
    "perak_low_cost":"Kos rendah / Rumah Perakku I",
    "perak_middle":"Kos sederhana / Rumah Perakku II",
    "perak_affordable":"Mampu milik / Rumah Perakku III",
    "perak_open":"Harga bebas / terbuka",
}


def catalog() -> dict[str, Any]:
    return {
        "registry_version": REGISTRY_VERSION,
        "sources": [NATIONAL_SOURCE, PERAK_SOURCE, *CATALOG_ONLY],
        "profiles": [
            {"id":"none","label":"Belum pilih negeri / GPP","details":"Do not claim a policy check without jurisdiction."},
            {"id":"national_2016","label":"GP001-A Perumahan 2016 - rujukan kebangsaan",
             "details":"Printed pages 44-45; subject to current state/PBT adoption."},
            {"id":"perak_2023","label":"Perak 2023 + GPP kebangsaan (rujukan sampingan)",
             "details":"Perak floor area/storey limits. National lot dimensions are reference-only until local adoption is verified."},
        ],
        "housing_categories":[
            {"id":"terrace_low_cost","label":"Rumah teres kos rendah","development_type":"terrace_housing"},
            {"id":"terrace_lower_middle","label":"Rumah teres kos sederhana rendah","development_type":"terrace_housing"},
            {"id":"terrace_middle","label":"Rumah teres kos sederhana (Mid)","development_type":"terrace_housing"},
            {"id":"terrace_high","label":"Rumah teres kos tinggi (High; minimum nasional tiada)","development_type":"terrace_housing"},
            {"id":"cluster","label":"Rumah kluster","development_type":"other_landed"},
            {"id":"semi_detached","label":"Rumah berkembar","development_type":"other_landed"},
            {"id":"detached","label":"Rumah sesebuah","development_type":"other_landed"},
            {"id":"zero_lot","label":"Rumah sesebuah (zero lot boundary)","development_type":"other_landed"},
            {"id":"townhouse","label":"Rumah bandar (Perak PR6; GP001 lot size not indexed)","development_type":"other_landed"},
        ],
        "terrace_design_presets": [{**preset, "width_m":round(preset["width_ft"]*0.3048,4),
             "depth_m":round(preset["depth_ft"]*0.3048,4)} for preset in PRACTICAL_TERRACE_PRESETS],
        "national_lot_rules": [
            {**r,"source_id":NATIONAL_SOURCE["id"],
             "url":NATIONAL_SOURCE["url"],"max_width_m":None,"max_depth_m":None}
            for r in NATIONAL_LOT_RULES
        ],
        "perak_floor_min_sqft": PERAK_FLOOR_MIN_SQFT,
        "perak_other_housing_rules": {key:{**rule,"source_id":PERAK_SOURCE["id"],
            "source_url":PERAK_SOURCE["url"],"source_page":"PR"+rule["code"][2:]+" halaman "+str(rule["page"])}
            for key,rule in PERAK_OTHER_HOUSING.items()},
        "perak_layout_references": [{**r,"value_m":round(r["value_ft"]*0.3048,4),
            "source_id":PERAK_SOURCE["id"],"source_url":PERAK_SOURCE["url"],
            "source_page":"PR1, halaman bercetak 5","automated_geometry_check":False}
            for r in PERAK_LAYOUT_REFERENCES],
        "perak_market_segments": [{"id":key,"label":value} for key,value in PERAK_SEGMENT_LABELS.items()],
        "not_indexed": [item["id"] for item in CATALOG_ONLY],
        "disclaimer":"Only GP001-A (2016) housing lots and selected Perak (2023) housing clauses have machine-readable rules. Catalog entries are NOT all indexed. No GIS auto-jurisdiction, gazetted RT lookup or PBT certification.",
    }


def evaluate_policy(proposal: Any) -> dict[str, Any]:
    """Evidence-scoped numeric checks, never issuance of planning permission."""
    profile=getattr(proposal,"policy_profile","none")
    category=getattr(proposal,"housing_category",None)
    storeys=getattr(proposal,"storeys",None)
    segment=getattr(proposal,"perak_market_segment",None)
    floor_m2=getattr(proposal,"floor_area_m2",None)
    bedrooms=getattr(proposal,"bedrooms",None)
    building_height_m=getattr(proposal,"building_height_m",None)
    is_terrace=getattr(proposal,"development_type","")=="terrace_housing"
    is_landed=getattr(proposal,"development_type","") in ("terrace_housing","other_landed")
    checks:list[dict[str,Any]]=[]
    warnings=[
        "Pemeriksaan angka rujukan sahaja. Tiada status lulus KM, zoning RT, semakan PBT atau kelulusan pelan bangunan.",
        "Semak dokumen negeri/PBT terkini, garis panduan lokal, RT/RKK, rizab jalan, anjakan, penyediaan kemudahan, saliran serta lot sebenar.",
    ]
    label=next((p["label"] for p in catalog()["profiles"] if p["id"]==profile),"Unknown")
    def add_check(*,key:str,title:str,limit:float|int,observed:float|int|None,
                  measure:str,direction:str,source:dict[str,Any],page:str,role:str,
                  printed_equivalent_ft:float|None=None)->None:
        if observed is None:
            state="not_supplied"
        elif direction=="min":
            # National table prints e.g. 6.1 m (20 ft) and 5.5 m (18 ft),
            # where metric is rounded. Exact feet converted to metres must
            # NOT falsely fail against the rounded metric threshold.
            effective_limit=min(limit,printed_equivalent_ft*.3048) if (
                printed_equivalent_ft is not None and measure=="m"
            ) else limit
            state="meets_number" if observed+1e-8>=effective_limit else "below_min"
        else:
            state="meets_number" if observed<=limit+1e-8 else "above_max"
        checks.append({
            "key":key,"title":title,"type":direction,"value":float(limit),
            "observed":float(observed) if observed is not None else None,
            "unit":measure,"result":state,
            "published_equivalent_ft":printed_equivalent_ft,
            "source_id":source["id"],"source_title":source["title"],
            "source_url":source["url"],"source_page":page,
            "role":role,
            "binding":False,  # PBT adoption and current statutory policy are not verified.
        })

    if profile=="none":
        return {
            "registry_version":REGISTRY_VERSION,"profile_id":profile,"profile_label":label,
            "status":"not_selected","checks":[],"reference_only":True,
            "warnings":warnings,
            "max_lot_width_m":None,"max_lot_depth_m":None,
            "message":"Pilih bidang kuasa GPP dahulu. PLANEXUS tidak boleh andaikan syarat PBT daripada koordinat tapak.",
        }
    if not is_landed:
        return {
            "registry_version":REGISTRY_VERSION,"profile_id":profile,"profile_label":label,
            "status":"not_indexed","checks":[],"reference_only":True,
            "warnings":warnings+["Saiz lot rumah kedai belum diekstrak daripada GPP Perdagangan; tiada angka piawaian rumah digunakan untuk rumah kedai."],
            "max_lot_width_m":None,"max_lot_depth_m":None,
            "message":"GPP perdagangan masih dalam katalog sumber, bukan peraturan numerik yang disahkan.",
        }
    if category is None or storeys is None:
        warnings.append("Jenis perumahan terperinci dan bilangan tingkat diperlukan sebelum memilih baris Jadual 2.")
    else:
        rule=next((r for r in NATIONAL_LOT_RULES
                   if r["category"]==category and storeys in r["storeys"]),None)
        if rule:
            role="primary_reference" if profile=="national_2016" else "supplementary_national_reference"
            add_check(key="min_lot_frontage",title="Lebar hadapan lot minimum",
                      limit=rule["min_width_m"],observed=proposal.lot_width_m,
                      measure="m",direction="min",source=NATIONAL_SOURCE,
                      page=f"Jadual 2, muka surat bercetak {rule['page']}",role=role,
                      printed_equivalent_ft=rule.get("min_width_ft"))
            add_check(key="min_lot_depth",title="Panjang / dalam lot minimum",
                      limit=rule["min_depth_m"],observed=proposal.lot_depth_m,
                      measure="m",direction="min",source=NATIONAL_SOURCE,
                      page=f"Jadual 2, muka surat bercetak {rule['page']}",role=role,
                      printed_equivalent_ft=rule.get("min_depth_ft"))
            if rule["min_floor_area_m2"] is not None:
                add_check(key="min_floor_area_national",title="Luas lantai minimum (rujukan kebangsaan)",
                          limit=rule["min_floor_area_m2"],observed=floor_m2,
                          measure="m²",direction="min",source=NATIONAL_SOURCE,
                          page=f"Jadual 2, muka surat bercetak {rule['page']}",role=role)
            if profile=="perak_2023":
                warnings.append("GP001-A national lot minima are displayed as supplementary references, NOT confirmed as binding Perak/PBT lot minima. PR1 Perak 2023 lists floor area, not frontage/depth.")
        else:
            if category=="terrace_high":
                warnings.append("GP001-A 2016 Jadual 2 has NO high-cost terrace minimum row. The High/Premium 22 x 75 ft preset is only a development design example, not a statutory minimum.")
            else:
                warnings.append("No matching national Jadual 2 row for this housing category/storey combination; do not infer a standard.")
    if profile=="perak_2023":
        if is_terrace:
            add_check(key="max_storeys_perak",title="Bilangan tingkat maksimum (teres Perak)",
                      limit=3,observed=storeys,measure="tingkat",direction="max",
                      source=PERAK_SOURCE,page="PR1, halaman bercetak 5",role="primary_state_reference")
            add_check(key="max_building_height_perak",title="Tinggi tanah-ke-bumbung maksimum",
                      limit=60*0.3048,observed=building_height_m,measure="m",direction="max",
                      source=PERAK_SOURCE,page="PR1, halaman bercetak 5",role="primary_state_reference")
            add_check(key="min_bedrooms_perak",title="Bilangan bilik tidur minimum",
                      limit=3,observed=bedrooms,measure="bilik",direction="min",
                      source=PERAK_SOURCE,page="PR1, halaman bercetak 5",role="primary_state_reference")
            if segment is not None and segment in PERAK_FLOOR_MIN_SQFT:
                area=PERAK_FLOOR_MIN_SQFT[segment]*0.09290304
                add_check(key="min_floor_area_perak",title="Luas ruang lantai minimum",
                          limit=round(area,4),observed=floor_m2,measure="m²",direction="min",
                          source=PERAK_SOURCE,page="PR1, halaman bercetak 5; "+str(int(PERAK_FLOOR_MIN_SQFT[segment]))+" kps",role="primary_state_reference")
            else:
                warnings.append("Pilih segmen kos Perak (kos rendah/sederhana/mampu milik/terbuka) untuk mengetahui luas lantai minimum yang betul.")
            warnings.append("PR1 Perak menyebut rizab jalan 50 kaki, lorong belakang 15 kaki, lorong tepi 20 kaki, dan anjakan hadapan 15/20 kaki; geometri jalan/anjakan BELUM diuji dalam modul ini.")
        elif category in PERAK_OTHER_HOUSING:
            state=PERAK_OTHER_HOUSING[category]
            page=f"{state['code']}, halaman bercetak {state['page']}"
            add_check(key="max_storeys_perak",title="Bilangan tingkat maksimum (Perak)",
                      limit=state["max_storeys"],observed=storeys,measure="tingkat",
                      direction="max",source=PERAK_SOURCE,page=page,role="primary_state_reference")
            add_check(key="max_building_height_perak",title="Ketinggian tanah ke bumbung maksimum (Perak)",
                      limit=round(state["max_height_ft"]*.3048,4),observed=building_height_m,
                      measure="m",direction="max",source=PERAK_SOURCE,page=page,role="primary_state_reference")
            add_check(key="min_bedrooms_perak",title="Bilangan bilik tidur minimum (Perak)",
                      limit=state["min_bedrooms"],observed=bedrooms,measure="bilik",
                      direction="min",source=PERAK_SOURCE,page=page,role="primary_state_reference")
            add_check(key="min_floor_area_perak",title="Luas ruang lantai minimum (Perak)",
                      limit=round(state["min_floor_sqft"]*.09290304,4),observed=floor_m2,
                      measure="m²",direction="min",source=PERAK_SOURCE,page=page,role="primary_state_reference")
            if state.get("notes"):
                warnings.append(state["notes"])
            warnings.append(
                "PR2-PR6 has road/lot setback requirements which are not measured in the current map. "
                "National lot frontage/depth minima remain supplementary and require verified PBT adoption."
            )
        else:
            warnings.append("Tidak ada kategori perumahan terperinci yang dipilih/diindeks untuk GPP Perak PR1-PR6.")
    if profile=="national_2016":
        applicable=[item for item in checks if item["role"]=="primary_reference"]
    else:
        applicable=[item for item in checks if item["role"]=="primary_state_reference"]
    if any(c["result"] in ("below_min","above_max") for c in applicable):
        status="outside_numeric_reference"
    elif not applicable:
        status="insufficient_rule_coverage"
    elif any(c["result"]=="not_supplied" for c in applicable):
        status="more_inputs_needed"
    else:
        status="numeric_reference_only"
    return {
        "registry_version":REGISTRY_VERSION,
        "profile_id":profile,"profile_label":label,
        "status":status,"checks":checks,
        "reference_only":True,"warnings":warnings,
        "max_lot_width_m":None,"max_lot_depth_m":None,
        "message":"Perbandingan angka GPP berasaskan halaman dokumen sahaja; bukan pematuhan rasmi. Saiz lot maksimum tidak dinyatakan pada Jadual 2 yang diindeks.",
    }


def answer_gpp_question(question:str)->dict[str,Any]:
    """Deterministic policy Q&A with evidence links; does not use LLM guesses."""
    q=question.casefold()
    perak="perak" in q or "ipoh" in q or "meru" in q or "tanjung malim" in q
    if any(term in q for term in ("rumah kedai", "shoplot", "shop lot", "lot kedai", "perdagangan", "komersial")):
        commerce=next(source for source in CATALOG_ONLY if source["id"]=="gpp_commercial_gp003a")
        return {
            "mode":"verified_policy_registry_summary",
            "response":(
                "**GPP Kawasan Perdagangan:** PLANEXUS menyenaraikan dokumen GP003-A "
                "sebagai rujukan rasmi tetapi belum mengesahkan jadual ukuran lot "
                "rumah kedai untuk kategori, ketinggian dan bidang kuasa ini. "
                "Jangan guna piawaian rumah teres sebagai minimum rumah kedai. "
                "Rujuk GPP Perdagangan, RT dan PBT semasa. "
                f"Sumber indeks rasmi: {commerce['url']}.\n\n"
                "**Status:** Belum diindeks; tiada saiz lot minimum atau maksimum yang boleh disahkan."
            ),
            "notice":"Sumber GPP perdagangan hanya di katalog; tiada aturan angka untuk kegunaan ini.",
            "policy_sources":[{"title":commerce["title"],"url":commerce["url"],"evidence":commerce["evidence"]}],
            "evidence":None,
        }
    if any(term in q for term in ("parking", "parkir", "tempat letak kereta", "tempat letak kenderaan",
                                     "kemudahan masyarakat", "tanah tinggi", "kawasan bukit", "cerun gpp")):
        matched=next((doc for doc in CATALOG_ONLY
                      if ("parkir" in q or "parking" in q or "letak" in q) and doc["id"]=="gpp_parking_gp011a"
                      or ("kemudahan masyarakat" in q and doc["id"]=="gpp_facilities_2022")
                      or (("bukit" in q or "tanah tinggi" in q or "cerun gpp" in q) and doc["id"]=="gpp_hills_gp007a11")),None)
        if matched:
            return {
                "mode":"verified_policy_registry_summary",
                "response":(
                    "**Dokumen GPP belum diindeks secara numerik:** "+matched["title"]+". "
                    "PLANEXUS belum mengesahkan jadual nisbah/ukuran dalam dokumen ini. "
                    "Tiada kadar, syarat atau ambang angka boleh disimpulkan secara automatik. "
                    f"Sumber rasmi: {matched['url']}. Semak RT/PBT dan dokumen terkini."
                ),
                "notice":"Sumber rujukan sah dalam katalog; angka piawaian belum dimasukkan.",
                "policy_sources":[{"title":matched["title"],"url":matched["url"],"evidence":matched["evidence"]}],
                "evidence":None,
            }
    # A direct question about a known home type must NOT get a generic
    # terrace answer. Derive dimensions from the same validated Jadual 2 rules.
    if any(term in q for term in ("semua gpp","keseluruhan gpp","senarai gpp")):
        return {
            "mode":"verified_policy_registry_summary",
            "response":(
                "**Liputan GPP PLANEXUS:** Dua sumber perumahan mempunyai aturan angka disahkan: "
                +NATIONAL_SOURCE["title"]+"; "+PERAK_SOURCE["title"]+". "
                "Empat sumber lain hanya tersenarai dalam katalog dan belum diekstrak "
                "(perdagangan, parkir, kawasan bukit dan kemudahan masyarakat). "
                "PLANEXUS BELUM mengindeks semua GPP negeri, PBT dan peraturan RT. "
                "Buka GPP Knowledge Registry untuk lihat status setiap dokumen."
            ),
            "notice":"Liputan dokumen terhad dan dinyatakan; tiada tuntutan semakan menyeluruh.",
            "policy_sources":[{"title":r["title"],"url":r["url"],"evidence":r["evidence"]}
                              for r in (NATIONAL_SOURCE,PERAK_SOURCE)],
            "evidence":None,
        }

    selected_category = None
    if ("teres" in q or "terrace" in q) and any(x in q for x in ("kos tinggi","high cost","high-cost","premium")):
        selected_category="terrace_high"
    elif ("teres" in q or "terrace" in q) and any(x in q for x in ("mid cost","mid-cost","medium cost")):
        selected_category="terrace_middle"
    elif ("teres" in q or "terrace" in q) and any(x in q for x in ("low cost","low-cost")):
        selected_category="terrace_low_cost"
    elif any(x in q for x in ("zero lot","zero-lot","zlb")):
        selected_category="zero_lot"
    elif any(x in q for x in ("berkembar","semi-detached","semi detached")):
        selected_category="semi_detached"
    elif any(x in q for x in ("kluster","cluster")):
        selected_category="cluster"
    elif any(x in q for x in ("rumah bandar","townhouse","town house")):
        selected_category="townhouse"
    elif any(x in q for x in ("sesebuah","detached")):
        selected_category="detached"
    elif any(x in q for x in ("sederhana rendah","lower middle")):
        selected_category="terrace_lower_middle"
    elif any(x in q for x in ("kos rendah","low-cost","low cost")):
        selected_category="terrace_low_cost"
    elif any(x in q for x in ("kos sederhana","middle cost")):
        selected_category="terrace_middle"

    if selected_category:
        requested_floors = None
        if "setingkat" in q or "satu tingkat" in q or "one storey" in q:
            requested_floors=1
        elif "dua tingkat" in q or "two storey" in q:
            requested_floors=2
        elif "tiga tingkat" in q or "three storey" in q:
            requested_floors=3
        else:
            match=re.search(r"(?<!\d)([123])\s*(?:tingkat|storey|storeys)\b",q)
            if match:
                requested_floors=int(match.group(1))
        rules=[
            rule for rule in NATIONAL_LOT_RULES
            if rule["category"]==selected_category
            and (requested_floors is None or requested_floors in rule["storeys"])
        ]
        if rules:
            rows="\n".join(
                "- "+rule["label"]+": lot MINIMUM "
                +str(rule["min_width_m"])+" x "+str(rule["min_depth_m"])+" m"
                +("; luas lantai minimum "+str(rule["min_floor_area_m2"])+" m² untuk 1 tingkat"
                   if rule["min_floor_area_m2"] is not None else "")
                for rule in rules
            )
        else:
            rows=(
                "GP001-A 2016 Jadual 2 tidak menetapkan had minimum lot "
                "khusus teres kos TINGGI (High) - sila semak garis panduan "
                "negeri dan PBT." if selected_category=="terrace_high" else
                "Tiada baris Jadual 2 yang disahkan bagi jenis rumah dan bilangan tingkat ini."
            )
        practical=next((preset for preset in PRACTICAL_TERRACE_PRESETS
                        if preset["category"]==selected_category),None)
        example_note=""
        if practical and selected_category in ("terrace_middle","terrace_high"):
            example_note=(
                "\n**Preset reka bentuk, bukan had GPP:** "+practical["label"]
                +". "+practical["note"]
                +" Sumber contoh: "+practical["source_url"]+"\n"
            )
        if perak:
            if selected_category.startswith("terrace_"):
                category_note=(
                    "**Perak 2023 PR1 (teres):** lantai minimum 900 kps kos rendah, "
                    "950 kps kos sederhana, 1,000 kps mampu milik, 1,001 kps bebas; "
                    "maksimum 3 tingkat dan 60 kaki tinggi bangunan. "
                    "PR1 mengandungi syarat jalan/anjakan yang perlu diukur dalam pelan."
                )
            else:
                state=PERAK_OTHER_HOUSING.get(selected_category)
                if state:
                    category_note=(
                        "**Perak 2023 "+state["code"]+" (hlm. "+str(state["page"])+"):** "
                        "Luas lantai minimum "+str(int(state["min_floor_sqft"]))+" kps, "
                        "bilangan bilik minimum "+str(state["min_bedrooms"])+", "
                        "maksimum "+str(state["max_storeys"])+" tingkat, "
                        "tinggi tanah ke bumbung maksimum "+str(int(state["max_height_ft"]))+" kaki. "
                        +(" "+state["notes"] if state.get("notes") else "")
                        +" Jalan dan anjakan perlu diukur berasingan pada pelan."
                    )
                else:
                    category_note="Tiada aturan Perak khusus yang telah diindeks bagi jenis rumah ini."
            body=category_note+"\n**Rujukan tambahan lot kebangsaan GP001-A (bukan syarat Perak/PBT yang disahkan):**\n"+rows+example_note
            refs=[PERAK_SOURCE,NATIONAL_SOURCE]
        else:
            body="**GP001-A 2016 Jadual 2 (hlm.44–45), jenis rumah diminta:**\n"+rows+example_note
            refs=[NATIONAL_SOURCE]
        if practical and selected_category in ("terrace_middle","terrace_high"):
            refs.append({
                "title":"Contoh saiz lot projek teres, bukan GPP",
                "url":practical["source_url"],"evidence":practical["source_page"]
            })
        return {
            "mode":"verified_policy_registry_summary",
            "response":body+"\n\nSaiz lot di atas ialah minimum, bukan maksimum. "
                       "Maksimum lot tidak dinyatakan dalam jadual ini. "
                       "PBT/RT, pindaan negeri dan syarat lain mesti disahkan sebelum perancangan.",
            "notice":"Peraturan bersumber GP001-A/Perak, bukan tafsiran AI generatif. Tiada kelulusan diberikan.",
            "policy_sources":[{"title":r["title"],"url":r["url"],"evidence":r["evidence"]} for r in refs],
            "evidence":None,
        }
    if perak:
        response=(
            "**GPP Negeri Perak 2023 (PR1, halaman 5):** "
            "Rumah teres kos rendah: lantai sekurang-kurangnya 900 kps; kos sederhana 950 kps; "
            "mampu milik 1,000 kps; kategori terbuka 1,001 kps dan ke atas. "
            "Tiga tingkat maksimum, 3 bilik tidur minimum, dan tinggi dari tanah ke bumbung maksimum 60 kaki. "
            "PR1 juga menyenaraikan jalan perkhidmatan minimum 50 kaki, lorong belakang 15 kaki, lorong tepi 20 kaki, dan anjakan hadapan 15 kaki (kos rendah) / 20 kaki (kategori lain); ini belum dinilai berdasarkan pelan geometri. "
            "Dokumen PR1 ini tidak menyatakan ukuran lebar x panjang lot minimum, jadi rujuk GP001-A dan sahkan dengan PBT/RT yang berkuat kuasa. "
            f"Sumber: {PERAK_SOURCE['url']} (PR1, hlm. 5)."
        )
        refs=[PERAK_SOURCE,NATIONAL_SOURCE]
    else:
        response=(
            "**GP001-A Perumahan 2016, Jadual 2 (hlm. 44-45):** "
            "Teres kos rendah 1 tingkat 6.1 x 16.8 m, 2 tingkat 4.3 x 16.8 m; "
            "teres kos sederhana rendah 1 tingkat 6.1 x 18.3 m, 2 tingkat 5.5 x 16.8 m; "
            "teres kos sederhana 1 tingkat 6.1 x 19.8 m, 2-3 tingkat 5.5 x 19.8 m. "
            "Ini saiz lot MINIMUM, bukan maksimum. Negeri/PBT, jenis rumah dan jumlah tingkat mesti dipastikan. "
            f"Sumber: {NATIONAL_SOURCE['url']} (Jadual 2, hlm. 44-45)."
        )
        refs=[NATIONAL_SOURCE]
    return {"mode":"verified_policy_registry_summary",
            "response":response+"\n\n**Had:** Ini bukan kelulusan pembangunan atau tafsiran RT. Semak pindaan terkini dan PBT.",
            "notice":"GPP curated registry, source-backed; no LLM; local adoption unverified.",
            "policy_sources":[{"title":r["title"],"url":r["url"],"evidence":r["evidence"]} for r in refs],
            "evidence":None}
