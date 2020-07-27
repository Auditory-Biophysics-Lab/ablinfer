.. _inferserver:

InferServer Module
==================

.. module:: ablinfer.inferserver

The InferServer module provides the backend for the :py:class:`ablinfer.remote.DispatchRemote` dispatcher. This server is designed to run on a central server to provide inference capabilities to the local network. The server uses an implementation of :py:class:`ablinfer.docker.DispatchDocker` to launch models using Docker.

Limitations
"""""""""""
No pre/post-processing (*including file conversion*) is done on the server: this is the client's responsibility; since most clients will be coming from 3DSlicer, there are better functions there for doing this anyways. 

This server is designed to serve a *local network*: it has no implementation of authentication or access control. If desired, this should be handled by the web server itself.

Requirements
""""""""""""
The server itself has minimal hardware requirements (anything capable of running a modern Python); most hardware requirements will be dictated by the models you intend to serve. 

As the server is written using Flask, it supports a diverse set of deployment options. See the `Flask documentation on deployment <https://flask.palletsprojects.com/en/1.1.x/deploying/>`_ for details.

Deployment using NGINX + uWSGI
""""""""""""""""""""""""""""""

This section will illustrate an example deployment using NGINX and uWSGI, which is the tested deployment strategy. A basic familiarity with NGINX, a working NGINX server, and a working Docker server (with GPU support, if desired) is assumed. The `ArchWiki page on uWSGI <https://wiki.archlinux.org/index.php/UWSGI#Configuration>` is also helpful for troubleshooting.

The first step is to install the needed dependencies: uWSGI and uWSGI's Python 3 plugin. Depending on your distribution, these may be packaged together or separately. These are typically called ``uwsgi`` and ``uwsgi-plugin-python``, respectively. If you're unfamiliar with Python virtualenvs, install PipEnv as well, either with ``pip install pipenv`` or by installing your distribution's PipEnv package (often ``python-pipenv`` or ``python3-pipenv``)

Once that's finished, install InferServer into a directory of your choice. Where this should be depends on the distribution: typically, ``/srv/inferserver`` suffices. Installation can be done one of two ways: you can either clone ABLInfer's GitHub repository or install it from PyPI. Change into that directory; if installing using GitHub, run:

.. code-block:: sh

   ## Clone into the current directory
   git clone 'https://github.com/Auditory-Biophysics-Lab/ablinfer' .
   ## Install dependencies and Flask, making a virtualenv inside this folder
   PIPENV_VENV_IN_PROJECT=y pipenv install flask

If installing from PyPI:

.. code-block:: sh

   PIPENV_VENV_IN_PROJECT=y pipenv install ablinfer flask

At the moment, PipEnv doesn't support optional dependencies so we had to install Flask manually.

Next, configure InferServer. This involves creating a Python file somewhere (usually ``/srv/inferserver/config.py``) that contains configuration for InferServer. The available variables and their default values are:

.. literalinclude:: ../../ablinfer/inferserver/default_settings.py
   :language: python

To change a variable, add it to your config file with the desired value; you don't need to replicate default values.

Next, we have to configure uWSGI. First, create a configuration INI file called ``inferserver.ini`` in uWSGI's configuration directory; this is usually ``/etc/uwsgi`` but may be ``/etc/local/uwsgi``. It should contain the following (omit the lines starting with ``##``):

.. code-block:: ini

   [uwsgi]
   ## The plugin line must be first
   plugin = python
   ## This is the directory you installed InferServer into
   chdir = /srv/inferserver
   ## You may have to change this if you didn't use PipEnv
   virtualenv = /srv/inferserver/.venv
   mount = /=ablinfer:inferserver:app
   ## This is the socket which NGINX will use to communicate with the server
   socket = /run/uwsgi/inferserver.sock
   ## This UID and GID usually suffices (it's simplest to use your webserver's UID/GID)
   uid = http
   gid = http
   ## Required for InferServer
   enable-threads = true
   ## This must point to the location of your InferServer config file
   env = INFERSERVER_SETTINGS=/srv/inferserver/config.py

Note that you will have to ensure that the user uWSGI runs as (``uid``) has access to Docker; this usually means that they have to be in the ``docker`` group. This can be done by running ``usermod -a -G docker <youruser>``. This user must also have read access to the InferServer install (e.g. ``/srv/inferserver``) and the model directory and write access to the session directory.

Next, start up uWSGI. On (most) SystemD systems, this is done by:

.. code-block:: sh

   systemctl enable uwsgi@inferserver
   systemctl start uwsgi@inferserver

For other systems, consult your distribution's documentation on uWSGI as it varies signficantly.

Lastly, we need to get NGINX to provide access to uWSGI. This involves two ``location`` directives inside your NGINX configuration's ``server`` directive:

.. code-block:: nginx

   location / { # Change `/` if you want to serve it from a different URL
       # Necessary for uploading large files
       client_max_body_size 0;
       try_files $uri @inferserver;
   }

   location @inferserver {
       include uwsgi_params;
       # This must be the `socket` from the uWSGI configuration
       uwsgi_pass unix:/run/uwsgi/inferserver.sock;
   }

Once that's finished, restart NGINX and browse to the URL where you're serving InferServer: you should see something like:

.. code-block:: json

   {
       "data": {
           "server": "ablinfer",
           "version": "0.0.1"
       }
   }

Installing Models
"""""""""""""""""

Installing a model is done in two steps. First, download the model's JSON specification and put it into InferServer's model directory (from your configuration). Then, restart InferServer; the Docker image will be pulled automatically on the first model run. For Docker images that aren't uploaded to DockerHub (or if you want to test it manually first), ensure that the Docker image is installed by checking ``docker image ls``. Remember that the entirety of ABLInfer was installed along with InferServer, meaning that you can activate the server's virtualenv and use `python -m ablinfer.cli` to use the ABLInfer CLI to test models.

