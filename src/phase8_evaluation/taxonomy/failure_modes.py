from enum import StrEnum


class FailureMode(StrEnum):
    MISSING_EXPECTED_PARAMETER = "missing_expected_parameter"
    PARAMETER_ERROR_ABOVE_TOLERANCE = "parameter_error_above_tolerance"
    CROSS_TENANT_EVALUATION = "cross_tenant_evaluation"
    SCENE_IDENTITY_MISMATCH = "scene_identity_mismatch"
