#!/usr/bin/env python3

from collections.abc import Collection as ABCCollection
from collections.abc import Mapping as ABCMapping
from collections import OrderedDict as OD
import json
import logging
from numbers import Number
from typing import Mapping, Optional, Collection, Union, IO, Tuple, Dict, Set, Any
from .typing_shim import get_origin, get_args
import collections
from .update import __version__, update_model
from ..processing import processing_ops

def get_origin_w(tp):
    o = get_origin(tp)
    return o if o is not None else tp

def normalize_model(model: Mapping, processing: bool = False) -> Mapping:
    """Normalize the given model. 

    Also validates what fields it can on the model.

    :param model: The model to normalize.
    :param processing: Whether or not to parse in detail the processing operations.
    """
    if model["json_version"] != __version__:
        raise ValueError("Can only normalize v%s models, please update it first" % __version__)

    def isinstance_w(a, t):
        if isinstance(t, Collection):
            if Any in t:
                return True
            return isinstance(a, t)
        if t == Any:
            return True
        return isinstance(a, t)

    def check_rec(v, t):
        origin = get_origin_w(t)
        args = get_args(t)
        if origin == Union:
            if None in args and v is None:
                return True
            for a in args:
                if a is None:
                    continue
                ret = check_rec(v, a)
                if ret:
                    return True
            return False
            #return any((check_rec(v, a) for a in args if a is not None))
        elif origin in (Collection, ABCCollection):
            if args:
                return isinstance(v, ABCCollection) and all((check_rec(i, args[0]) for i in v))
            return isinstance(v, ABCCollection) 
        elif origin in (Mapping, ABCMapping):
            if args:
                return isinstance(v, ABCMapping) and all((isinstance_w(i, args[0]) and isinstance_w(j, args[1]) for i, j in v.items()))
            return isinstance(v, Mapping)
        return isinstance_w(v, origin)

    def simple_verify(d, spec_part, fragment=(), warn_extra=True):
        if warn_extra:
            for k in d:
                if k not in spec_part:
                    logging.warning("Extraneous field %s" % '/'.join(fragment+(k,)))
        for k, t in spec_part.items():
            if isinstance(t, Collection) and not isinstance(t, Mapping):
                t, c = t
            else:
                c = None

            optional = (get_origin_w(t) == Union) and (type(None) in t.__args__)

            if not optional and k not in d:
                raise ValueError("Missing required field %s" % '/'.join(fragment+(k,)))
            elif optional and k not in d:
                logging.warning("Missing optional field %s" % '/'.join(fragment+(k,)))
                if callable(c):
                    d[k] = c()
                elif c is not None:
                    d[k] = c
            elif isinstance(t, Mapping): ## Recurse
                simple_verify(d[k], t, fragment=fragment+(k,), warn_extra=warn_extra)
            elif not check_rec(d[k], t):
                raise ValueError("Improper type for %s" % '/'.join(fragment+(k,)))

    ## All of these specs indicate the structure of the object and have the following rules
    ## - Each string name maps to a type, a duple, or a mapping
    ## - If mapped to a mapping, then the verification recurses
    ## - If mapped to a type, the value is checked to see if it's that type
    ## - If mapped to a type and the type is Optional[...], then a missing value only triggers a 
    ##   warning, not an exception
    ## - If mapped to a tuple, the first element is the type and the second is what should be used 
    ##   to populate the value if it's missing (only used if the type is Optiona[...])
    ## - If mapped to a tuple, the second element is either a callable, a boolean, or None; in the 
    ##   latter two cases, missing values are set to the given literal and in the former they are 
    ##   set to the result of the callable (with no arguments)

    ## Check the outer layer
    spec = {
        "json_version": str,
        "id": str,
        "type": str,
        "name": str,
        "organ": str,
        "task": str,
        "status": str,
        "modality": str,
        "version": str,
        "description": Optional[str],
        "website": Optional[str],
        "maintainers": (Optional[Collection[str]], list),
        "citation": Optional[str],
        "docker": {
            "image_name": str,
            "image_tag": str,
            "data_path": str,
        },
        "inputs": ABCMapping,
        "params": (Optional[ABCMapping], OD),
        "outputs": ABCMapping,
        "order": Optional[ABCCollection],
    }
    simple_verify(model, spec)

    if not model["id"].isidentifier():
        raise ValueError("Model ID must be a valid Python identifier")

    params: Set[str] = set()
    part_spec = {
        "name": str,
        "description": str,
        "flag": str,
        "extension": str,
        "type": str,
        "pre": (Optional[ABCCollection], list),
    }

    type_spec = {
        "volume": {
            "labelmap": (Optional[bool], False),
        },
        "segmentation": {
            "labelmap": (Optional[bool], False),
            "master": Optional[str],
            "colours": (Optional[Mapping[str, Any]], OD),
            "names": (Optional[Mapping[str, str]], OD),
        },
        "int": {
            "min": (Optional[Number], -2147483648),
            "max": (Optional[Number], 2147483647),
            "default": Number,
        },
        "float": {
            "min": (Optional[Number], -3.40282e+038),
            "max": (Optional[Number], 3.40282e+038),
            "default": Number,
        },
        "bool": {
            "default": bool,
        },
        "string": {
            "default": str,
        },
        "enum": {
            "enum": Union[Collection[str], Mapping[str, str]],
            "default": str,
        },
    }

    process_spec = {
        "name": str,
        "description": str,
        "status": str,
        "locked": (Optional[bool], False),
        "operation": str,
        "action": Optional[str],
        "targets": Optional[Collection[int]],
        "params": Mapping[str, Any],
    }

    def verify_part(name):
        cname = name.title()
        for k, v in model[name].items():
            if k in params:
                raise ValueError("Names must be unique (%s is already used)" % repr(k))
            elif not isinstance(k, str):
                raise ValueError("%s name %s must be a string" % (cname, repr(k)))
            elif not k.isidentifier():
                raise ValueError("%s name %s must be a valid Python identifier" % (cname, repr(k)))
            params.add(k)
            simple_verify(v, part_spec, fragment=(name, k), warn_extra=False)

            typ = v["type"]
            if name == "params" and typ not in ("int", "float", "bool", "enum", "string"):
                raise ValueError("Invalid %s type %s" % (name, repr(typ)))
            elif name in ("outputs", "inputs") and typ not in ("volume", "segmentation"):
                raise ValueError("Invalid %s type %s" % (name, repr(typ)))
            simple_verify(v, type_spec[typ], fragment=(name, k), warn_extra=False)
            if typ == "enum":
                if not isinstance(v["enum"], Mapping):
                    v["enum"] = OD(((i, i) for i in v["enum"]))
            elif typ == "segmentation":
                if "colours" not in v:
                    v["colours"] = OD()
                for colourk, colourv in v["colours"].items():
                    if not isinstance(colourv, Collection[Number]) or len(colourv) not in (3, 4):
                        raise ValueError("Segmentation colours must be 3- or 4-element arrays of floats, not \"%s\"" % repr(colourv))
                    elif len(colourv) == 3:
                        ## Fill in opacity
                        v["colours"][colourk] = (*colourv, 1)
                    for colour in colourv:
                        if colour < 0 or colour > 1:
                            raise ValueError("Invalid segementation colour %s, must be a float on [0,1]" % repr(colour))

            if name != "params":
                sname = "pre" if name == "inputs" else "post"
                if sname not in v:
                    v[sname] = []
                for n, sec in enumerate(v[sname]):
                    process_spec_this = process_spec.copy()
                    if sec["operation"] in processing_ops[name[:-1]]:
                        psec = processing_ops[name[:-1]][sec["operation"]][2]
                        if psec is not None:
                            action = sec["action"] if "action" in sec else None
                            if action in psec or None in psec:
                                if action in psec:
                                    act = psec[action]
                                else:
                                    logging.info("Unknown %sprocessing action %s for %s, using default" % (sname, action, sec["operation"]))
                                    act = psec[None]

                                if act:
                                    process_spec_this["params"] = {param_name: (Optional[type_spec[param_val["type"]]["default"]], param_val["default"]) for param_name, param_val in act.items()}
                            else:
                                logging.warning("Unknown %sprocessing action %s for %s, skipping" % (sname, action, sec["operation"]))
                    else:
                        logging.warning("Unknown %sprocessing operation %s, skipping" % (sname, sec["operation"]))
                    simple_verify(sec, process_spec_this, fragment=(name, k, sname, str(n)))
                    if sec["status"] not in ("required", "suggested", "optional"):
                        raise ValueError("Invalid status %s for %s" % (repr(sec["status"]), '/'.join((name, k, sname, str(n)))))

    verify_part("inputs")

    del part_spec["pre"]
    part_spec["post"] = (Optional[Collection], list)
    verify_part("outputs")

    del part_spec["post"]
    del part_spec["extension"]
    verify_part("params")

    field_set = set((*model["inputs"], *model["params"], *model["outputs"]))
    flag_set = set((
        *(i["flag"] for i in model["inputs"].values()), 
        *(i["flag"] for i in model["params"].values()),
        *(i["flag"] for i in model["outputs"].values()),
    ))
    if "order" in model and model["order"]:
        if len(model["order"]) != len(model["inputs"]) + len(model["params"]) + len(model["outputs"]):
            raise ValueError("Length of order does not match the number of inputs, outputs, and params")
        elif set(model["order"]) != field_set:
            raise ValueError("Order elements must match field names")
    elif ("order" not in model or not model["order"]) and "" in flag_set:
        raise ValueError("Order must be specified if positional arguments are used")


    return model

def update_normalize_model(model: Mapping) -> Tuple[Mapping, bool]:
    """Update and normalize a model.

    :param model: The model to fix.

    :returns: The updated model and a boolean indicating whether an update was performed.
    """
    upd = update_model(model)
    return (normalize_model(upd[0]), upd[1])

def load_model(f: Union[str, IO], fp: bool = True, normalize: bool = True) ->  Tuple[Mapping, bool]:
    """Load a model.

    :param f: The file or string to load from.
    :param fp: Whether f is a file-like object or a string.
    :param normalize: Whether or not to normalize the result.

    :returns: The updated model and a boolean indicating whether an update was performed.
    """
    if fp:
        inp = json.load(f, object_pairs_hook=OD)
    else:
        inp = json.loads(f, object_pairs_hook=OD)

    upd = update_model(inp)
    if normalize:
        upd = (normalize_model(upd[0]), upd[1])

    return upd
