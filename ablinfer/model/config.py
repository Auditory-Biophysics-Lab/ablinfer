#!/usr/bin/env python3

import logging
from typing import Mapping

def normalize_model_config(model: Mapping, model_config: Mapping) -> Mapping:
    """Normalizes the given model config against the given model.

    The model is assumed to be normalized.

    Note that for processing configuration to be normalized properly, the processing functions must 
    be imported before running this function; e.g. :mod:`ablinfer.slicer.processing` requires 
    dependencies not usually found outside 3DSlicer and so is not imported automatically.

    :param model: The model.
    :param model_config: The model configuration to normalize; this will modify it.
    :returns: The modified model config, for convenience.
    """

    for (s, process) in (("inputs", "pre"), ("outputs", "post")):
        csec = model_config[s]
        for name, spec in model[s].items():
            if name not in csec:
                raise ValueError("Missing %s %s" % (s.rstrip('s'), name))
            sec = csec[name]
            if "value" not in sec:
                raise ValueError("Missing value for %s %s" % (s.rstrip('s'), name))

            if process not in sec:
                sec[process] = [{} for i in range(len(spec[process]))]
            elif sec[process] and len(sec[process]) != len(spec[process]):
                raise ValueError("Either no processing parameters may be given or all must be given in %s/%s" % (s, name))
            
            for p, elem in zip(spec[process], sec[process]):
                defaults = {
                    "enabled": p["status"] in ("required", "suggested"),
                    "params": p["params"].copy()
                }
                if "enabled" not in elem:
                    elem["enabled"] = defaults["enabled"]
                elif p["status"] == "required" and not elem["enabled"]:
                    raise ValueError("Processing operation \"%s\" on %s/%s may not be disabled" % (p["name"], s, name))

                if "params" not in elem:
                    elem["params"] = defaults["params"]
                else:
                    for p, v in defaults["params"].items():
                        if p not in elem["params"]:
                            elem["params"][p] = v

    if "params" not in model_config:
        logging.warning("Missing params section")
        model_config["params"] = {}

    csec = model_config["params"]
    for name, spec in model["params"].items():
        if name not in csec:
            logging.warning("Using default value for params/%s" % name)
            csec[name] = {"value": spec["default"]}
            continue
        sec = csec[name]
        if "value" not in sec:
            sec["value"] = spec["default"]
            continue

        typ = spec["type"]
        if typ in ("int", "float"):
            try:
                if typ == "int":
                    sec["value"] = int(sec["value"])
                else:
                    sec["value"] = float(sec["value"])
            except Exception as e:
                raise ValueError("Invalid value for params/%s: %s" % (name, repr(e)))
            if sec["value"] < spec["min"] or sec["value"] > spec["max"]:
                raise ValueError("Value for params/%s must be on [%d, %d]" % (name, spec["min"], spec["max"]))
        elif typ == "string":
            try:
                sec["value"] = str(sec["value"])
            except Exception as e:
                raise ValueError("Invalid value for params/%s: %s" % (name, repr(e)))
        elif typ == "bool":
            try:
                sec["value"] = bool(sec["value"])
            except Exception as e:
                raise ValueError("Invalid value for params/%s: %s" % (name, repr(e)))
        elif typ == "enum":
            if sec["value"] not in spec["enum"].values():
                raise ValueError("Invalid enum value for params/%s" % name)
        else:
            raise NotImplementedError("Unknown type %s, either the model is invalid for this version or this is a bug" % repr(typ))

    return model_config
