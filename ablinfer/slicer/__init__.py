"""This module provides functions and classes for interfacing with 3DSlicer.

When running in 3DSlicer, this module should be explictly imported to access the custom pre/post-
processing functions it provides.
"""

from .dispatchslicer import SlicerDispatchDocker, SlicerDispatchMixin, SlicerDispatchRemote
from .processing import __name__ as _
