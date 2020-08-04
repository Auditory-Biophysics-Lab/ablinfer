#!/usr/bin/env python3

"""Module for handling model validation and updating.

The main purpose is to ensure that loaded models are valid and that all other functions may assume
that each model conforms to the newest model specification format. Future model specification
formats are indended to be backwards-compatible with old ones, with sane defaults for new fields
added automatically.

Each update function here is intended to update the model from one version to the next. The
functions will then be run in sequence until the model has been brought to the latest version.
This version is determined by the "json_version" field; if absent, the model is assumed to be a
DeepInfer model.

v1.2
- Added the "ID" field
- Added the "colours" and "names" parameters to "segmentation" parameters

v1.1
- Added the "website" field and removed "brief_description"

v1.0
- Unified metadata fields from various DeepInfer models
- Standardize certain fields in the various input/output/parameter types
- Remove the plethora of integer types in favour of min/max values
- Add pre/post-processing functions
- Add more description to each field
"""

from collections import OrderedDict as OD
import json
import hashlib
import logging
import re
from typing import Tuple, Callable, IO, Dict, Union

__version__ = "1.2"
__version__int = tuple((int(i) for i in __version__.split('.')))

_UPDATES = {}
def _register(s: str) ->  Callable:
    """Register an update function."""
    def reg_inner(f: Callable[[Dict], Dict]) ->  Callable[[Dict], Dict]:
        if s in _UPDATES:
            raise ValueError("Already registered a helper for v%s" % s)
        _UPDATES[s] = f

        return f
    return reg_inner

@_register("deepinfer")
def _update_deepinfer(model):
    """Update from the DeepInfer model format."""

    ## DeepInfer's regex for converting CamelCase to a friendly name
    re_camel = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')
    beautify_cc = lambda s: re_camel.sub(r' \1', s)

    inor = lambda d, v, s: d[v] if v in d else s

    ## This is a big one, we create the new model from scratch
    nm = OD((
        ("json_version", "1.0"),
        ("type", "docker"),

        ("name", model["name"]),
        ("organ", inor(model, "organ", "")),
        ("task", inor(model, "task", "")),
        ("status", inor(model, "status", "")),
        ("modality", inor(model, "modality", "")),
        ("version", inor(model, "version", "")),

        ("description", inor(model, "detaileddescription", inor(model, "briefdescription", ""))),
        ("brief_description", inor(model, "briefdescription", "")),
        ("maintainers", inor(model, "maintainers", [])),
        ("citation", inor(model, "citation", "")),

        ("docker", OD((
            ("image_name", model["docker"]["dockerhub_repository"]),
            ("image_tag", model["docker"]["digest"]),
            ("data_path", inor(model, "data_path", "/home/deepinfer/data")),
        ))),

        ("inputs", OD()),
        ("params", OD()),
        ("outputs", OD()),
    ))

    for member in model["members"]:
        name = member["name"]
        iotype = member["iotype"]
        typ = member["type"]
        if typ in ("bool", "int",) and iotype != "parameter":
            logging.info("Converting %s to parameter from %s" % (name, iotype))
            iotype = "parameter"

        if iotype in ("input", "output"):
            if typ == "volume":
                ## Note: itk_type and default are both ignored by DeepInfer for volumes
                nm[iotype+'s'][name] = OD((
                    ("name", beautify_cc(name)),
                    ("description", inor(member, "detaileddescriptionSet", "")),
                    ("flag", "--"+name),
                    ("extension", ".nrrd"),

                    ("type", "volume"),
                    ("labelmap", member["voltype"] == "LabelMap"),
                ))
            elif typ == "point_vec":
                nm[iotype+'s'][name] = OD((
                    ("name", beautify_cc(name)),
                    ("description", inor(member, "detaileddescriptionSet", "")),
                    ("flag", "--"+name),
                    ("extension", ".fcvs"),

                    ("type", "point_vec"),
                ))
            else:
                raise ValueError("Unknown %s type %s" % (iotype, typ))
        elif iotype == "parameter":
            m = OD((
                ("name", beautify_cc(name)),
                ("description", inor(member, "detaileddescriptionSet", "")),
                ("flag", "--"+name),

            ))

            rmap = {
                "uint8_t": (0, 255),
                "int8_t":(-128, 127),
                "uint16_t":(0, 65535),
                "int16_t":(-32678, 32767),
                "uint32_t": (0, 2147483647),
                "uint64_t": (0, 2147483647),
                "unsigned int": (0, 2147483647),
                "int32_t": (-2147483648, 2147483647),
                "int64_t": (-2147483648, 2147483647),
                "int": (-2147483648, 2147483647),
            }

            if typ in ("uint8_t", "int8_t", "uint16_t", "int16_t", "uint32_t", "int32_t", "uint64_t", "int64_t", "unsigned int", "int"):
                m["type"] = "int"
                m["default"] = inor(member, "default", 0)
                minv, maxv = rmap[typ]

                m["min"] = minv
                m["max"] = maxv
            elif typ == "bool":
                m["type"] = "bool"
                m["default"] = (inor(member, "default", "false") == "false")
            elif typ in ("float", "double"):
                m["type"] = "float"
                m["default"] = float(inor(member, "default", 0))
            elif typ == "enum":
                m["type"] = "enum"
                m["enum"] = OD(((i, i) for i in member["enum"]))
                m["default"] = inor(member, "default", member["enum"][0])

    return nm

@_register("1.0")
def update_1_0(model):
    model["json_version"] = "1.1"
    if "website" not in model:
        model["website"] = ""
    if "brief_description" in model:
        del model["brief_description"]

    return model

@_register("1.1")
def update_1_1(model):
    model["json_version"] = "1.2"
    if "id" not in model:
        tid = model["name"].lower().replace(' ', '_').replace('-', '_')
        if not tid.isidentifier():
            tid = "model_" + hashlib.md5(model["name"].encode("utf-8")).hexdigest()
        model["id"] = tid

    return model

def update_model(model: Dict, updated: bool = False) ->  Tuple[Dict, bool]:
    """Update a model to the newest version.

    Note that no verification of fields not affected by the updates is conducted.

    :returns: The updated model and a boolean indicating whether an update was performed.
    """
    if "json_version" in model:
        v = model["json_version"]

        try:
            major, minor = (int(i) for i in v.split('.'))
            v_i = (major, minor)
        except:
            raise ValueError("Model version %s is invalid (should be major.minor)" % v)

        ## Normalize the version, just in case
        v = "%d.%d" % v_i

        if v_i > __version__int:
            raise ValueError("Model version %s is too new (this version is %s)" % (v, __version__))
        elif v == __version__:
            return model, updated
    else:
        v = "deepinfer"

    if v not in _UPDATES:
        raise ValueError("I don't know how to update v%s" % v)

    nm = _UPDATES[v](model)

    return update_model(nm)[0], True
