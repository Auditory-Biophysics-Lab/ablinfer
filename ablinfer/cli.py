#!/usr/bin/env python3

if __name__ == "__main__":
    import argparse
    import getpass
    import os
    import sys

    import requests

    from .docker import DispatchDocker
    from .remote import DispatchRemote
    from . import DispatchBase
    from .model import load_model
    from .constants import DispatchStage

    ## Remote the pre-processing from the dispatchers
    class DispatchRemoteSimple(DispatchRemote):
        def _run_processing(self, inp):
            return

    class DispatchDockerSimple(DispatchDocker):
        def _run_processing(self, inp):
            return

    ## First parser, this handles 
    parser = argparse.ArgumentParser(description="A CLI for running inferences on ABLInfer servers or Docker containers with an ABLInfer model specification")
    parser.add_argument("-s", "--server", help="Base URL of the remote ABLInfer server to use, instead of a local Docker instance")
    parser.add_argument("-c", "--cert", type=str, default=False, help="SSL certificate to use to verify the server; if none, SSL verification will be skipped")
    parser.add_argument("-u", "--username", type=str, help="Username for remote server")
    parser.add_argument("-p", "--password", type=str, help="Password for remote server (if none and username is provided, the password will be prompted)")
    parser.add_argument("-f", "--field-names", action="store_true", help="Use field names for model arguments instead of the model flags (only affects this CLI interface, no effect on the actual inference)")
    parser.add_argument("model", help="Either a local model specification file or a model ID from the server")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Model arguments")

    args = parser.parse_args()

    dispatch: DispatchBase

    if args.server is not None: ## Remote dispatch
        session = requests.Session()
        session.verify = args.cert
        if args.username is not None:
            if args.password is None:
                args.password = getpass.getpass("Password: ")
            session.auth = (args.username, args.password)

        dispatch = DispatchRemoteSimple({
            "base_url": args.server,
            "session": session,
        })
        
        if not os.path.isfile(args.model):
            try:
                model = dispatch.get_model(args.model)
            except Exception as e:
                sys.stderr.write("Unable to retrieve model \"%s\" from server: %s" % (args.model, repr(e)))
                sys.stderr.write("Available models on server: %s" % ", ".join(dispatch.get_model_list()))
                sys.exit(1)
        else:
            with open(args.model, 'r') as f:
                model = load_model(f)[0]
    else: ## Local dispatch
        dispatch = DispatchDockerSimple()

        with open(args.model, 'r') as f:
            model = load_model(f)[0]

    ## Assemble the second parser
    flag_map = {}
    sec_map = {}
    for s in ("outputs", "inputs", "params"):
        for k, v in model[s].items():
            sec_map[k] = s
            if args.field_names:
                flag_map[k] = "--" + k.replace('_', '-')
            else:
                flag_map[k] = v["flag"].rstrip('=')
        
    if not model.get("order"):
        order = sorted(flag_map)
    else:
        order = model["order"]

    parser = argparse.ArgumentParser(args.model)
    for k in order:
        v = model[sec_map[k]][k]
        
        flag = flag_map[k]
        params = {
            "help": "%s. %s" % (v["name"], v["description"]),
            "dest": k,
        }

        typ = v["type"]
        if typ in ("segmentation", "volume"): ## File
            params["required"] = True
        elif typ == "int":
            params["type"] = int
        elif typ == "float":
            params["type"] = float
        elif typ == "bool":
            params["action"] = "store_true"
        elif typ == "enum":
            params["choices"] = tuple(k["enum"].values())
        elif typ == "string":
            pass
        else:
            raise ValueError("Unknown type %s" % typ)

        parser.add_argument(flag, **params)

    args = parser.parse_args(args.args)
    model_config = {
        "inputs": {},
        "params": {},
        "outputs": {},
    }
    for k in order:
        s = sec_map[k]
        if getattr(args, k) is not None:
            model_config[s][k] = {"value": getattr(args, k)}

    def progress(stage, f1, f2, s):
        if stage == DispatchStage.Initial:
            stage = "INIT"
        elif stage == DispatchStage.Validate:
            stage = "VALI"
        elif stage == DispatchStage.Preprocess:
            stage = "PREP"
        elif stage == DispatchStage.Save:
            stage = "SAVE"
        elif stage == DispatchStage.Run:
            stage = "RUN "
        elif stage == DispatchStage.Load:
            stage = "LOAD"
        elif stage == DispatchStage.Postprocess:
            stage = "POST"
        else:
            stage = "    "

        if s.endswith('\n'):
            s = s[:-1]
        print("[%s] %3.0f%%, %3.0f%%: %s" % (stage, 100*f1, 100*f2, s))

    dispatch.run(
        model,
        model_config,
        progress=progress,
    )
