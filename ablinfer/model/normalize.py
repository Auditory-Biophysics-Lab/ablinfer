#!/usr/bin/env python3

from collections.abc import Collection as ABCCollection
from collections.abc import Mapping as ABCMapping
from collections import OrderedDict as OD
import json
import logging
from numbers import Number
from typing import Mapping, Optional, Collection, Union, IO, Tuple, Dict, Set, Any
from .update import __version__, update_model

def get_origin(t):
    return t.__origin__ if hasattr(t, "__origin__") else t

def get_args(t):
    return t.__args__ if hasattr(t, "__args__") else ()

def normalize_model(model: Mapping, processing: bool = False):
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
        origin = get_origin(t)
        args = get_args(t)
        if origin == Union:
            if None in args and v is None:
                return True
            return any((check_rec(v, a) for a in args))
        elif origin in (Collection, ABCCollection):
            if args:
                return isinstance(v, Collection) and all((check_rec(i, args[0]) for i in v))
            return isinstance(v, Collection) 
        elif origin in (Mapping, ABCMapping):
            if args:
                return isinstance(v, Mapping) and all((isinstance_w(i, args[0]) and isinstance_w(j, args[1]) for i, j in v.items()))
            return isinstance(v, Mapping)
        return isinstance_w(v, t)

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

            optional = (get_origin(t) == Union) and (type(None) in t.__args__)

            if not optional and k not in d:
                raise ValueError("Missing required field %s" % '/'.join(fragment+(k,)))
            elif optional and k not in d:
                logging.warning("Missing optional field %s" % '/'.join(fragment+(k,)))
                if isinstance(c, bool):
                    d[k] = c
                elif c is not None:
                    d[k] = c()
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
        "inputs": Mapping,
        "params": (Optional[Mapping], OD),
        "outputs": Mapping,
        "order": Optional[Collection],
    }
    simple_verify(model, spec)

    params: Set[str] = set()
    part_spec = {
        "name": str,
        "description": str,
        "flag": str,
        "extension": str,
        "type": str,
        "pre": (Optional[Collection], list),
    }

    type_spec = {
        "volume": {
            "labelmap": (Optional[bool], False),
        },
        "segmentation": {
            "labelmap": (Optional[bool], False),
            "master": Optional[str],
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
            if name == "params" and typ not in ("int", "float", "bool", "enum"):
                raise ValueError("Invalid %s type %s" % (name, repr(typ)))
            elif name in ("outputs", "inputs") and typ not in ("volume", "segmentation"):
                raise ValueError("Invalid %s type %s" % (name, repr(typ)))
            simple_verify(v, type_spec[typ], fragment=(name, k), warn_extra=False)
            if typ == "enum":
                if not isinstance(v["enum"], Mapping):
                    v["enum"] = OD(((i, i) for i in v["enum"]))

            if name != "params":
                sname = "pre" if name == "inputs" else "post"
                for n, sec in enumerate(v[sname]):
                    simple_verify(sec, process_spec, fragment=(name, k, sname, str(n)))
                    if sec["status"] not in ("required", "suggested", "optional"):
                        raise ValueError("Invalid status %s for %s" % (repr(sec["status"]), '/'.join((name, k, sname, str(n)))))

    verify_part("inputs")

    del part_spec["pre"]
    part_spec["post"] = (Optional[Collection], list)
    verify_part("outputs")

    del part_spec["post"]
    del part_spec["extension"]
    verify_part("params")

    return model

def load_model(f: Union[str, IO], fp: bool = True, normalize: bool = True) ->  Tuple[Dict, bool]:
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
