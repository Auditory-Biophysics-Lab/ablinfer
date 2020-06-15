"""Module for pre/post-processing."""

from typing import Mapping, Callable, Any, Union, Optional, Sequence

_OPS: Mapping[str, Mapping] = {
    "input": {},
    "output": {},
}

def register_processing(typ: Union[str, Sequence[str], None], name: str, types: str, actions: Optional[Mapping]) ->  Callable:
    """Register a processing operation.

    The format of `actions` is:

    {
        None: {...}, ## Default action
        "action1": {...}, ## Named action
        ...
    }

    Each sub-dictionary is of the same form as the "inputs" or "outputs" object in a model JSON
    file, e.g.:

    {
        "param1": {
            "name": "Parameter 1",
            "type": "int",
            "min": 0,
            "max": 10,
            "default": 5,
        },
        ...
    }

    with the exception that any pre/post sections are invalid. The type may be "segmentation" or
    "volume", but these MUST NOT be modified by any processing operations.

    @param typ is either "input", "output", or None, in which case the processing is considered
               valid for both inputs and outputs.
    @param name is the name (not user-friendly) for the action
    @param types is the type of inputs/outputs (e.g. "segmentation", "volume") that this operation
                 is valid for
    @param actions either None or a dictionary describing the types for each action
    """
    if typ is None:
        typ = tuple(_OPS)
    elif isinstance(typ, str):
        typ = (typ,)
    def wrapper(f):
        for t in typ:
            if name in _OPS[t]:
                raise ValueError("Processing function %s/%s already registered" % (t, name))
            _OPS[t][name] = (f, types, actions)

        return f
    return wrapper

def dispatch_processing(op: Mapping, op_config: Mapping, node: Any, node_section: Mapping, model: Mapping, model_config: Mapping, inp: bool = True) ->  None:
    """Dispatch a processing operation.

    @param op the current operation's section in the model
    @param op_config the current operation's config section from the model_config
    @param node the node to operate on (e.g. filename)
    @param node_section the node's section from the model
    @param model the entire model specification
    @param model the entire model config
    @param inp whether or not this is an input
    """
    if inp:
        typ = "input"
    else:
        typ = "output"

    if op["operation"] not in _OPS[typ]:
        raise KeyError("Unknown processing operation %s/%s" % (typ,op["operation"]))

    _OPS[typ][op["operation"]][0](op, op_config, node, node_section, model, model_config)
