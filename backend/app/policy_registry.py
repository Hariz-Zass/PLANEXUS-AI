"""Curated, source-grounded PLANEXUS GPP policy registry (read-only, versioned).

This is NOT an indexed copy of all Malaysian planning policies. Only entries
manually checked against the stated official document/page are machine-readable.
Never infer a maximum where the source lists only a minimum, and never merge a
national reference with state/PBT regulations as a certified composite.
"""
from __future__ import annotations

from typing import Any

REGISTRY_VERSION = "2026-11-02-gpp-housing-v3"

NATIONAL_SOURCE = {
    "id": "gp001a_2016",
    "title": "GP 001-A: Garis Panduan Perancangan Perumahan",
    "year": 2016,
    "issuer": "PLANMalaysia / Jabatan Perancangan Bandar dan Desa Semenanjung Malaysia",
    "jurisdiction": "Semenanjung Malaysia - national reference, subject to adoption and local plans",
    "url": "https://www.planmalaysia.gov.my/uploads/content-downloads/file_20251114202120.pdf",
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
    "evidence": "PR1, printed page 5, and approval notice; MMKN 5 September 2023, confirmed 13 September 2023",
    "scope": "State guidance; source table provides minimum floor areas and storey/height constraints, but not numerical lot frontage/depth minima.",
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

# Width/depth are explicit METRES as printed in Table 2, not approximate
# conversions of rounded imperial equivalents. None is NEVER zero or unlimited.
# Storey 1.5 is not represented in the product's integer floor input.
NATIONAL_LOT_RULES: tuple[dict[str, Any], ...] = (
    {"category":"terrace_low_cost", "storeys":[1], "label":"Rumah teres kos rendah, 1 tingkat",
     "min_width_m":6.1, "min_depth_m":16.8, "min_floor_area_m2":65.0, "page":44},
    {"category":"terrace_low_cost", "storeys":[2], "label":"Rumah teres kos rendah, 2 tingkat",
     "min_width_m":4.3, "min_depth_m":16.8, "min_floor_area_m2":None, "page":44},
    {"category":"terrace_lower_middle", "storeys":[1], "label":"Rumah teres kos sederhana rendah, 1 tingkat",
     "min_width_m":6.1, "min_depth_m":18.3, "min_floor_area_m2":69.7, "page":44},
    {"category":"terrace_lower_middle", "storeys":[2], "label":"Rumah teres kos sederhana rendah, 2 tingkat",
     "min_width_m":5.5, "min_depth_m":16.8, "min_floor_area_m2":None, "page":44},
    {"category":"terrace_middle", "storeys":[1], "label":"Rumah teres kos sederhana, 1 tingkat",
     "min_width_m":6.1, "min_depth_m":19.8, "min_floor_area_m2":79.0, "page":44},
    {"category":"terrace_middle", "storeys":[2,3], "label":"Rumah teres kos sederhana, 2-3 tingkat",
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
            {"id":"terrace_middle","label":"Rumah teres kos sederhana","development_type":"terrace_housing"},
            {"id":"cluster","label":"Rumah kluster","development_type":"other_landed"},
            {"id":"semi_detached","label":"Rumah berkembar","development_type":"other_landed"},
            {"id":"detached","label":"Rumah sesebuah","development_type":"other_landed"},
            {"id":"zero_lot","label":"Rumah sesebuah (zero lot boundary)","development_type":"other_landed"},
        ],
        "national_lot_rules": [
            {**r,"source_id":NATIONAL_SOURCE["id"],
             "url":NATIONAL_SOURCE["url"],"max_width_m":None,"max_depth_m":None}
            for r in NATIONAL_LOT_RULES
        ],
        "perak_floor_min_sqft": PERAK_FLOOR_MIN_SQFT,
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
                  measure:str,direction:str,source:dict[str,Any],page:str,role:str)->None:
        if observed is None:
            state="not_supplied"
        elif direction=="min":
            state="meets_number" if observed+1e-8>=limit else "below_min"
        else:
            state="meets_number" if observed<=limit+1e-8 else "above_max"
        checks.append({
            "key":key,"title":title,"type":direction,"value":float(limit),
            "observed":float(observed) if observed is not None else None,
            "unit":measure,"result":state,
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
                      page=f"Jadual 2, muka surat bercetak {rule['page']}",role=role)
            add_check(key="min_lot_depth",title="Panjang / dalam lot minimum",
                      limit=rule["min_depth_m"],observed=proposal.lot_depth_m,
                      measure="m",direction="min",source=NATIONAL_SOURCE,
                      page=f"Jadual 2, muka surat bercetak {rule['page']}",role=role)
            if rule["min_floor_area_m2"] is not None:
                add_check(key="min_floor_area_national",title="Luas lantai minimum (rujukan kebangsaan)",
                          limit=rule["min_floor_area_m2"],observed=floor_m2,
                          measure="m²",direction="min",source=NATIONAL_SOURCE,
                          page=f"Jadual 2, muka surat bercetak {rule['page']}",role=role)
            if profile=="perak_2023":
                warnings.append("GP001-A national lot minima are displayed as supplementary references, NOT confirmed as binding Perak/PBT lot minima. PR1 Perak 2023 lists floor area, not frontage/depth.")
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
        else:
            warnings.append("PR1 Perak digunakan hanya untuk teres. Jenis perumahan bertanah lain ada PR2-PR6, belum diindeks sebagai pemeriksaan numerik.")
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
