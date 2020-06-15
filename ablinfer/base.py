"""Base class for dispatch helpers."""

from __future__ import division

from abc import ABCMeta, abstractmethod
import logging
import os
from threading import Lock
from typing import List, Mapping, Any, Callable, Dict

from .processing import dispatch_processing

class DispatchException(Exception):
    """To be raised if a process runs into a problem.

    :param stderr: The stderr output of the process, if any.
    """
    def __init__(self, msg, stderr: str = None):
        super().__init__(msg)

        self.stderr = stderr

class DispatchBase(metaclass=ABCMeta):
    """Base class for dispatching to models.

    This class cannot actually be instantiated; users are intended to instantiate a subclass that
    dispatches using the appropriate method (e.g. :class:`ablinfer.docker.DispatchDocker`).

    The general procedure when running is:

    1. :meth:`_validate_config`
    2. :meth:`_validate_model_config`
    3. :meth:`_make_fmap`
    4. :meth:`_make_flags`
    5. :meth:`_make_command`
    6. :meth:`_run_processing` (dispatches required nodes to :meth:`_clone` to copy them)
    7. :meth:`_save_input`
    8. :meth:`_run_command`
    9. :meth:`_load_output`
    10. :meth:`_run_processing`
    11. :meth:`_cleanup()`

    Functions are expected to raise exceptions if they encounter any unfixable errors. If an
    exception is raised, :meth:`_cleanup_all` will be called.
    """

    def __init__(self, config: Mapping = None) ->  None:
        if config is None:
            config = {}
        self.config = config

        self._created_files: List[str] = []
        self._output_files: List[str] = []
        self._pre_nodes: Dict[str, Any] = {}

        self._lock = Lock()

        self.model: Mapping[str, Any] = None
        self.model_config: Mapping[str, Any] = None

        self._validate_config()

    def _validate_config(self) ->  None:
        """Validate the non-model configuration."""

    def _validate_model_config(self) ->  None:
        """Validate the model configuration.

        We assume for convenience that validation has already been done by the config widget, i.e.
        each input/output/parameter has a proper type, default value, etc. The main validation done
        here is to make sure that no inputs/outputs are the same and no inputs are null.
        """
        in_nodes = {i["value"] for i in self.model_config["inputs"].values()}
        if None in in_nodes:
            raise ValueError("Make sure that all inputs are selected!")

        out_nodes = {i["value"] for i in self.model_config["outputs"].values()}
        if in_nodes.intersection(out_nodes).difference((None,)):
            raise ValueError("Inputs and outputs must be different")

    def _make_fmap_helper(self, actual_path: str) ->  Mapping[str, str]:
        ## Strip the trailing slash of actual_path, if it has one
        if len(actual_path) > 1 and actual_path[-1] in ('/', '\\'):
            actual_path = actual_path[:-1]

        fmap = {}
        for s in ("inputs", "outputs",):
            for k, v in self.model[s].items():
                fmap[k] = actual_path + '/' + k + v["extension"]

        return fmap

    @abstractmethod
    def _make_fmap(self) ->  Mapping[str, str]:
        """Make the file map.

        :returns: The created filemap, mapping the input/output name to its path as seen by
                  whatever the command will be dispatched to (e.g. for Docker, this would be the
                  path inside the container).
        """

    def _clone(self, node: Any) ->  Any:
        """Clone the given node for pre-processing.

        This should be overwritten for implementations based on the format your nodes are in. Any
        cloned node distinct from the input node is added to `self._pre_nodes`, which maps the
        input name to the result of this function. These nodes should be cleaned up at in the
        :meth:`_cleanup` function.
        """
        return node

    def _run_processing(self, inp: bool) ->  None:
        """Run pre/post processing.

        :param inp: Whether to do the input or output section.
        """
        section = "inputs" if inp else "outputs"
        process = "pre" if inp else "post"

        if inp:
            self._pre_nodes = {}

        for o, member in self.model[section].items():
            node = self.model_config[section][o]["value"]

            if process not in member:
                continue
            logging.info("Running %sprocessing for %s..." % (process, member["name"]))

            ## Clone nodes if we're pre-processing
            if inp and True in (i["enabled"] for i in self.model_config[section][o][process]):
                ## Make sure we have at least one pre-processing to run
                cnode = self._clone(node)
                if cnode != node:
                    self._pre_nodes[o] = cnode
                node = cnode

            for n, op in enumerate(member[process], 1):
                logging.info("%d. %s" % (n, op["name"]))
                if not self.model_config[section][o][process][n-1]["enabled"]:
                    logging.info("- Not enabled: skipping")
                    continue
                ## TODO: Possibly keep going if a processing step fails?
                dispatch_processing(op, self.model_config[section][o][process][n-1], node, member, self.model, self.model_config, inp=inp)

    @abstractmethod
    def _save_input(self, fmap: Mapping[str, str]) ->  None:
        """Save the input files at the appropriate locations for running the model.

        See the :class:`ablinfer.docker.DispatchDocker` class for an example. This function will
        need to be overridden to reflect whatever node format your subclass uses.
        """

    def _make_flags(self, fmap: Mapping[str, str]) ->  List[str]:
        """Construct the flags to pass to the command.

        :param fmap: The generated fmap.
        """
        cmd = {}
        def format_flag(f, v):
            if not f:
                return (v,)
            elif f[-1] == '=':
                return (f+v,)
            return (f, v,)

        for n in ("inputs", "outputs"):
            for k, _ in self.model_config[n].items():
                cmd[k] = format_flag(self.model[n][k]["flag"], fmap[k])

        for k in self.model_config["params"]:
            if self.model["params"][k]["type"] == "bool": ## Handle boolean switches
                if self.model_config["params"][k]["value"]:
                    cmd[k] = (self.model["params"][k]["flag"],)
            else:
                cmd[k] = format_flag(self.model["params"][k]["flag"], str(self.model_config["params"][k]["value"]))

        ## Set the flags in the proper order
        if "order" in self.model:
            order = self.model["order"]
        else:
            order = sorted(list(cmd.keys()))

        acmd = []
        for i in order:
            if i not in cmd:
                continue
            acmd.extend(cmd[i])

        return acmd

    def _make_command(self, flags: List[str]) ->  List[str]:
        """Make the final command.

        :param flags: A list of the flags to be included.
        :returns: The final command, to be passed to :meth:`_run_command_`.
        """
        return flags

    @abstractmethod
    def _run_command(self, cmd: List[str], progress: Callable[[float, str], None]) ->  None:
        """Run the actual command.

        Must raise :class:`DispatchException` if the called process runs into a problem.

        :param cmd: The command to execute.
        :param progress: The function to call with progress reports.
        """

    @abstractmethod
    def _load_output(self, fmap: Mapping[str, str]) ->  None:
        """Put the output files into the appropriate locations.

        It is this function's responsibility to set self._output_files as the files are created, so
        that they can be removed properly if the command fails.

        :param fmap: The file map.
        """

    def _cleanup(self, error: bool = False) ->  None:
        """Run successful cleanup.

        This function should conduct all of the cleanup necessary for a successful run. This will
        also be called if the run fails. This means that this function should run checks of its
        own to see what actually needs to be cleaned up.

        :param error: Whether or not an error was encountered.
        """
        for f in self._created_files:
            try:
                os.remove(f)
            except:
                pass

    def _cleanup_all(self) ->  None:
        """Cleanup everything.

        This will only be called if an error is raised.
        """
        self._cleanup(error=True)
        for f in self._output_files:
            try:
                os.remove(f)
            except:
                pass

    def _run(self, progress: Callable[[float, str], None]) ->  None:
        """Actual run method.

        This is just to make sure the run method can't be called twice at once.
        """
        logging.info("Processing started")

        try:
            logging.info("Validating model configuration...")
            self._validate_model_config()

            fmap = self._make_fmap()
            cmd = self._make_command(self._make_flags(fmap))

            logging.info("Running pre-processing...")
            self._run_processing(inp=True)

            self._save_input(fmap)

            logging.info("Command: "+' '.join(cmd))

            logging.info("Running model...")
            self._run_command(cmd, progress)

            logging.info("Loading output...")
            self._load_output(fmap)

            logging.info("Running post-processing...")
            self._run_processing(inp=False)

            logging.info("Cleaning up inputs...")
            self._cleanup(error=False)

            logging.info('Processing completed')
        except Exception as e:
            self._cleanup_all()
            raise e

    def run(self, model: Mapping, model_config: Mapping, progress: Callable[[float, str], None] = print) ->  None:
        """Run the model.

        This is the entry point

        :param model: The loaded model JSON file.
        :param model_config: The model parameters, as returned by `ModelConfigWidget.get_values`.
        :param progress: an optional function accepting a float on [0,1] representing current
                         progress in the model and an optional string with more detailed info
        """
        ## Ensure only one run is underway
        with self._lock:
            self.model = model
            self.model_config = model_config

            self._run(progress)
