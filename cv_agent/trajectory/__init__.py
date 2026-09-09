"""Aim, camera, and target-tracking trajectory generation."""

from .paths import (
    GENERATORS,
    Trajectory,
    apply_lab_perturbation,
    generate,
    lab_modulate,
    smoothness_features,
)
from .catalog import (
	TRAJECTORY_PROFILES,
	TrajectoryFamily,
	TrajectoryProfile,
	classify_trajectory,
	get_trajectory_profile,
	trajectory_catalog,
	trajectory_groups,
)

__all__ = [
	"GENERATORS",
	"TRAJECTORY_PROFILES",
	"Trajectory",
	"TrajectoryFamily",
	"TrajectoryProfile",
	"classify_trajectory",
	"generate",
	"apply_lab_perturbation",
	"lab_modulate",
	"get_trajectory_profile",
	"smoothness_features",
	"trajectory_catalog",
	"trajectory_groups",
]
