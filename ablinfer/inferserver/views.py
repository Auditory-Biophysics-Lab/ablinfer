#!/usr/bin/env python3

import datetime as dt
import enum
import hashlib
import json
from os import path
import os
import queue
import shutil
import threading
import time
import traceback
from typing import Dict, Any
import uuid

import docker
from flask import jsonify, request, send_file, Response

from ..docker import DispatchDocker
from ..model import load_model

from . import app
from .util import KeepAliveIterator, guess_filetype

for d in ("MODEL_PATH", "SESSION_PATH"):
    d = app.config[d]
    if not path.isdir(d):
        os.makedirs(d)

__version__ = "1.0.0"

class IndexedQueue:
    """Thread-safe queue with indexing. 

    Uses `threading.RLock` for synchronization.

    The common `timeout` parameter is the same as for `threading.RLock.acquire`. 
    """
    def put(self, item: Any) -> Any:
        """Put an item."""
        with self._lock:
            self._queue.append(item)
            self._count.release()

    def get(self, timeout=None) -> None:
        """Get an item."""
        ret = self._count.acquire(timeout=timeout)
        if not ret:
            raise queue.Empty()

        with self._lock:
            return self._queue.pop(0)

    def index(self, item: Any) -> int:
        """Get the index of an item in the queue.

        Has the same behaviour as `List.index`.
        """
        with self._lock:
            return self._queue.index(item)

    def __init__(self):
        self._queue = []
        self._count = threading.Semaphore(0)
        self._lock = threading.RLock()

class DispatchDockerServer(DispatchDocker):
    def _make_command(self, flags):
        ret = super()._make_command(flags)
        with self.session.lock:
            self.session.container = self.container.id
        return ret

    def _cleanup(self, error=None):
        if self.container is not None and "__logs" in self.model_config:
            with open(self.model_config["__logs"], "wb") as f:
                for chunk in self.container.logs(stream=True):
                    f.write(chunk)

        with self.session.lock:
            super()._cleanup()
            self.session.set_state(Session.State.FAILED if error else Session.State.COMPLETE)
            if error:
                self.session.info = repr(error)
            self.session.container = None

    def _run_processing(self, inp):
        ## We don't do any here
        return

    def _on_container_start(self):
        with self.session.lock:
            self.session.state = Session.State.WORKING

    def run(self, session: "Session", *args, **kwargs):
        self.session = session
        super().run(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None

class Model:
    class ModelParam:
        def parse(self, value):
            if self.is_file:
                raise NotImplementedError("Cannot validate files")
            elif self.type == "int":
                minv = self.param["min"] if "min" in self.param else -2147483648
                maxv = self.param["max"] if "max" in self.param else 2147483647

                value = int(value) 
                if value < minv or value > maxv:
                    raise ValueError("Must be between %d and %d" % (minv, maxv))
            elif self.type == "float":
                minv = self.param["min"] if "min" in self.param else -3.40282e+038
                maxv = self.param["max"] if "max" in self.param else 3.40282e+038

                value = float(value)
                if value < minv or value > maxv:
                    raise ValueError("Must be between %d and %d" % (minv, maxv))
            elif self.type == "bool":
                value = bool(value)
            elif self.type == "enum":
                value = self.enum[value]
            elif self.type == "string":
                pass 
            else:
                ## Just in case, we catch this in the constructor
                raise ValueError("Unknown type %s (THIS SHOULD NOT HAPPEN)" % self.type)

            return value

        def __init__(self, id_, param):
            if param["type"] not in ("volume", "segmentation", "int", "float", "bool", "enum", "string",):
                raise ValueError("Unknown type %s for %s" % (param["type"], param["name"]))
            self.id = id_
            self.is_file = param["type"] in ("segmentation", "volume",)
            self.param = param
            self.type = param["type"]
            self.default = param["default"] if "default" in param else None
            self.enum = None
            if self.type == "enum":
                if isinstance(self.param["enum"], list):
                    self.enum = {n: n for n in  self.param["enum"]}
                else:
                    self.enum = self.param["enum"]

    def __init__(self, model: Dict):
        self.name = model["name"]
        self.inputs = {k: Model.ModelParam(k, v) for k, v in model["inputs"].items()}
        self.params = {k: Model.ModelParam(k, v) for k, v in model["params"].items()}
        self.outputs = {k: Model.ModelParam(k, v) for k, v in model["outputs"].items()}
        self.model = model

class Session:
    """Class for an inference session.

    The session's `lock` attribute is an RLock and must be acquired before accessing/modifying any
    of the session's attributes.
    """
    class State(enum.Enum):
        WAITING = "waiting"
        READY = "ready"
        WORKING = "working"
        COMPLETE = "complete"
        FAILED = "failed"

    def set_state(self, state: State):
        """Set the state and update the "last used" time."""
        self.state = state
        self.state_change = dt.datetime.now()

    def cleanup(self):
        """Cleanup the session.

        This removes all files remaining on disk.
        """
        try:
            shutil.rmtree(self.base_dir)
        except:
            pass

    def __init__(self, id_, model: Model, params: Dict):
        self.id = id_
        self.model = model
        self.params = params
        self.lock = threading.RLock()
        self.last = dt.datetime.now()

        ## A mapping of needed items to whether or not they're busy. If an item is in here, it's 
        ## needed
        self.needed = {k: False for k, v in model.inputs.items() if v.is_file}

        self.state_change = dt.datetime.now()
        self.state = Session.State.WAITING
        self.info = ""

        self.base_dir = path.join(app.config["SESSION_PATH"], id_)
        os.mkdir(self.base_dir)
        os.mkdir(path.join(self.base_dir, "inputs"))
        os.mkdir(path.join(self.base_dir, "outputs"))

        ## Store parameters
        with open(os.path.join(self.base_dir, "params.json"), "w") as f:
            json.dump(params, f)

        ## Setup the filenames
        self.filenames = {}
        for s in ("inputs", "outputs"):
            self.params[s] = {}
            sv = model.model[s]
            for k, v in sv.items():
                self.filenames[k] = path.join(self.base_dir, s, k+v["extension"])
                self.params[s][k] = {"value": self.filenames[k]}
        self.params["__logs"] = path.join(self.base_dir, "logs")
        self.params["__error"] = path.join(self.base_dir, "error")

        self.container = None

class Worker:
    def run(self):
        while self.main.running:
            try:
                ## Timeout every 5 seconds to check if we're supposed to quit
                session = self.main.queue.get(timeout=5)
            except queue.Empty:
                continue

            ## Run the model
            try:
                self.dispatch.run(session, session.model.model, session.params, print)
            except Exception as e:
                with session.lock, open(session.params["__error"], 'w') as f:
                    traceback.print_exc(file=f)
                traceback.print_exc()

    def __init__(self, main: "Main", id_):
        self.main = main
        self.id = id_

        ## TODO: Docker config?
        self.dispatch = DispatchDockerServer()

class Main:
    """Main server object."""
    def handle_models(self):
        """Provide a list of the names of available models."""
        return jsonify(data=tuple(self.models.keys()))

    def handle_models_model_inp_check(self, model, inp):
        if model not in self.models:
            return jsonify(errors=[{"detail": "Unknown model %s" % model}]), 404

        cl = request.content_length
        if cl > 4096:
            return jsonify(errors=[{"detail": "Request too large, needs at most 4096"}]), 413

        header = bytes()
        ext = self.models[model].model["inputs"][inp]["extension"]
        checked = False

        for chunk in request.stream:
            if len(header) < 4096:
                header += chunk

        ft = guess_filetype(header)
        return jsonify(data={
            "filetype": ft,
            "acceptable": (ext not in (".nii", ".nrrd", ".nii.gz")) or not app.config["CHECK_INPUT_FILETYPES"] or (ft is not None and ft.lower() == ext.lower()),
        })

    def handle_models_model(self, model):
        """Provide the model specification for the given model name."""
        if model not in self.models:
            return jsonify(errors=[{"detail": "Unknown model %s" % model}]), 404

        if request.method == "GET":
            return jsonify(data=self.models[model].model)

        ## POST, create a new session
        if not request.is_json:
            return jsonify(errors=[{"detail": "Must pass the model parameters as JSON"}]), 400

        ## Validate and parse the user's parameters
        model = self.models[model]
        params = request.get_json()
        params_val = {"params": {}}
        for section in params_val:
            if section not in params:
                return jsonify(errors=[{"detail": "Missing section %s" % section}]), 400
            params_sec = params[section]
            params_val_sec = params_val[section]
            for name, param in getattr(model, section).items():
                params_val_sec[name] = {}
                if param.is_file:
                    continue
                elif name not in params_sec:
                    if param.default is None:
                        return jsonify(errors=[{"detail": "Missing parameter %s/%s" % (section, name)}]), 400
                    value = param.default
                else:
                    if not isinstance(params_sec[name], dict):
                        return jsonify(errors=[{"detail": "Improper formatting for %s/%s" % (section, name)}]), 400
                    try:
                        value = param.parse(params_sec[name]["value"])
                    except Exception as e:
                        return jsonify(errors=[{"detail": "Invalid value for %s/%s: %s" % (section, name, str(e))}]), 400
                params_val_sec[name]["value"] = value

        ## Now that they're valid, create a new session
        with self.sessions_lock:
            id_ = str(uuid.uuid4())
            while id_ in self.sessions:
                id_ = str(uuid.uuid4())

            self.sessions[id_] = Session(id_, model, params_val)

        ## Return the created session ID
        return jsonify(data={"session_id": id_})

    def handle_sessions_session(self, session):
        """Return information on a session."""
        with self.sessions_lock:
            if session not in self.sessions:
                return jsonify(errors=[{"detail": "Unknown session"}]), 404

            session = self.sessions[session]
            with session.lock:
                data = {
                    "status": str(session.state.value),
                    "needed": list(session.needed.keys()),
                    "info": str(session.info),
                }

            return jsonify(data=data)

    def handle_sessions_session_inputs(self, session, inp):
        """Allow the user to upload input files for the session."""
        with self.sessions_lock:
            if session not in self.sessions:
                return jsonify(errors=[{"detail": "Unknown session"}]), 404

            session = self.sessions[session]

            with session.lock:
                if inp not in session.model.inputs:
                    return jsonify(errors=[{"detail": "Unknown input"}]), 404
                elif session.state != Session.State.WAITING:
                    return jsonify(errors=[{"detail": "Session has already received all input"}]), 400

                if inp not in session.needed:
                    ## Overwrite the old one
                    session.needed[inp] = False 
                if session.needed[inp]:
                    ## Busy, ignore the request 
                    return jsonify(errors=[{"detail": "Resource is already being uploaded"}]), 409
                
                ## Set the busy flag
                session.needed[inp] = True
                session.last = dt.datetime.now()

        try:
            h = hashlib.sha256()

            header = bytes()
            ext = session.model.inputs[inp].param["extension"]
            checked = False

            with open(session.filenames[inp], "wb") as f:
                for chunk in request.stream:
                    chunk = bytes(chunk)
                    if not checked:
                        if len(header) < 1024:
                            header += chunk[:1024]
                        if len(header) >= 1024:
                            if app.config["CHECK_INPUT_FILETYPES"] and ext in (".nii", ".nii.gz", ".nrrd"):
                                ft = guess_filetype(header)
                                if ft is not None and ft.lower() != ext.lower():
                                    return jsonify(errors=[{"detail": "Expected filetype %s" % ext}]), 400
                            checked = True
                            header = None

                    f.write(chunk)
                    h.update(chunk)
            return jsonify(data=h.hexdigest())

            with session.lock:
                del session.needed[inp]

                if not session.needed:
                    session.state = Session.State.READY 
                    self.queue.put(session)

        finally:
            with session.lock:
                ## Clear the busy flag, if something broke
                if inp in session.needed:
                    session.needed[inp] = False
            
        return jsonify(data={"sha256": h.hexdigest()})

    def handle_sessions_session_outputs(self, session, outp):
        """Allow the user to download finished output files."""
        with self.sessions_lock:
            if session not in self.sessions:
                return jsonify(errors=[{"detail": "Unknown session"}]), 404

            session = self.sessions[session]
            
            with session.lock:
                if outp not in session.model.outputs:
                    return jsonify(errors=[{"detail": "Unknown output"}]), 404
                elif session.state != Session.State.COMPLETE:
                    return jsonify(errors=[{"detail": "Session is not complete"}]), 400
            
            return send_file(session.filenames[outp])

    def cleanup(self):
        """Run cleanup of old sessions."""
        print("Running cleanup")
        now = dt.datetime.now()
        remove_states = [Session.State.WAITING]
        if app.config["CLEANUP_FINISHED"]:
            remove_states.extend((Session.State.FAILED, Session.State.COMPLETE,))

        with self.sessions_lock:
            sessions = list(self.sessions.keys())
            for s in sessions:
                v = self.sessions[s]
                with v.lock:
                    if v.state in remove_states and (now - v.last).total_seconds() >= app.config["CLEANUP_SECONDS"]:
                        if app.config["CLEANUP_FILES"]:
                            v.cleanup()
                        del self.sessions[s]

            self.cleanup_timer = threading.Timer(app.config["CLEANUP_TIMER"], self.cleanup)
            self.cleanup_timer.start()

    def handle_sessions_session_logs(self, session):
        """Return session logs."""
        with self.sessions_lock:
            if session not in self.sessions:
                return jsonify(errors=[{"detail": "Unknown session"}]), 404

            session = self.sessions[session]
            with session.lock:
                if session.state not in (Session.State.WORKING, Session.State.READY, Session.State.COMPLETE, Session.State.FAILED):
                    return jsonify(errors=[{"detail": "Session not running yet"}]), 400
                elif session.state == Session.State.READY:
                    container = True
                else:
                    container = session.container

        if container is not None:
            ## Get logs from the container
            def gen():
                while True:
                    with self.sessions_lock, session.lock:
                        if session.state == Session.State.READY:
                            try:
                                index = self.queue.index(session) + 1
                            except ValueError:
                                index = 0
                        elif session.state == Session.State.WORKING:
                            client = docker.from_env()
                            container = client.containers.get(session.container)
                            break
                    yield ("Waiting, position in queue is %d\n" % index).encode("utf-8")
                    time.sleep(1)

                for line in container.logs(stream=True, follow=True):
                    yield line
            return Response(KeepAliveIterator(gen(), alt="\0\n"), mimetype="text/plain", headers={"X-Accel-Buffering": "no"})
        else:
            return send_file(session.params["__logs"], mimetype="text/plain")

    def handle_root(self):
        return jsonify(data={"server": "inferserver", "version": __version__})

    def __init__(self):
        self.models = {}
        for fname in os.listdir(app.config["MODEL_PATH"]):
            if not fname.lower().endswith(".json"):
                continue
            with open(path.join(app.config["MODEL_PATH"], fname), 'r') as f:
                model = load_model(f)[0]
            self.models[model["id"]] = Model(model)

        self.sessions = {}
        self.sessions_lock = threading.RLock()

        app.route("/", methods=["GET"])(self.handle_root)
        app.route("/models", methods=["GET"])(self.handle_models)
        app.route("/models/<model>", methods=["GET", "POST"])(self.handle_models_model)
        app.route("/models/<model>/inputs/<inp>/check", methods=["POST"])(self.handle_models_model_inp_check)
        app.route("/sessions/<session>", methods=["GET"])(self.handle_sessions_session)
        app.route("/sessions/<session>/inputs/<inp>", methods=["PUT"])(self.handle_sessions_session_inputs)
        app.route("/sessions/<session>/outputs/<outp>", methods=["GET"])(self.handle_sessions_session_outputs)
        app.route("/sessions/<session>/logs", methods=["GET"])(self.handle_sessions_session_logs)

        self.running = True

        self.queue = IndexedQueue()
        self.workers = []

        if app.config["CLEANUP_TIMER"] != -1:
            self.cleanup_timer = threading.Timer(app.config["CLEANUP_TIMER"], self.cleanup)
            self.cleanup_timer.start()
        else:
            self.cleanup_timer = None

        for i in range(app.config["WORKER_THREADS"]):
            worker = Worker(self, i)
            thread = threading.Thread(target=worker.run)
            self.workers.append(thread)
            thread.start()

main = Main()
