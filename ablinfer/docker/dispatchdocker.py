"""Basic implementation for dispatching an inference to a Docker container."""

import logging

import docker

from ..base import DispatchBase
## FIXME: The following import should be removed when DeviceRequest support is added to `docker-py`
from ._docker_patch import DeviceRequest
from .docker_helper import put_file, get_file

class DispatchDocker(DispatchBase):
    """Class for dispatching to a Docker container.

    A "docker" key is added to `config`, which should contain all of the keyword arguments to pass
    to `docker.DockerClient`, excepting `version`. If not present, `docker.from_env` is used (so
    either "docker" should be present or you should properly set environment variables, the latter
    being preferred).
    """
    def __init__(self, config=None):
        super(DispatchDocker, self).__init__(config=config)

        ## The version here must be "auto". At the time of this writing, `docker-py` defaults to
        ## using a version of the API too old to allow GPU support, even if the server supports it.
        ## Setting it to "auto" negotiates the version to the highest common version.
        if "docker" not in self.config or self.config["docker"] is None:
            self.client = docker.from_env(version="auto")
        else:
            self.client = docker.DockerClient(version="auto", **self.config["docker"])

        self.container = None

    def _validate_model_config(self):
        imagename = self.model["docker"]["image_name"] + ':' + self.model["docker"]["image_tag"]
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
        for k, v in self.model_config["inputs"].items():
            fname, fpath = (i[::-1] for i in fmap[k][::-1].split('/', 1))

            logging.info("Storing file %s to container as %s" % (v["value"], fpath+'/'+fname))
            put_file(self.container, fpath, v["value"], name=fname)

    def _run_command(self, cmd, progress):
        ## Ignore cmd, it's not actually helpful anymore
        self.container.start()
        for line in self.container.logs(stream=True):
            progress(0, line)
        resp = self.container.wait()
        if resp["StatusCode"] != 0:
            raise Exception("Failed")

    def _cleanup(self, error=False):
        super(DispatchDocker, self)._cleanup(error=error)
        if self.container is not None:
            self.container.remove()

    def _load_output(self, fmap):
        for k, v in self.model_config["outputs"].items():
            self._output_files.append(v["value"])
            get_file(self.container, fmap[k], v["value"])