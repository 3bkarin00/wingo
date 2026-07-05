"""Config validation error codes.

Every config rejection carries one of these codes (never just free-text) so
gates and API clients can match on the code rather than parsing messages.
"""
from enum import Enum


class ConfigErrorCode(str, Enum):
    DEVICE_WINDOW_OVERLAP = "device_window_overlap"
    DEVICE_NOT_SEGMENT_CONTAINED = "device_not_segment_contained"
    TE_HINGE_TOO_FAR_FORWARD = "te_hinge_too_far_forward"
    LE_HINGE_TOO_FAR_AFT = "le_hinge_too_far_aft"
    GAP_BELOW_TOLERANCE = "gap_below_tolerance"
    SANDWICH_STACK_EXCEEDS_THICKNESS = "sandwich_stack_exceeds_thickness"


class ConfigValidationError(ValueError):
    """Raised by cross-field validators with an actionable, coded message."""

    def __init__(self, code: ConfigErrorCode, message: str):
        self.code = code
        super().__init__(f"[{code.value}] {message}")
