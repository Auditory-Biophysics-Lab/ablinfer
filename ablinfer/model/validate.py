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
import logging
import re
from typing import Tuple, Callable, IO, Dict, Union

__version__ = "1.1"

_UPDATES = {}
def register(s: str) ->  Callable:
    """Register an update function."""
    def reg_inner(f: Callable[[Dict], Dict]) ->  Callable[[Dict], Dict]:
        if s in _UPDATES:
            raise ValueError("Already registered a helper for v%s" % s)
        _UPDATES[s] = f

        return f
    return reg_inner

@register("deepinfer")
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

@register("1.0")
def update_1_0(model):
    model["json_version"] = "1.1"
    if "website" not in model:
        model["website"] = ""
    if "brief_description" in model:
        del model["brief_description"]

    return model

def update(model: Dict, updated: bool = False) ->  Tuple[Dict, bool]:
    """Update a model to the newest version.

    @returns the updated model and a boolean indicating whether an update was performed
    """
    if "json_version" in model:
        v = model["json_version"]

        if v > __version__:
            raise ValueError("Model version %s is too new (this version is %s)" % (v, __version__))
        elif v == __version__:
            return model, updated
    else:
        v = "deepinfer"

    if v not in _UPDATES:
        raise ValueError("I don't know how to update v%s" % v)

    nm = _UPDATES[v](model)

    return update(nm)[0], True

def load_model(f: Union[str, IO], fp: bool = True) ->  Tuple[Dict, bool]:
    """Load a model.

    @param f the file or string to load from
    @param fp whether f is a file-like object or a string

    @returns the updated model and a boolean indicating whether an update was performed
    """
    if fp:
        inp = json.load(f, object_pairs_hook=OD)
    else:
        inp = json.loads(f, object_pairs_hook=OD)

    return update(inp)

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        sys.stderr.write("Update a model file to the latest version.\nUsage: %s <input model> <output file>\n" % sys.argv[0])

    with open(sys.argv[1], 'r') as f, open(sys.argv[2], 'w') as of:
        json.dump(load_model(f)[0], of, indent=4)
