#!/usr/bin/env python3

from collections import OrderedDict as OD
import logging
from urllib.parse import urljoin
import time

import requests as r

from ..base import DispatchBase, DispatchException

def urljoin_b(*args):
    """Make urljoin behave like path.join to preserve my sanity."""
    if len(args) > 2:
        return urljoin(urljoin_b(*args[:-1])+'/', args[-1])
    elif len(args) == 2:
        return urljoin(args[0]+'/', args[1])
    return args[0]

class DispatchRemote(DispatchBase):
    """Class for dispatching to an ABLInfer server.

    A required ``base_url`` key is added to ``config``, which must be the server's base URL, which
    will be passed to :func:``urllib.parse.urljoin`` to construct the query URLs. In addition, an
    optional key ``auth`` is added to ``config``, which may be of any form accepted by the ``auth``
    parameter of the various :module:``requests`` methods. Lastly, for other auth forms a 
    ``session`` parameter is added to ``config`` which allows the user to provide a 
    :class:``requests.Session`` instance.
    """
    def __init__(self, config=None):
        self.base_url = None
        self.auth = None
        self.session = None
        self.remote_session = None
        self.model_id = None

        super().__init__()

    def get_model(self, model_id: str):
        """Retrieve a model from the site.

        This function assumes that the model received is normalized.

        :param model_id: The model's ID.
        """
        with self._lock:
            resp = self.session.get(urljoin_b(self.base_url, "models", "model_id"), auth=self.auth)
            resp.raise_for_status()
            return resp.json(object_pairs_hook=OD)["data"]

    def _validate_config(self):
        super()._validate_config()

        self.base_url = self.config["base_url"]
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        self.auth = self.config["auth"] if "auth" in self.config else None
        self.session = self.config["session"] if "session" in self.config else r.Session()

        ## Check the server
        logging.info("Trying server at %s..." % self.base_url)
        resp = r.get(self.base_url)
        resp.raise_for_status()
        resp = resp.json()
        if resp["data"]["server"] != "ablinfer":
            raise ValueError("Unknown server %s" % repr(resp["data"]["server"]))

    def _validate_model_config(self):
        ## We need to check that the server has the correct version of the model first
        self.model_id = self.model["id"]
        try:
            model = self.get_model(self.model_id)
        except Exception as e:
            raise DispatchException("Unable to retrieve model from the server: %s" % repr(e))

        if self.model["version"] != model["version"]:
            raise DispatchException("Version mismatch between server model and local model: server has v%s, we have v%s" % (model["version"], self.model["version"]))

        super()._validate_model_config()

    def _make_fmap(self):
        return {}

    def _make_flags(self, fmap):
        return []

    def _make_command(self, flags):
        resp = self.session.post(
            urljoin_b(self.base_url, "models", self.model_id), 
            json={"params": self.model_config["params"]},
            auth=self.auth
        )
        resp.raise_for_status()

        self.remote_session = resp.join()["data"]["session_id"]

        return []

    def _get_status(self):
        return self.session.get(urljoin_b(self.base_url, "sessions", self.remote_session), auth=self.auth).json()["data"]["status"]

    def _save_input(self, fmap):
        for name, v in self.model_config["inputs"].items():
            with open(v["value"], "rb") as f:
                resp = self.session.put(urljoin_b(self.base_url, "sessions", self.remote_session, "inputs", name), headers={"Content-Type": "application/octet-stream"}, data=f, auth=self.auth)
                resp.raise_for_status()
        if self._get_status() == "waiting":
            raise DispatchException("Session ID %s is still waiting for input, but all input has been provided, please report this" % self.remote_session)

    def _run_command(self, cmd, progress):
        logging.info("Starting run...")
        resp = self.session.get(urljoin_b(self.base_url, "sessions", self.remote_session, "logs"), auth=self.auth, stream=True)
        for line in resp.iter_lines(512):
            progress(0.5, line.decode("utf-8"))

        ## Now the run is over
        logging.info("Logs ended, waiting for the session to finish...")
        while True:
            status = self._get_status()
            if status in ("complete", "failed"):
                break
            time.sleep(1)

        if status == "failed":
            raise DispatchException("Session ID %s failed, please report this" % self.remote_session)

    def _load_output(self, fmap):
        for name, v in self.model_config["outputs"].items():
            logging.info("Saving output %s" % name)
            self._output_files.append(v["value"])
            with open(v["value"], "wb") as f:
                resp = self.session.get(urljoin_b(self.base_url, "sessions", self.remote_session, "outputs", name), auth=self.auth, stream=True)
                resp.raise_for_status()
                for chunk in resp.iter_content(1048576):
                    f.write(chunk)

    def _cleanup(self, error=None):
        super()._cleanup(error=error)

        self.remote_session = None
        self.session = None
        self.auth = None
        self.model_id = None