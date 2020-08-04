.. _model-reference:

Model Reference
===============

All models are specified using JSON files. These specifications tell ABLInfer how to interface with the model, what parameters it expects, any pre/post-processing, as well as some helpful metadata for the user. 

The format of model specification files used by ABLInfer is based on the model specifications for DeepInfer, with the notable additions of the standardization of metadata fields and the addition of pre/post-processing blocks.

Throughout the following examples, a line containing ``"..."`` indicates that part of the model specification has been omitted for clarity.

Metadata (``/``)
----------------
.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description
   * - ``json_version``
     - The version of the JSON model format that this model conforms to.
   * - ``type``
     - The type of application to run. Currently, only ``"docker"`` is supported.
   * - ``id``
     - The ID for the model. Must be a valid Python identifier.
   * - ``name``
     - The name of the model, in a human-friendly format.
   * - ``organ``
     - The organ that the model operates on, in a human-friendly format.
   * - ``task``
     - The model's task, e.g. ``"Segmentation"``, ``"Registration"``
   * - ``status``
     - A user-friendly indication of the status of the model, e.g. ``"Testing"``, ``"Production"``
   * - ``modality``
     - The modality of images involved, e.g. ``"CT"``
   * - ``version``
     - The model's version. There is no format enforced here; comparison between versions is done using a Python string comparison
   * - ``description``
     - [Optional] A detailed description of the model.
   * - ``website``
     - [Optional] A website for where users can go for support/more information about the model.
   * - ``maintainers``
     - [Optional] A list of the maintainers of the model, e.g. ``["Some Person (SomeOrg)", "Another Person (AnotherOrg)"]``
   * - ``citation``
     - [Optional] What users should cite if they use this model.

An example of these fields is:

.. code-block:: json

   {
       "json_version": "1.1",
       "type": "docker",

       "name": "Test Segmenter",
       "organ": "Third Hair from the Left",
       "task": "Segmentation",
       "status": "Production",
       "modality": "CT",
       "version": "1.0.1",

       "description": "This is where I would put a great deal of text explaining the function of the model, as it will be displayed when the user selects a model for use. Maybe some instructions or something.",
       "website": "elgoog.com",
       "maintainers": ["Ben Connors (UWO)"],
       "citation": "Paper currently nonexistant",

       "..."
   }

Docker Parameters (``/docker``)
-------------------------------
This section should only be present for ``type="docker"`` models.

.. list-table::
   :widths: 10, 50
   :header-rows: 1
    
   * - Field 
     - Description 
   * - ``image_name``
     - The name of the Docker image to use, e.g. ``alpine``, ``nvidia/cuda``
   * - ``image_tag``
     - The image tag, or ``"latest"`` if there isn't one.
   * - ``data_path``
     - The folder inside the container where the input/output should be written to/read from. This should be world-read/write-able. Use only forward slashes (``/``) in the path, not backward slashes. For most cases ``/tmp`` suffices.

An example of these fields is:

.. code-block:: json

   {
       "...",
       "docker": {
           "image_name": "testimage",
           "image_tag": "latest",
           "data_path": "/tmp"
       },
       "..."
   }

Input Parameters (``/inputs``)
------------------------------
This section defines the inputs for the models. Inputs are volumes, segmentations, and others that must be written to a file to be provided as input; parameters are those values which may be passed as command-line arguments.

The actual ``/inputs`` field should be an object mapping Python-friendly (i.e. they work as a Python variable name) to the specification for that input. Note that the Python-friendly name of the input must be unique among the inputs, outputs, and parameters sections. The available fields on the input objects depend on the type of input; the fields common to all types are:

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description
   * - ``name``
     - A user-friendly (but short) name for the input.
   * - ``description``
     - A longer description of the input. 
   * - ``flag``
     - The flag that will be used to provide the filename of the input to the model, including the leading dash(es). If the flag is ``""`` (the empty string), the filename is passed without a flag. If the flag ends with ``=``, then the filename is passed like ``--flag=thefilename``.
   * - ``extension``
     - The extension to save the file as. This should be something that makes sense for the given type, e.g. ``".nii"`` or ``".nrrd"`` for volumes, and is NOT inferred from the input type.
   * - ``type``
     - The type of input. Currently supported are ``"volume"`` and ``"segmentation"``.
   * - ``pre``
     - [Optional] A list of pre-processing operations (explained later).

An example is:

.. code-block:: json

   {
       "...",
       "inputs": {
           "input1": {
               "name": "Volume Input",
               "description": "Please select the volume to segment.",
               "flag": "-i",
               "extension": ".nrrd",
   
               "type": "volume",
               "...",
               "pre": ["..."]
           },
           "..."
       },
       "..."
   }

Volume Inputs (``type="volume"``)
"""""""""""""""""""""""""""""""""

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description
   * - ``labelmap``
     - Whether or not the volume is a labelmap. Only really meaningful for output volumes.

An example is:

.. code-block:: json

   {
       "...",
       "inputs": {
           "input1": {
               "name": "Volume Input",
               "description": "Please select the volume to segment.",
               "flag": "-i",
               "extension": ".nrrd",
   
               "type": "volume",
               "labelmap": true,
               "..."
           },
           "..."
       },
       "..."
   }

Segmentation Inputs (``type="segmentation"``)
"""""""""""""""""""""""""""""""""""""""""""""

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description
   * - ``labelmap``
     - Whether or not the input is actually a labelmap but should be converted to a segmentation before use. Don't use circular references or Slicer may explode. Note that in most cases this should be set to false, as labelmaps can be loaded directly as segmentations.
   * - ``colours``
     - [Optional] A mapping from label value (typically a string representation of a positive integer) to the desired colour, which is a 3- or 4-tuple of floats on [0,1] corresponding to the segmentation's red, green, blue, and, if desired, opacity (assumed to be 1 if omitted). Not all labels need be present; those labels that aren't added are left with the default colours of whatever software is used.
   * - ``names``
     - [Optional] A mapping from label value (see ``colours``) to a string name for that component.
   * - ``master``
     - [Optional] The name of the master volume for this segmentation (e.g. ``"input1"``, not the friendly name). Note that for Slicer, this field is mandatory for any segmentations requiring pre- or post-processing using the Segment Editor.

An example is:

.. code-block:: json

   {
       "...",
       "inputs": {
           "...",
           "input2": {
               "name": "Segmentation Input",
               "description": "Please select the initial segmentation.",
               "flag": "--seg=",
               "extension": ".nrrd",
   
               "type": "segmentation",
               "labelmap": true,
               "colours": {
                   "2": [0.5, 0.2, 1, 0.5],
                   "4": [1, 0, 0]
               },
               "names": {
                   "3": "The One We Really Care About"
               },
               "master": "input1",
               "..."
           },
           "..."
       },
       "..."
   }

Preprocessing (``/inputs/<input/pre``)
""""""""""""""""""""""""""""""""""""""
The pre-processing section is an optional list of pre-processing operations. The intention of this section (and the output version) is to allow the model to leverage Slicer's functionality to easily add pre- and post-processing to the model. 

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description 
   * - ``name`` 
     - A user-friendly name for the operation.
   * - ``description``
     - A description of what the operation does.
   * - ``status``
     - One of ``"optional"`` (disabled by default but can be enabled, ``"suggested"`` (enabled by default but can be disabled), and ``"required"`` (always enabled).
   * - ``locked``
     - A boolean; if true, the user cannot edit the parameters given in the model specification.
   * - ``operation``
     - The operation to conduct. These are built-in to the specific ABLInfer implementation.
   * - ``action``
     - [Optional] The specific action to conduct. May be required by the operation, or may be ignored.
   * - ``targets``
     - [Optional] For segmentation inputs, this is the list of segments to apply the operation to.
   * - ``params``
     - A mapping from parameter name to its value. See the documentation for the specific operation for the available parameters and their effects.

The available parameters for a processing block's ``params`` field depend on the specific operation; consult its documentation. In general, any parameter that you want the user to be able to modify should be specified, even if its default value will usually suffice.

The following example uses the ``seged`` operation in the Slicer ABLInfer to remove islands from segments 1, 2, and 4 of the segmentation input (note: the default for this operation is to apply it to all segments if ``targets`` is not given or is empty).

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

General Parameters (``/params``)
--------------------------------
These parameters are passed to the model using the command-line, and are typically short things such as the number of GPUs to use, the number of iterations, numerical accuracy, etc. The format of this section is nearly identical to ``/inputs``, though the ``pre`` and ``extension`` fields are omitted as they are useless and the ``default`` field is added. As well, it is an error to specify ``"volume"`` or ``"segmentation"`` as a parameter. The supported parameter types are described below.

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description 
   * - ``default``
     - The default value for the parameter.

Integer/Float Parameters (``type="int"/type="float"``)
""""""""""""""""""""""""""""""""""""""""""""""""""""""
These types replace the myriad of integer and float types used by DeepInfer. They correspond to Python's ``int`` and ``float`` types, which are typically ``long`` and ``double``. 

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description 
   * - ``min``
     - The minimum accepted value. Defaults to the minimum 32-bit value for both types.
   * - ``max``
     - The maximum accepted value. Defaults to the maximum 32-bit value for both types.

An example for picking an integer on ``[-1,16]`` is:

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

An example for picking a float on ``[0,1]`` is:

.. code-block:: json

   {
       "...",
       "params": {
           "...",
           "accuracy": {
               "name": "Accuracy",
               "description": "The numerical accuracy to target.",
               "flag": "-a",
               "type": "float",
               "default": 1,
               "min": 0,
               "max": 1
           },
           "...",
       },
       "..."
   }

String Parameters (``type="string"``)
"""""""""""""""""""""""""""""""""""""
A generic string parameter. This type has no special fields.

Boolean Parameters (``type="bool"``)
""""""""""""""""""""""""""""""""""""
A generic boolean parameter. This type has no special fields. An example is:

.. code-block:: json

   {
       "...",
       "params": {
           "...",
           "verbose": {
               "name": "Verbose",
               "description": "Increase output verbosity.",
               "flag": "-v",
               "type": "bool",
               "default": true
           },
           "...",
       },
       "..."
   }

Enum Parameters (``type="enum"``)
"""""""""""""""""""""""""""""""""
This type provides an enum parameter. The ``default`` field should reference the value of the desired default, not the name.

.. list-table::
   :widths: 10, 50
   :header-rows: 1

   * - Field
     - Description 
   * - ``enum``
     - A description of the accepted values. Two formats are allowed: either a list of values or a mapping of name to value. All involved must be strings, as they will be passed to the command as strings anyways.

An example for picking a colour is:

.. code-block:: json

   {
       "...",
       "params": {
           "...",
           "colour": {
               "name": "Colour",
               "description": "Please select your favourite colour.",
               "flag": "-c",
               "type": "enum",
               "default": "RED",
               "enum": {
                   "Red": "RED",
                   "Blue": "BLUE",
                   "Green": "GREEN",
                   "I'm Wrong": "WRONG"
               }
           },
           "..."
       },
       "..."
   }


Output Parameters (``/outputs``)
--------------------------------
The output section is almost identical to ``/inputs``, with the exception of the ``"pre"`` field being renamed to ``"post"`` on each output. The supported output types are the same as the input types.

Order List (``/order``)
-----------------------
This field is an optional list of the order in which the inputs, outputs, and parameters should be passed to the model, if it's important. If not present, the order is arbitrary. An example would be:

.. code-block:: json

   {
       "...",
       "order": ["input1", "output1", "param1"]
   }

.. _model-example:

A Complete Example
------------------

The following is a complete example of a model, tying together all of the above sections. The model takes as input an input volume and an initial segmentation (whose islands are removed before use), allows the user to choose the number of GPUs used (using the convention that -1 means all), the numerical accuracy, and the verbosity, and returns a final segmentation, which is saved as a labelmap but loaded as a segmentation. Lastly, the output segmentation's islands are removed on all segments and it is rendered in 3D with a specific smoothing factor.

.. code-block:: json

   {
       "json_version": "1.1",
       "type": "docker",

       "name": "Test Segmenter",
       "organ": "Third Hair from the Left",
       "task": "Segmentation",
       "status": "Production",
       "modality": "CT",
       "version": "1.0.1",

       "description": "This is where I would put a great deal of text explaining the function of the model, as it will be displayed when the user selects a model for use. Maybe some instructions or something.",
       "website": "elgoog.com",
       "maintainers": ["Ben Connors (UWO)"],
       "citation": "Paper currently nonexistant",

       "docker": {
           "image_name": "testimage",
           "image_tag": "latest",
           "data_path": "/tmp"
       },

       "inputs": {
           "input_vol": {
               "name": "Volume Input",
               "description": "Please select the volume to segment.",
               "flag": "-i",
               "extension": ".nrrd",
   
               "type": "volume",
               "labelmap": false,
               "pre": []
           },

           "input_seg": {
               "name": "Segmentation Input",
               "description": "Please select the initial segmentation.",
               "flag": "--seg=",
               "extension": ".nrrd",
   
               "type": "segmentation",
               "labelmap": false,
               "colours": {
                   "2": [0.5, 0.2, 1, 0.5],
                   "4": [1, 0, 0]
               },
               "names": {
                   "3": "The One We Really Care About"
               },
               "master": "input_vol",
               "pre": [
                   {
                       "name": "Island Removal",
                       "description": "Remove all islands",
                       "status": "required",
                       "locked": true,
                       "operation": "seged",
                       "action": "Islands",
                       "targets": [1, 2, 4],
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
               "name": "GPU Count",
               "description": "The number of GPUs to use.",
               "flag": "--gpus=",
               "type": "int",
               "default": -1,
               "min": -1,
               "max": 16
           },
           "accuracy": {
               "name": "Accuracy",
               "description": "The numerical accuracy to target.",
               "flag": "-a",
               "type": "float",
               "default": 1,
               "min": 0,
               "max": 1
           },
           "verbose": {
               "name": "Verbose",
               "description": "Increase output verbosity.",
               "flag": "-v",
               "type": "bool",
               "default": true
           },
           "colour": {
               "name": "Colour",
               "description": "Please select your favourite colour.",
               "flag": "-c",
               "type": "enum",
               "default": "RED",
               "enum": {
                   "Red": "RED",
                   "Blue": "BLUE",
                   "Green": "GREEN",
                   "I'm Wrong": "WRONG"
               }
           }
       },
       
       "outputs": {
           "output_seg": {
               "name": "Segmentation Output",
               "description": "Please select where to put the output segmentation.",
               "flag": "",
               "extension": ".nii.gz",
   
               "type": "segmentation",
               "labelmap": true,
               "master": "input_vol",
               "post": [
                   {
                       "name": "Island Removal",
                       "description": "Remove all islands",
                       "status": "suggested",
                       "locked": true,
                       "operation": "seged",
                       "action": "Islands",
                       "targets": [],
                       "params": {
                           "Operation": "KEEP_LARGEST_ISLAND",
                           "MinimumSize": "1"
                       }
                   },
                   {
                       "name": "Show in 3D",
                       "description": "Show the result in 3D",
                       "status": "suggested",
                       "operation": "render_3d",
                       "params": {
                           "smoothing": 0.314
                       }
                   }
               ]
           }
       },

       "order": [
           "gpus",
           "accuracy",
           "verbose",
           "input_vol",
           "colour",
           "input_seg",
           "output_seg"
       ]
   }

The resulting command passed to the model would be something like, assuming default values are used (filenames may change):

.. code-block::

   <model executable> --gpus=-1 --accuracy=1 -v -i /tmp/input_vol.nrrd -c RED --seg=/tmp/input_seg.nrrd output_seg.nii.gz

Please use saner flags and ordering in your model.
