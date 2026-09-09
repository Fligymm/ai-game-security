import numpy as np

from cv_agent.analytics.sequence import TrajectorySequenceEncoder
from cv_agent.analytics.trajectory_schema import TrajectorySession


def session(**kwargs):
    defaults = dict(session_id="s", source="human", target_distance_px=10, target_size_px=2, reaction_time_ms=0)
    defaults.update(kwargs)
    return TrajectorySession(**defaults)


def test_padding_and_mask():
    encoded, mask = TrajectorySequenceEncoder(3).encode_with_mask(session(timestamps=[1, 2], x=[1, 2], y=[0, 0], dx=[1, 1], dy=[0, 0]))
    assert encoded.shape == (3, 8) and mask.tolist() == [True, True, False]
    assert np.all(encoded[2] == 0)


def test_empty_and_zero_motion_are_finite():
    encoder = TrajectorySequenceEncoder(2)
    assert encoder.encode(session()).shape == (2, 8)
    data = encoder.encode(session(timestamps=[1], x=[0], y=[0], dx=[0], dy=[0]))
    assert np.isfinite(data).all()
