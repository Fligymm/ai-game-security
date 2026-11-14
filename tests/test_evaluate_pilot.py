from __future__ import annotations

from tools.evaluate_pilot import _iou, _match_image, _prf


def test_iou_and_greedy_match() -> None:
    truth = [{"class_id": 0, "xyxy": [0, 0, 10, 10]}]
    predictions = [
        {"class_id": 0, "xyxy": [0, 0, 10, 10], "confidence": 0.9},
        {"class_id": 0, "xyxy": [50, 50, 60, 60], "confidence": 0.8},
    ]

    assert _iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert _iou([0, 0, 10, 10], [50, 50, 60, 60]) == 0.0
    assert _match_image(truth, predictions, 0.5) == {"tp": 1, "fp": 1, "fn": 0}


def test_match_counts_missed_truth() -> None:
    truth = [{"class_id": 1, "xyxy": [0, 0, 10, 10]}]
    assert _match_image(truth, [], 0.5) == {"tp": 0, "fp": 0, "fn": 1}


def test_prf_handles_empty_denominators() -> None:
    assert _prf(0, 0, 0) == {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert _prf(2, 1, 2) == {
        "precision": 2 / 3,
        "recall": 0.5,
        "f1": 2 * (2 / 3) * 0.5 / ((2 / 3) + 0.5),
    }