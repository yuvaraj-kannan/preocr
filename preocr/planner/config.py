"""Configuration for the intent-aware OCR planner.

Thresholds are configurable and should be calibrated using false-positive cost
(OCR cost) vs false-negative cost (missed extraction). Use a validation set
with page-level ground truth.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlannerConfig:
    """
    Configuration for the OCR planner.

    Attributes:
        override_policy: Controls which overrides are active. Policy-configurable
            scoping so the decision layer is reusable across industries.
            - "none": scoring only (no overrides)
            - "failsafe_only": extraction/layout failure only
            - "medical_strict": failsafe + OCR-critical intent overrides
        domain_mode: Convenience for override_policy. "medical" -> medical_strict,
            "generic" -> failsafe_only. Ignored if override_policy is set explicitly.
        intent_high_threshold: Score threshold for OCR-critical intent override.
        decision_threshold_safety: Lower threshold for safety mode (favor recall).
        decision_threshold_balanced: F1-optimized threshold (medical mode).
        decision_threshold_balanced_generic: Higher threshold for generic mode
            (precision-oriented; intent_weight=0 so less signal).
        decision_threshold_cost: Higher threshold for cost mode (reduce OCR).
        decision_mode: "safety" | "balanced" | "cost".
        intent_weight: Weight for intent contribution in scoring (default 0.6).
        image_weight: Weight for image_dominance (default 0.3).
        text_weakness_weight: Weight for text_weakness (default 0.3).
        very_low_text_threshold: Text length below this may add failsafe_boost.
        fast_path_image_coverage_threshold: Skip planner scoring when preocr says no
            OCR and all pages have image_coverage below this (%). 0 = disabled.
        decision_version: Version string for decision schema.
    """

    override_policy: Optional[str] = None  # none | failsafe_only | medical_strict
    domain_mode: str = "medical"  # medical | generic
    intent_high_threshold: float = 0.7
    decision_threshold_safety: float = 0.45
    decision_threshold_balanced: float = 0.6
    decision_threshold_balanced_generic: float = 0.65
    decision_threshold_cost: float = 0.75
    decision_mode: str = "balanced"
    intent_weight: float = 0.6
    image_weight: float = 0.3
    text_weakness_weight: float = 0.3
    very_low_text_threshold: int = 20
    fast_path_image_coverage_threshold: float = 10.0  # 0 = disabled
    decision_version: str = "intent-aware-v1"

    def get_decision_threshold(self) -> float:
        """Return the decision threshold for the current mode."""
        if self.decision_mode == "safety":
            return self.decision_threshold_safety
        if self.decision_mode == "cost":
            return self.decision_threshold_cost
        if self.decision_mode == "balanced" and self.domain_mode == "generic":
            return self.decision_threshold_balanced_generic
        return self.decision_threshold_balanced

    def get_intent_weight(self) -> float:
        """
        Intent weight for scoring. Zero in generic mode (intent is domain-specific).
        In medical mode, returns intent_weight.
        """
        if self.domain_mode == "generic":
            return 0.0
        return self.intent_weight

    def get_override_policy(self) -> str:
        """
        Resolve override policy. If override_policy is set, use it.
        Otherwise derive from domain_mode: medical -> medical_strict, generic -> failsafe_only.
        """
        if self.override_policy is not None:
            return self.override_policy
        return "medical_strict" if self.domain_mode == "medical" else "failsafe_only"

    def intent_override_active(self) -> bool:
        """Whether OCR-critical intent override is active (medical_strict only)."""
        return self.get_override_policy() == "medical_strict"

    def failsafe_override_active(self) -> bool:
        """Whether extraction/layout failsafe override is active."""
        return self.get_override_policy() in ("failsafe_only", "medical_strict")
