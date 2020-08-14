Slicer Processing Module
========================

.. module:: ablinfer.slicer.processing

This module defines some processing functions for use in (and requiring) 3DSlicer. As such, these functions must be imported manually when desired, using 

.. code-block:: python
   
   import ablinfer.slicer.processing

Currently, two processing functions are provided. 

``"render_3d"``
"""""""""""""""
This function takes a single parameter, ``"smoothing"``, and renders the target segmentation in 3D. 

``"seged"``
"""""""""""
This function provides complete access to the 3DSlicer Segmentation Editor, though it's not particularly friendly.The actions correspond to the active effects of the segmentation editor using the same names: the string action is passed directly to the segmentation editor. Typically, determining the parameter names will require some searching and some trials. The best place to look is likely the `Slicer Segment Editor Python modules <https://github.com/Slicer/Slicer/tree/master/Modules/Loadable/Segmentations/EditorEffects/Python>`_; the ``SegmentEditor*Effect.py`` files are relatively friendly. The action is usually found in the ``__init__`` method as ``scriptedEffect.name`` and the default values/available parameters are usually in the ``setMRMLDefaults`` method. 

For example, to remove all islands but the largest from all segments, the processing section in the model specification would be (note the capitalization in ``action`` and ``params``):

.. code-block:: json

   {
       "name": "Island Removal",
       "...",
       "operation": "seged",
       "action": "Islands",
       "targets": [],
       "params": {
           "Operation": "KEEP_LARGEST_ISLAND",
           "MinimumSize": 1
       }
   }

(NB: despite ``MinimumSize`` being uneditable in Slicer [at the time of this writing], it does actually impact island removal).
