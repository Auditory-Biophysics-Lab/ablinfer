Base Module
===========

.. module:: ablinfer

.. autoclass:: ablinfer.DispatchBase

   .. automethod:: run

   The following functions make up the actual functionality of the class, and at least the abstract
   ones must be overriden in derivative classes.

   .. automethod:: _validate_config
   .. automethod:: _validate_model_config
   .. automethod:: _make_fmap
   .. automethod:: _make_fmap_helper
   .. automethod:: _make_flags
   .. automethod:: _make_command
   .. automethod:: _run_processing
   .. automethod:: _save_input
   .. automethod:: _run_command
   .. automethod:: _load_output
   .. automethod:: _cleanup
   .. automethod:: _cleanup_all

.. autoexception:: ablinfer.DispatchException
