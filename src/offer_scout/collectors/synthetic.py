"""SIMULATED data generator for demos, tests and dashboard development.

Everything produced here is fictional and flagged simulated=True. The pipeline marks the whole
run data_mode=SIMULATED, caps confidence at LOW and blocks any handoff to Agent 2.
Supply differs per language-market so cross-market ideas can be exercised end to end.
"""
from __future__ import annotations

import random
from typing import Any

from ..models import RawRecord, Record
from ..normalize import make_record_id, now_iso
from .base import Collector, ParseContext

_COUNTRY_LANG = {"BR": "pt", "DE": "de", "FR": "fr", "ES": "es"}
DEFAULT_MK = {"en": 1.0, "pt": 0.5, "de": 0.5, "fr": 0.5, "es": 0.5}

# n=listings, price, max reviews, sellers, ad runtime (None = no ads), trend slope, mk = share of supply per language-market
PROFILES: dict[str, dict[str, Any]] = {
    "pet_business_kit": dict(n=24, price=(3, 32), reviews=1500, sellers=14, ad_runtime=52, trend=1.25, mk={"en": 1.0, "pt": 0.04, "de": 0.12, "fr": 0.5, "es": 0.2}),
    "pet_health_record": dict(n=30, price=(3, 9), reviews=500, sellers=25, ad_runtime=None, trend=1.0, clone=True),
    "pet_care_planner": dict(n=16, price=(4, 18), reviews=400, sellers=11, ad_runtime=None, trend=1.0),
    "caregiver_handover": dict(n=18, price=(5, 25), reviews=250, sellers=12, ad_runtime=None, trend=1.15, risky=["Dementia Caregiver Daily Log", "Cancer Treatment Tracker Caregiver Binder"], mk={"en": 1.0, "pt": 0.05, "de": 0.7, "fr": 0.1, "es": 0.1}),
    "special_needs_family_organizer": dict(n=12, price=(5, 20), reviews=180, sellers=8, ad_runtime=None, trend=1.05),
    "medical_info_organizer": dict(n=10, price=(4, 15), reviews=150, sellers=7, ad_runtime=None, trend=1.0),
    "habit_tracker": dict(n=30, price=(1, 8), reviews=900, sellers=26, ad_runtime=None, trend=1.0, clone=True),
    "study_planner": dict(n=20, price=(4, 15), reviews=600, sellers=15, ad_runtime=None, trend=1.0, mk={"en": 1.0, "pt": 0.9, "de": 0.8, "fr": 0.3, "es": 0.1}),
    "tutoring_business_kit": dict(n=10, price=(8, 30), reviews=120, sellers=7, ad_runtime=None, trend=1.1),
    "freelancer_client_kit": dict(n=18, price=(6, 35), reviews=700, sellers=12, ad_runtime=34, trend=1.1, mk={"en": 1.0, "pt": 0.08, "de": 0.1, "fr": 0.4, "es": 0.1}),
    "bookkeeping_spreadsheet": dict(n=22, price=(5, 30), reviews=800, sellers=16, ad_runtime=None, trend=1.05, mk={"en": 1.0, "pt": 0.9, "de": 0.7, "fr": 0.5, "es": 0.4}),
    "social_content_planner": dict(n=26, price=(2, 15), reviews=1100, sellers=22, ad_runtime=None, trend=1.0),
    "notion_template": dict(n=20, price=(4, 25), reviews=500, sellers=14, ad_runtime=None, trend=1.1),
    "event_planner": dict(n=18, price=(3, 18), reviews=600, sellers=14, ad_runtime=None, trend=1.0),
    "home_moving_organizer": dict(n=12, price=(3, 12), reviews=250, sellers=9, ad_runtime=None, trend=1.0),
    "budget_planner": dict(n=24, price=(3, 14), reviews=900, sellers=18, ad_runtime=None, trend=1.05),
    "family_routine_planner": dict(n=14, price=(3, 12), reviews=400, sellers=10, ad_runtime=None, trend=1.0),
    "autism_nutrition_intervention": dict(n=12, price=(8, 25), reviews=300, sellers=9, ad_runtime=20, trend=1.2),
    "get_rich_financial_claims": dict(n=8, price=(10, 40), reviews=100, sellers=6, ad_runtime=15, trend=1.0),
}
DECORATORS = {
    "en": ["Printable PDF", "Excel Google Sheets", "Canva Editable", "Instant Download", "Fillable PDF", "Digital Download"],
    "pt": ["PDF Imprimível", "Planilha Excel", "Download Instantâneo", "Editável no Canva"],
    "de": ["PDF zum Ausdrucken", "Excel Vorlage", "Sofort Download", "Canva Vorlage"],
    "fr": ["PDF imprimable", "Modèle Excel", "Téléchargement immédiat", "Modèle Canva"],
    "es": ["PDF imprimible", "Plantilla Excel", "Descarga inmediata", "Plantilla Canva"],
}


class SyntheticCollector(Collector):
    name = "synthetic"
    source_class = "synthetic"
    simulated = True
    country_scoped = True

    def __init__(self, subcategories: dict[str, dict[str, Any]], seed: int = 7):
        self.query_map: dict[str, tuple[str, str]] = {}
        for sid, cfg in subcategories.items():
            for q in cfg.get("queries", []):
                self.query_map[q] = (sid, "en")
            for lang, qs in (cfg.get("queries_i18n") or {}).items():
                for q in qs:
                    self.query_map[q] = (sid, lang)
        self.seed = seed
        self._emitted: set[tuple[str, str]] = set()

    def collect(self, query: str, country: str, limit: int) -> list[RawRecord]:
        hit = self.query_map.get(query)
        if not hit:
            return []
        sub, lang = hit
        if (sub, lang) in self._emitted:
            return []  # one batch per niche and language-market, however many queries or countries ask
        self._emitted.add((sub, lang))
        prof = PROFILES.get(sub, dict(n=6, price=(5, 20), reviews=60, sellers=4, ad_runtime=None, trend=1.0))
        mult = prof.get("mk", DEFAULT_MK).get(lang, DEFAULT_MK[lang])
        n = round(prof["n"] * mult)
        sellers = max(1, round(prof["sellers"] * mult))
        rng = random.Random(f"{self.seed}-{sub}-{lang}")
        decos = DECORATORS[lang]
        raws: list[RawRecord] = []
        stamp = now_iso()
        for i in range(n):
            seller = f"sim-seller-{lang}-{rng.randrange(sellers)}"
            title = f"{query.title()} | {rng.choice(decos)}"
            if lang == "en" and sub == "autism_nutrition_intervention":
                title = f"Autism Gluten Free Casein Free Diet Meal Plan | {rng.choice(decos)}"
            elif lang == "en" and sub == "get_rich_financial_claims":
                title = f"Trading Signals Course Get Rich Fast | {rng.choice(decos)}"
            elif prof.get("clone"):
                title = f"{query.title()} | {decos[i % 2]}"
            elif lang == "en" and prof.get("risky") and i < len(prof["risky"]):
                title = prof["risky"][i] + " | Printable PDF"
            reviews = int(rng.random() ** 2 * prof["reviews"] * max(mult, 0.2))
            recent = int(reviews * rng.uniform(0.02, 0.12))
            payload = dict(
                signal_type="REVIEW_VELOCITY", seller=seller, product_name=title, text=title,
                price_usd=round(rng.uniform(*prof["price"]), 2), review_count=reviews or None,
                recent_review_count_90d=recent, source_url=f"https://example.invalid/sim/{sub}/{lang}/{i}",
            )
            raws.append(RawRecord("synthetic_marketplace", f"sim-{sub}-{lang}-{i}", payload["source_url"], stamp, query, country, payload, True))
        if prof["ad_runtime"] and lang == "en":
            for s in range(3):
                for v in range(rng.randint(1, 6)):
                    title = f"{query.title()} for beginners"
                    if sub == "autism_nutrition_intervention":
                        title = "Autism diet meal plan for picky eaters"
                    if sub == "get_rich_financial_claims":
                        title = "Forex trading signals get rich"
                    payload = dict(signal_type="AD_PERSISTENCE", seller=f"sim-advertiser-{s}", product_name=title, text=title,
                                   runtime_days=max(3, prof["ad_runtime"] - s * 14 - v), active=True,
                                   source_url=f"https://example.invalid/sim-ad/{sub}/{s}/{v}")
                    raws.append(RawRecord("synthetic_ads", f"sim-ad-{sub}-{s}-{v}", payload["source_url"], stamp, query, country, payload, True))
        if n:
            series = [100.0 * (prof["trend"] ** (k / 11)) * rng.uniform(0.95, 1.05) for k in range(12)]
            raws.append(RawRecord("synthetic_trends", f"sim-trend-{sub}-{lang}", None, stamp, query, country,
                                  dict(signal_type="SEARCH_TREND", seller=None, product_name=query, text=query, trend_series=series), True))
        return raws

    def parse(self, raw: RawRecord, ctx: ParseContext) -> Record | None:
        p = raw.payload
        return Record(
            record_id=make_record_id(raw.source_platform, raw.source_id), source_platform=raw.source_platform,
            source_id=raw.source_id, source_url=raw.source_url, signal_type=p["signal_type"], captured_at=raw.captured_at,
            seller=p.get("seller"), product_name=p.get("product_name"), text=p.get("text", ""), country=raw.country,
            price_usd=p.get("price_usd"), review_count=p.get("review_count"),
            recent_review_count_90d=p.get("recent_review_count_90d"), runtime_days=p.get("runtime_days"),
            active=p.get("active"), trend_series=p.get("trend_series"), simulated=True,
        )
