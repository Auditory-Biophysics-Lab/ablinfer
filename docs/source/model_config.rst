Model Configuration Reference
=============================

The model configuration object is passed to the :meth:`ablinfer.DispatchBase.run` (and its implementations) and provides all of the per-run configuration. The structure is based on the model specification (see :ref:`model-reference`) for that model. The object consists of a mapping with three fields, corresponding to the ones in the model specification:

.. code-block:: json
   
   {
       "inputs": {"..."},
       "params": {"..."},
       "outputs": {"..."}
   }

Each of the three sections has the same fields as in the specific model specification. Each field maps to an object containing at least the ``value`` field, which maps to its actual value. Using the GPU count example, the model specification is:

.. code-block:: json

   {
       "...",
       "params": {
           "gpus": {
               "name": "GPU Count",
               "description": "The number of GPUs to use.",
               "flag": "--gpus=",
               "type": "int",
               "default": -1,
               "min": -1,
               "max": 16
           },
           "...",
       },
       "..."
   }

And the corresponding model configuration for using 3 GPUs would be:

.. code-block:: json

   {
       "...",
       "params": {
           "gpus": {
               "value": 3
           },
           "...",
       },
       "..."
   }

For parameters, if the configuration is using the default value given in the model specification then it can be omitted.

Unlike parameters, inputs and outputs must always be included in the model configuration. As well, the actual format of the ``value`` field **depends on the specific implementation:** for instance, the Docker implementation requires the ``value`` to be the location of the file on the host system's disk, whereas the Slicer implementation requires the ``value`` to be a Slicer node.

Inputs and outputs have the additional ``pre`` or ``post`` list, as appropriate. Either the field must be omitted or it must contain an entry for each available processing operation in the specification. For example, the following model specification:

.. code-block:: json

   {
       "...",
       "inputs": {
           "...",
           "input2": {
               "name": "Segmentation Input",
               "description": "Please select the initial segmentation.",
               "...",
               "pre": [
                   {
                       "name": "Island Removal",
                       "description": "Remove all islands",
                       "status": "suggested",
                       "locked": true,
                       "operation": "seged",
                       "action": "Islands",
                       "targets": [1, 2, 4],
                       "params": {
                           "Operation": "KEEP_LARGEST_ISLAND",
                           "MinimumSize": "1"
                       }
                   },
                   "...",
               ]
           },
           "...",
       },
       "..."
   }

would have the model configuration:

.. code-block:: json

   {
       "...",
       "inputs": {
           "...",
           "input2": {
               "value": "...", 
               "pre": [
                   {
                       "enabled": true,
                       "params": {
                           "Operation": "KEEP_LARGEST_ISLAND",
                           "MinimumSize": "1"
                       }
                   },
                   "...",
               ]
           },
           "...",
       },
       "..."
   }

Note that like parameters, if the default value for a processing parameter (e.g. ``Operation`` and ``MinimumSize`` above), it may be omitted from the model configuration.

A Complete Configuration Example
--------------------------------

Using the model specification example (see :ref:`model-example`), the model configuration would be:

.. code-block:: json

   {
       "inputs": {
           "input_vol": {
               "value": "./input_vol.nii",
               "pre": []
           },
           "input_seg": {
               "value": "./input_seg.nii",
               "pre": [
                   {
                       "enabled": true,
                       "params": {
                           "Operation": "KEEP_LARGEST_ISLAND",
                           "MinimumSize": "1"
                       }
                   }
               ]
           }
       },
   
       "params": {
           "gpus": {
               "value": -1
           },
           "accuracy": {
               "value": 1
           },
           "verbose": {
               "value": true
           }
       },
   
       "outputs": {
           "output_seg": {
               "value": "./output_seg.nii.gz",
               "post": [
                   {
                       "enabled": true,
                       "params": {
                           "Operation": "KEEP_LARGEST_ISLAND",
                           "MinimumSize": "1"
                       }
                   },
                   {
                       "enabled": true,
                       "params": {
                           "smoothing": 0.314
                       }
                   }
               ]
           }
       }
   }
