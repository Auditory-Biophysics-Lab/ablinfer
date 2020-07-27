import os
from flask import Flask

app = Flask(__name__)
app.config.from_object("ablinfer.inferserver.default_settings")
if os.environ.get("INFERSERVER_SETTINGS") is not None:
    app.config.from_envvar("INFERSERVER_SETTINGS")

from .views import main
