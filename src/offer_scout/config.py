from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    pass


def _load(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class Settings:
    raw: dict[str, Any]
    keywords: dict[str, Any]
    compliance: dict[str, Any]
    root: Path
    localization: dict[str, Any] | None = None

    @property
    def run(self) -> dict[str, Any]:
        return self.raw["run"]

    @property
    def sources(self) -> dict[str, Any]:
        return self.raw.get("sources", {})

    @property
    def scoring(self) -> dict[str, Any]:
        return self.raw.get("scoring", {})

    @property
    def fx(self) -> dict[str, float]:
        return self.raw.get("fx_rates_to_usd", {"USD": 1.0})

    @property
    def markets(self) -> dict[str, dict[str, Any]]:
        """Language-market id -> config (label, region, countries, currency)."""
        return self.raw.get("markets", {})

    def country_language(self, country: str | None) -> str | None:
        for lang, m in self.markets.items():
            if country in m.get("countries", []):
                return lang
        return None

    def supported_languages(self) -> set[str]:
        return set(self.compliance.get("supported_languages", ["en"]))

    def subcategories(self) -> dict[str, dict[str, Any]]:
        """Flat map: subcategory id -> config (category and localization merged in)."""
        loc = (self.localization or {}).get("subcategories", {})
        out: dict[str, dict[str, Any]] = {}
        for category, subs in self.keywords["categories"].items():
            for sub_id, cfg in subs.items():
                merged = dict(cfg)
                merged["category"] = "blocked" if category == "blocked" else category
                merged.update(loc.get(sub_id, {}))
                out[sub_id] = merged
        return out


def load_settings(config_dir: str | Path = "config", root: str | Path = ".") -> Settings:
    config_dir = Path(config_dir)
    raw = _load(config_dir / "settings.yaml")
    keywords = _load(config_dir / "keywords.yaml")
    compliance = _load(config_dir / "compliance.yaml")
    loc_path = config_dir / "localization.yaml"
    localization = _load(loc_path) if loc_path.exists() else {}
    gov = raw.get("governance", {})
    # Scout never publishes or spends: fail loudly if someone flips these.
    if gov.get("auto_publish") or gov.get("auto_launch_ads"):
        raise ConfigError(
            "auto_publish / auto_launch_ads must be false in Scout. "
            "Publishing and ads belong to Agent 3 behind a human approval gate."
        )
    if not gov.get("require_human_approval", True):
        raise ConfigError("require_human_approval must stay true.")
    return Settings(raw=raw, keywords=keywords, compliance=compliance, root=Path(root), localization=localization)
