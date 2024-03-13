"""Utilities to run some Python code as part of Flask."""

import warnings
from functools import update_wrapper
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import run_postcondition

def with_flask_appcontext(f):
    """Runs f without arguments, within the Flask application context.

    Reverse-engineered from flask/cli.py by removing all the click
    stuff, ignoring Flask load-time warnings.
    """

    def decorator(*args, **kwargs):
        from flask.cli import ScriptInfo
        with warnings.catch_warnings(record=True):  # i.e. ignore them
            app = ScriptInfo().load_app()
        with app.app_context():
            return f(*args, **kwargs)
    return update_wrapper(decorator, f)


@with_flask_appcontext
def run_flask_postcondition(postcondition, check_mode=False):
    return run_postcondition(postcondition, check_mode=check_mode)

