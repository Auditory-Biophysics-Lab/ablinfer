.. ABLInfer documentation master file, created by
   sphinx-quickstart on Fri Jun 12 16:55:01 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to ABLInfer's Documentation!
====================================

ABLInfer is a Python library and command-line tool based on `DeepInfer <http://www.deepinfer.org>`_ for dispatching medical images to segmentation and registration toolkits, primarily aimed at using Docker containers for automated, deep-learning based segmentation.

To create a new model for use with ABLInfer, first follow :ref:`docker-image` to create and deploy your model's Docker image, then construct a model specification for it by following the :ref:`model-reference` page. Once finished, users can use your model by pulling the Docker image and downloading the model specification. 

.. toctree::
   :maxdepth: 1
   :caption: User Guide:
   
   configuring_docker
   docker_image
   model_ref
   slicer_processing
   model_config
   inferserver
   cli

.. toctree::
   :maxdepth: 1
   :caption: API:

   base
   docker
   remote
   slicer
   model
   processing

.. toctree::
   :maxdepth: 1
   :caption: Developers:

   


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
