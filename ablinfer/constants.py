"""This module contains various constants."""

import enum

class DispatchStage(enum.Enum):
    Initial = 0
    Validate = 1
    Preprocess = 2
    Save = 3
    Run = 4
    Load = 5
    Postprocess = 6
