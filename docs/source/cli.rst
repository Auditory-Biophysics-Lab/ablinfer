CLI Interface
=============

.. module:: ablinfer.cli

The CLI module provides a basic CLI interface for dispatching to ABLInfer models, either to a local Docker instance or to an ABLInfer server. This module is typically invoked using ``python3 -m ablinfer.cli <model file>``. The available command-line parameters are auto-generated from the contents of the model file; to see the available parameters, run ``python3 -m ablinfer.cli <model file> -h``.
