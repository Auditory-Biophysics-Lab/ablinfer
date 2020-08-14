Processing Module
=================

.. module:: ablinfer.processing

This module contains the logic for registering and dispatching to pre/post-processing functions during a run. It currently defines no actual processing functions: a couple have been defined in :py:mod:`ablinfer.slicer.processing`. Of primary interest is the method for defining new processing functions. The general format of a processing function is:

.. code-block:: python

   @register_processing(
       typ = "input", ## Which type this function is: "input" (pre), "output" (post), or None (both)
       name = "the_operation_name", 
       types = ("segmentation", "volume",), ## What input/output types this is valid for
       actions = {
           None: { ## Default action if the model doesn't provide one
               "param1": { ## Same structure as the model specification parameters
                   "name": "Parameter 1",
                   "type": "int",
                   "min": 0,
                   "max": 10,
                   "default": 5,
               },
               ...
           },
           "action1": {...}, ## Named action
       }
   )
   def operation(op, op_config, node, node_config, model, model_config):
       ## Your code here, you don't need to return anything

Note that the ``actions`` section of ``register_processing`` is not required, though it is recommended: if present, model config normalization can use default values of missing parameters. If not, ABLInfer has no idea what your processing function's parameters and actions are supposed to be, so you're on your own for validating and normalizing user input. This behaviour is (lazily) used in the Slicer Segmentation Editor function (:py:func:`ablinfer.slicer.processing.seged`) to avoid gathering/formatting the bevy of segmentation editor actions/parameters.

The ``op`` parameter is the mapping from the model specification corresponding to this processing action, ``op_config`` is the corresponding section in the model config, ``node`` is the *value* of the node that this action is on, ``node_config`` is its correspoding model config section (i.e. ``node = node_config["value"]``), ``model`` is the entire model specification, and ``model_config`` is the entire model config. You may retrieve the desired action as ``op["action"]`` (if given). If possible, processing functions should avoid using ``model`` and ``model_config``.

.. autofunction:: register_processing

.. autofunction:: dispatch_processing
