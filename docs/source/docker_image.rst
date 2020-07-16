.. _docker-image:

Creating a Docker Image
=======================

This document assumes basic familiarity with Docker concepts and how to create a Docker image; any Docker tutorial will provide this. The `Dockerfile Best Practices <https://docs.docker.com/develop/develop-images/dockerfile_best-practices>`_ page is also very helpful.

The first step in deploying a model is to create a Docker image for that model, containing all the necessary dependencies and providing a command-line interface to interact with the model. 

To start, create a new folder for your image and create ``Dockerfile`` inside it, which will describe the image. Usually, new Docker images will be based off of other images; in the case of TensorFlow and other ML projects with challenging dependencies, they will distribute images on `DockerHub <https://hub.docker.com>`_. Thus, the first line of the Dockerfile will typically be:

.. code-block:: Dockerfile

   FROM sourceproject/sourceimage:sometag

Projects usually offer a variety of Docker images based on different operating systems like Ubuntu or Alpine. Ubuntu is larger but tends to be much better supported, whereas Alpine is highly optimized for size (both on disk and in RAM). This is a concern when running hundreds of containers, but typically only a few will be needed at any given time for ML containers; Ubuntu is the usual choice. 

After choosing the source image, the next step is to install any remaining dependencies for your model. A good way to test this is to run the source image interactively, install the dependencies by hand, then copy those commands into the Dockerfile. This can be done by running

.. code-block:: sh

   docker run -it --entrypoint /bin/bash sourceproject/sourceimage:sometag

which will provide an interactive session in the container (if ``/bin/bash`` doesn't exist on the image, replace it with ``/bin/sh``). Commands can be added to the Dockerfile using the ``RUN`` directive:

.. code-block:: Dockerfile 

   RUN some-command arg1 arg2

Typical commands to run are ``apt`` (for Ubuntu-based images) and ``python -m pip``. To keep the image small, it is recommended to clear any cached packages and indexes after running these commands. Official Ubuntu images are supposed to clear ``apt`` cache automatically, but it can be done manually via:

.. code-block:: Dockerfile

   RUN apt-get clean
   RUN rm -rf /var/lib/apt/lists/*

Likewise for ``pip``; in the case of ``pip >= 20.1``, this can be done using 

.. code-block:: Dockerfile

   RUN pip cache purge

Otherwise, adding the flag ``--no-cache-dir`` to each ``pip install`` will fix it. 

The ``COPY`` directive can be used to copy local files and directories into the image, which is typically used to copy your model into the image. The behaviour is similar to ``cp -r`` on Unix systems. Note that containers may be run as any user: typically, you will want to set permissions on copied files to something permissive, e.g.

.. code-block:: Dockerfile

   COPY somedir /var/somedir
   RUN chmod -R g+rX,o+rX /var/somedir

to give all users read and (conditional) execute permissions on the copied file/directory. 

The last component is the entrypoint for the image. This is the command that is executed when the image is run, unless overriden by ``--entrypoint`` as done earlier. This can be any program or file that the image is able to execute.

.. code-block:: Dockerfile

   ENTRYPOINT ["/path/to/entrypoint"]

Once the image is built and tested, it must be deployed. For small deployments and testing, the simple method of exporting and importing the image suffices:

.. code-block:: sh

   ## On the source machine
   docker save yourproj/yourimage:sometag > yourimage.tar
   
   ## Copy the tar file to the deployment machine, then run
   docker import yourimage.tar

For larger and public deployments, the usual means is `DockerHub <https://hub.docker.com>`_. Create an account there and follow the tutorial (replacing the tutorial's image name with your own) to deploy the image. The image can now be retrieved from any machine by running

.. code-block::

   docker pull yourproj/yourimage:sometag

The next step in deployment is to create the model specification: :ref:`model-reference`.
