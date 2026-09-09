"""Offline inference for persisted trajectory classification models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .features import TrajectoryFeatureExtractor
from .trajectory_schema import TrajectorySession


class TrajectoryDetector:
    """Load a baseline model bundle and classify one trajectory session."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.bundle: dict[str, Any] | None = None
        if model_path is not None:
            self.load_model(model_path)

    def load_model(self, model_path: str | Path) -> "TrajectoryDetector":
        bundle = joblib.load(Path(model_path))
        required = {"model", "imputer", "scaler", "feature_names", "class_mapping"}
        if not isinstance(bundle, dict) or not required.issubset(bundle):
            raise ValueError("invalid baseline detector model bundle")
        self.bundle = bundle
        return self

    def predict_session(self, session: TrajectorySession) -> dict[str, Any]:
        if self.bundle is None:
            raise RuntimeError("no model loaded; call load_model() first")
        features = TrajectoryFeatureExtractor().extract(session)
        feature_names = list(self.bundle["feature_names"])
        vector = np.asarray([[float(features.get(name, np.nan)) for name in feature_names]], dtype=np.float64)
        transformed = self.bundle["scaler"].transform(self.bundle["imputer"].transform(vector))
        model = self.bundle["model"]
        probabilities = model.predict_proba(transformed)[0]
        classes = [int(value) for value in model.classes_]
        mapping = self.bundle["class_mapping"]
        probability_distribution = {
            str(mapping.get(str(label), label)): float(probability)
            for label, probability in zip(classes, probabilities)
        }
        predicted_label = classes[int(np.argmax(probabilities))]
        predicted_name = str(mapping.get(str(predicted_label), predicted_label))
        return {
            "prediction": predicted_name,
            "predicted_label": predicted_label,
            "probabilities": probability_distribution,
            "features": features,
        }


__all__ = ["TrajectoryDetector"]
