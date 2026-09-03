"""Evidence-first property profiles and configurable score calculations."""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).parent
DEFAULT_CONFIG_PATH = ROOT / "knowledge" / "scoring_config.json"


@dataclass
class ScoringConfig:
    signal_weights: dict[str, int] = field(default_factory=lambda: {
        "absentee_owner": 8,
        "out_of_state_mailing": 8,
        "probate": 18,
        "foreclosure": 20,
        "tax_delinquent": 15,
        "vacancy": 14,
        "long_ownership": 10,
        "condition_evidence": 15,
    })
    opportunity_weights: dict[str, int] = field(default_factory=lambda: {
        "motivation": 20,
        "deal_economics": 25,
        "buyer_demand": 15,
        "equity": 10,
        "property_quality": 8,
        "marketability": 7,
        "distress_momentum": 5,
        "data_confidence": 10,
    })
    tier_thresholds: dict[str, int] = field(default_factory=lambda: {
        "A+": 95, "A": 90, "B": 80, "C": 70, "D": 60,
    })


@dataclass
class PropertyProfile:
    property_id: str
    address: str
    county: str
    owner_name: str
    mailing_address: Optional[str]
    sources: list[str]
    source_files: list[str]
    data_states: dict[str, str]
    signals: list[dict[str, Any]]
    property_facts: dict[str, Any]
    scores: dict[str, Optional[int]]
    explanations: dict[str, list[str]]
    data_gaps: list[str]
    recommendation: str
    model_version: str = "rules-v1"
    calculated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> ScoringConfig:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ScoringConfig()
    defaults = ScoringConfig()
    return ScoringConfig(
        signal_weights={**defaults.signal_weights, **values.get("signal_weights", {})},
        opportunity_weights={**defaults.opportunity_weights, **values.get("opportunity_weights", {})},
        tier_thresholds={**defaults.tier_thresholds, **values.get("tier_thresholds", {})},
    )


def _score_signals(signals: list[dict[str, Any]], config: ScoringConfig) -> tuple[int, list[str]]:
    positive = []
    total = 0
    for signal in signals:
        signal_type = signal["type"]
        if signal_type in config.signal_weights:
            total += config.signal_weights[signal_type]
            positive.append(signal["label"])
    return min(100, total), positive


def build_profile(lead: dict[str, Any], config: Optional[ScoringConfig] = None) -> PropertyProfile:
    config = config or load_config()
    sources = list(lead.get("sources", []))
    mailing = lead.get("mailing_address") or None
    out_of_state = bool(mailing and mailing != "Unknown" and " TX " not in f" {mailing.upper()} ")
    signals = [{"type": "absentee_owner", "label": "Absentee owner", "state": "DERIVED"}]
    if out_of_state:
        signals.append({"type": "out_of_state_mailing", "label": "Out-of-state mailing address", "state": "DERIVED"})
    hcad = lead.get("hcad") or {}
    if hcad.get("ownership_duration_years") is not None and hcad["ownership_duration_years"] >= 10:
        signals.append({"type": "long_ownership", "label": f"{hcad['ownership_duration_years']} years since recorded ownership change", "state": "DERIVED"})
    motivation, positive = _score_signals(signals, config)
    source_confidence = min(100, len(sources) * 20 + (20 if mailing else 0) + (25 if hcad else 0))
    scores = {
        "distress": None,
        "motivation": motivation,
        "equity": None,
        "property_quality": None,
        "marketability": None,
        "buyer_demand": None,
        "deal_spread": None,
        "data_confidence": source_confidence,
        "opportunity": None,
        "risk": None,
    }
    gaps = ["Independent current market value", "Outstanding debt", "Comparable sales", "Repairs", "Buyer demand", "Deal economics"]
    if not hcad:
        gaps.insert(0, "Property characteristics")
    explanations = {
        "motivation": [f"+ {item}" for item in positive] or ["No supported motivation signal"],
        "data_confidence": [f"{len(sources)} source record(s) attached", "Mailing address is available" if mailing else "Mailing address is unknown", "HCAD parcel record matched" if hcad else "HCAD parcel record not matched"],
        "opportunity": ["Not calculated: valuation, equity, repairs, buyer demand, and deal economics are unavailable"],
    }
    return PropertyProfile(
        property_id=lead["id"], address=lead["address"], county=lead["county"],
        owner_name=lead["owner_name"], mailing_address=mailing, sources=sources,
        source_files=list(lead.get("source_files", [])),
        data_states={"identity": "VERIFIED", "mailing_address": "VERIFIED" if mailing else "UNKNOWN", "motivation": "INFERRED"},
        signals=signals, property_facts=hcad, scores=scores, explanations=explanations, data_gaps=gaps,
        recommendation="RESEARCH FIRST", calculated_at=lead.get("calculated_at", ""),
    )