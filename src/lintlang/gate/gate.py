"""
Optional LintLang finding gate — pure Python inference.

This module has ZERO dependencies beyond Python stdlib.
It loads bundled JSON artifacts and classifies findings for scan gate decisions.

Usage:
    from lintlang.gate import FPGate

    gate = FPGate()  # loads from default artifacts dir
    decision, p_tp = gate.classify(finding)
    # decision in {'KEEP', 'ESCALATE', 'DISMISS'}
    # p_tp in [0, 1] is the model's estimated TP score, not a verified probability
"""

import json
import math
from pathlib import Path
from typing import Any

# Import feature extraction (shared module, also pure Python)
from .features import extract_features, get_feature_names

# Default artifacts directory
DEFAULT_ARTIFACTS_DIR = Path(__file__).parent / 'artifacts'


class FPGate:
    """
    False Positive gate classifier for LintLang findings.

    Pure Python implementation with no external dependencies.
    """

    def __init__(
        self,
        artifacts_dir: str | Path | None = None,
        thresholds: tuple[float, float] | None = None,
    ):
        """
        Load model artifacts.

        Args:
            artifacts_dir: Directory containing model.json, scaler.json,
                          thresholds.json. Defaults to ./artifacts/
        """
        if artifacts_dir is None:
            artifacts_dir = DEFAULT_ARTIFACTS_DIR
        artifacts_dir = Path(artifacts_dir)

        # Load model coefficients
        with open(artifacts_dir / 'model.json') as f:
            model_data = json.load(f)
            self.coefficients = model_data['coefficients']
            self.intercept = model_data['intercept']
            self.feature_names = model_data['feature_names']

        # Load scaler parameters
        with open(artifacts_dir / 'scaler.json') as f:
            scaler_data = json.load(f)
            self.scaler_mean = scaler_data['mean']
            self.scaler_scale = scaler_data['scale']

        # Load thresholds
        with open(artifacts_dir / 'thresholds.json') as f:
            self.thresholds = json.load(f)
        if thresholds is not None:
            self.thresholds = {'keep': thresholds[0], 'dismiss': thresholds[1]}

        # Reject malformed or incompatible artifacts before any finding is scored.
        n_features = len(self.feature_names)
        if (
            self.feature_names != get_feature_names()
            or any(len(values) != n_features for values in (self.coefficients, self.scaler_mean, self.scaler_scale))
            or not all(isinstance(value, str) for value in self.feature_names)
        ):
            raise ValueError('Incompatible gate feature schema')
        for values in (self.coefficients, self.scaler_mean, self.scaler_scale):
            if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
                raise ValueError('Non-finite gate model parameter')
        if not all(value > 0 for value in self.scaler_scale):
            raise ValueError('Gate scaler must have positive scales')
        if not isinstance(self.intercept, (int, float)) or not math.isfinite(self.intercept):
            raise ValueError('Invalid gate intercept')
        keep = self.thresholds.get('keep')
        dismiss = self.thresholds.get('dismiss')
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            for value in (keep, dismiss)
        ):
            raise ValueError('Invalid gate thresholds')
        if not 0 <= dismiss < keep <= 1:
            raise ValueError('Gate thresholds require 0 <= DISMISS < KEEP <= 1')

    def _scale_features(self, features: dict[str, float]) -> list[float]:
        """Apply standard scaling to feature values."""
        scaled = []
        for i, name in enumerate(self.feature_names):
            value = features.get(name, 0.0)
            # StandardScaler: (x - mean) / scale
            scaled_value = (value - self.scaler_mean[i]) / self.scaler_scale[i]
            scaled.append(scaled_value)
        return scaled

    def _logistic(self, z: float) -> float:
        """Sigmoid function: 1 / (1 + exp(-z))"""
        # Clip to avoid overflow
        if z > 700:
            return 1.0
        if z < -700:
            return 0.0
        return 1.0 / (1.0 + math.exp(-z))

    def _predict_proba(self, features: dict[str, float]) -> float:
        """
        Compute the model's estimated TP score for a finding.

        Calibration on release inputs has not been established.
        """
        # Scale features
        scaled = self._scale_features(features)

        # Compute logit: z = intercept + sum(coef_i * x_i)
        logit = self.intercept
        for i, coef in enumerate(self.coefficients):
            logit += coef * scaled[i]

        # Apply sigmoid to get probability
        if not math.isfinite(logit):
            raise ValueError('Non-finite gate score')
        p_tp = self._logistic(logit)

        return p_tp

    def classify(self, finding: dict[str, Any]) -> tuple[str, float]:
        """
        Classify a finding as KEEP, ESCALATE, or DISMISS.

        Args:
            finding: Dict with keys: rule, severity, pattern_name,
                    evidence, context (and optionally file_path, id)

        Returns:
            (decision, p_tp) where:
            - decision: 'KEEP' | 'ESCALATE' | 'DISMISS'
            - p_tp: model-estimated TP score, not a verified probability
        """
        # Extract features
        features = extract_features(finding)

        # Get probability
        p_tp = self._predict_proba(features)

        # Apply decision policy
        if p_tp >= self.thresholds['keep']:
            decision = 'KEEP'
        elif p_tp < self.thresholds['dismiss']:
            decision = 'DISMISS'
        else:
            decision = 'ESCALATE'

        return decision, p_tp

    def classify_batch(self, findings: list[dict[str, Any]]) -> list[tuple[str, float]]:
        """
        Classify multiple findings.

        Returns list of (decision, p_tp) tuples.
        """
        return [self.classify(f) for f in findings]

    def get_gate_info(self, finding: dict[str, Any]) -> dict[str, Any]:
        """
        Get detailed gate information for a finding.

        Returns dict with decision, probability, features, etc.
        """
        features = extract_features(finding)
        p_tp = self._predict_proba(features)
        decision, _ = self.classify(finding)

        return {
            'decision': decision,
            'p_tp': round(p_tp, 4),
            'thresholds': self.thresholds,
            'top_features': self._get_top_features(features, top_k=5)
        }

    def _get_top_features(self, features: dict[str, float], top_k: int = 5) -> list[dict]:
        """Get top contributing features for a finding."""
        # Scale features
        scaled = self._scale_features(features)

        # Compute contribution: coef * scaled_value
        contributions = []
        for i, name in enumerate(self.feature_names):
            contrib = self.coefficients[i] * scaled[i]
            contributions.append({
                'name': name,
                'value': round(features.get(name, 0.0), 3),
                'contribution': round(contrib, 3),
                'direction': '+TP' if contrib > 0 else '-TP'
            })

        # Sort by absolute contribution
        contributions.sort(key=lambda x: abs(x['contribution']), reverse=True)

        return contributions[:top_k]
