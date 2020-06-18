"""This module provides utility functions for loading, updating, and normalizing model 
specifications. Typically, an application should use only :meth:`load_model` to load files, but the
other functions are also exposed.

Unless stated otherwise, all functions here modify the passed model directly and only return it for
convenience.

This submodule may also be called (e.g. with ``python3 -m ablinfer.model``) to update and normalize
model specification files.
"""

from .update import update_model
from .normalize import load_model, normalize_model, update_normalize_model
from .config import normalize_model_config
