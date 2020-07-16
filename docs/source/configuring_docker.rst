Configuring Docker
==================

In order to run Docker containers, the first step is (naturally) to set up Docker on your system. Without GPU support the setup is trivial; GPU support requires some extra work.

Linux
"""""

Linux setup is relatively easy, provided your system supports Docker 19.03 (which adds GPU support). On most systems, all that's required is to install Docker, install the NVIDIA container toolkit, then start the Docker daemon.  `NVIDIA's GitHub <https://github.com/NVIDIA/nvidia-docker>`_ provides a good and up-to-date explanation.

Windows
"""""""

At the time of this writing, Windows setup is much trickier. Currently, Docker Desktop (or Docker for Windows) doesn't support GPUs using WSL2; this is likely to change soon, so search around before proceeding. 

Otherwise, follow the instructions on `NVIDIA's WSL page <https://docs.nvidia.com/cuda/wsl-user-guide/index.html>`_ to get the basic setup completed, ending after the "Setting up to Run Containers" section (you should be able to run NVIDIA's sample GPU containers from inside WSL2). 

Next, we need to expose the Docker daemon running inside WSL2 to the rest of the system. The way to do this is to have the Docker daemon listen on a TCP port instead of on a Unix socket as it does by default. Unlike the vast majority of Unix daemons, this is non-trivial for Docker and requires a bit of work. 

The specific place to look for configuration depends on the service manager in use. On Ubuntu WSL distros at least, the service manager in use is an old wrapper around traditional initscripts, despite the source distributions using other service managers. This may change in the future or with different distros.

Typical Systems (Ubuntu)
''''''''''''''''''''''''

Once installing Docker, try running:

.. code-block:: sh
  
   service docker status

If the ``service`` command is not found, your system is likely using a different service manager. If the ``docker`` service is not found, you haven't installed Docker properly. Otherwise, the file to edit is ``/etc/init.d/docker``. Near the top of this file will be a line:

.. code-block:: sh

   DOCKER_OPTS=

Replace this line with:

.. code-block:: sh

   DOCKER_OPTS="-H tcp://127.0.0.1:2375"

Which will tell the Docker daemon to listen on port 2375 on the loopback interface. Restart the Docker daemon with ``service docker restart``. When running Docker commands/programs, remember to set ``DOCKER_HOST=tcp://127.0.0.1:2375``. 

OpenRC Systems
''''''''''''''

Otherwise, your system might be running OpenRC. The usual way to check for this is to try running 

.. code-block:: sh

   rc-service docker status

which behaves similarly to ``service``. If this works, edit the same line in ``/etc/conf.d/docker`` instead of in ``/etc/init.d/docker``.

SystemD Systems
'''''''''''''''

The other main possibility is SystemD. This can be checked by running:

.. code-block:: sh

   systemctl status docker

If this is successful, follow the instructions on the "Daemon socket" section of the `ArchWiki page <https://wiki.archlinux.org/index.php/Docker#Daemon_socket>`_, replacing the IP address ``0.0.0.0`` with ``127.0.0.1`` to prevent Docker from running publicly.
