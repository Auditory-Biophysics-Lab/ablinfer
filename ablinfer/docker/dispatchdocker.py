"""Basic implementation for dispatching an inference to a Docker container."""

import logging

import docker

from ..base import DispatchBase, DispatchException
from ..constants import DispatchStage
## FIXME: The following import should be removed when DeviceRequest support is added to `docker-py`
from ._docker_patch import DeviceRequest
from .docker_helper import put_file, get_file

class DispatchDocker(DispatchBase):
    """Class for dispatching to a Docker container.

    A ``docker`` key is added to ``config``, which should contain all of the keyword arguments to
    pass to ``docker.DockerClient``, excepting ``version``. If not present, ``docker.from_env`` is
    used (so either ``docker`` should be present or you should properly set environment variables, 
    the latter being preferred). 

    This implementation expects the model configuration values to be the path to the appropriate 
    files on the **host machine**, which it will then put into/get from the container during the 
    run.
    """
    def __init__(self, config=None):
        self.client = None
        self.container = None

        super(DispatchDocker, self).__init__(config=config)

    def _on_container_start(self):
        """Called when the container is actually started."""
        return

    def _validate_config(self):
        super()._validate_config()

        ## The version here must be "auto". At the time of this writing, `docker-py` defaults to
        ## using a version of the API too old to allow GPU support, even if the server supports it.
        ## Setting it to "auto" negotiates the version to the highest common version.
        if "docker" not in self.config or self.config["docker"] is None:
            self.client = docker.from_env(version="auto")
        else:
            self.client = docker.DockerClient(version="auto", **self.config["docker"])

        self.client.ping()

    def _validate_model_config(self):
        super()._validate_model_config()

        imagename = self.model["docker"]["image_name"] + ':' + self.model["docker"]["image_tag"]
        try:
            self.client.images.get(imagename)
        except docker.errors.ImageNotFound:
            self.progress(DispatchStage.Validate, 0, 0, "Docker image not found locally, trying to pull it")
            self.client.images.pull(imagename)
            self.client.images.get(imagename)

    def _make_fmap(self):
        return self._make_fmap_helper(self.model["docker"]["data_path"])

    def _make_command(self, flags):
        cmd = super()._make_command(flags)

        ## If the API is new enough, request GPU access
        kwargs = {}
        if self.client.version()["ApiVersion"] >= "1.40":
            logging.info("API version is high enough for GPU access")
            ## Request all GPU devices
            kwargs["device_requests"] = [
                {
                    "count": -1,
                    "capabilities": [["gpu"]]
                }
            ]
        else:
            logging.warning("API version is too low for GPUs")

        ## We have to create the container here, since the command/flags need to be known ahead of
        ## time for some strange reason (Docker limitation)
        imagename = self.model["docker"]["image_name"] + ':' + self.model["docker"]["image_tag"]
        self.container = self.client.containers.create(imagename, command=cmd, **kwargs)

        return []

    def _save_input(self, fmap):
        ## We assume here that all of the inputs and outputs are strings, indicating the file
        ## locations on the local machine. We need to copy the input files into the container
        total = len(self.model_config["inputs"])
        for n, (k, v) in enumerate(self.model_config["inputs"].items()):
            fname, fpath = (i[::-1] for i in fmap[k][::-1].split('/', 1))

            logging.info("Storing file %s to container as %s" % (v["value"], fpath+'/'+fname))
            self.progress(DispatchStage.Save, n/total, 0, "Storing file %s..." % v["value"])
            put_file(self.container, fpath, v["value"], name=fname)

    def _run_command(self, cmd):
        ## Ignore cmd, it's not actually helpful anymore
        self.container.start()
        self._on_container_start()
        for line in self.container.logs(stream=True):
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            self.progress(DispatchStage.Run, 0, 0, line)
        resp = self.container.wait()
        if resp["StatusCode"] != 0:
            ## Don't bother getting stderr, they can just get the logs themselves
            raise DispatchException("Called process failed")

    def _cleanup(self, error=None):
        super()._cleanup(error=error)
        if self.container is not None:
            self.container.remove()

    def _load_output(self, fmap):
        total = len(self.model_config["outputs"])
        for n, (k, v) in enumerate(self.model_config["outputs"].items()):
            self._output_files.append(v["value"])
            self.progress(DispatchStage.Load, n/total, 0, "Storing file %s...")
            get_file(self.container, fmap[k], v["value"])
