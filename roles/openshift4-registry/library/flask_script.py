#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Run a script through Python, with the local Flask app loaded.

See FlaskScriptTask.module_spec for supported task parameters.
"""

# 💡 To explore the Flask object model, try
#
#   oc -n redhat-quay exec -it $(oc -n redhat-quay get pod -o name |grep -e -quay-app- | head -1) -- flask shell
#
#   import data
#   import peewee
#   [getattr(data.database, t) for t in dir(data.database)
#    if isinstance(getattr(data.database, t), peewee.ModelBase) ]
#
# Choose one of the `peewee.ModelBase` instances so returned, and then say e.g.
#
#   list(data.database.OAuthApplication.select())
#

import inspect
import importlib.util
import warnings
from functools import update_wrapper

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.epfl_si.actions.plugins.module_utils.ansible_api import AnsibleResults
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import Postcondition, run_postcondition

try:
    from ansible.errors import AnsibleError
except ImportError:
    AnsibleError = Exception

deepcopy = __import__('copy').deepcopy


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


class FlaskScriptTask(object):
    module_spec = dict(
        supports_check_mode=True,
        argument_spec=dict(
            script=dict(type='str', default=None),
            postcondition_class=dict(type='str', default=None)))

    def __init__(self):
        self.module = AnsibleModule(**self.module_spec)
        self.result = AnsibleResults.empty()

    def run(self):
        check_mode = self.module.check_mode
        script =        self.module.params.get('script')
        postcondition_class = self.module.params.get('postcondition_class')

        if (script is None) == (postcondition_class is None):
            raise TypeError("Exactly one of `script` or `postcondition_class` must be set.")
        elif script is not None:
            if check_mode:
                return self.module.exit_json(skipped=True, reason="Cannot run `script` in check mode")
            else:
                imperative_locals = dict(result=self.result,
                                         **self.observability_helpers(self.result))
                self.exec_flask_script(script, imperative_locals)
                self.module.exit_json(**self.result)
        else:
            assert postcondition_class is not None
            oo_locals = dict(Postcondition=Postcondition,
                             **self.observability_helpers(self.result))
            for cls in self.load_flask_script_into_module(
                    'postcondition_class', postcondition_class,
                    oo_locals).values():
                if self.is_postcondition_subclass(cls):
                    AnsibleResults.update(
                        self.result,   # run_flask_postcondition() may also mutate this
                        self.run_flask_postcondition(self.construct_postcondition(cls)))
                    self.module.exit_json(**self.result)
            self.module.exit_json(failed=True,
                                  reason="Expected the `postcondition_class` code fragment to declare a Postcondition subclass")

    @with_flask_appcontext
    def exec_flask_script(self, script_text, globals):
        exec(script_text, globals)

    def load_flask_script_into_module(self, module_name, script_text, locals):
        # https://stackoverflow.com/a/60054149
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(module_name, loader=None))
        module_locals = module.__dict__
        module_locals.update(locals)
        self.exec_flask_script(script_text, module_locals)
        return module_locals

    def is_postcondition_subclass(self, cls):
        return (
            inspect.isclass(cls)
            and issubclass(cls, Postcondition)
            and cls is not Postcondition)

    def construct_postcondition(self, cls):
        if 'result' in inspect.signature(cls.__init__).parameters:
            return cls(result=self.result)
        else:
            return cls()

    @with_flask_appcontext
    def run_flask_postcondition(self, postcondition):
        return run_postcondition(postcondition, check_mode=self.module.check_mode)

    def observability_helpers(self, result_object):
        """Returns some functions that scripts may want to call, so as to signal their progress.

        To signal lack of progress, scripts should throw an exception instead.
        """
        def signal_changed(what):
            self.result['changed'] = True
            if not self.result.get('changes'):
                self.result['changes'] = []
            self.result['changes'].append(what)

        def log(what):
            if not self.result.get('log'):
                self.result['log'] = []
            self.result['log'].append(what)

        return dict(signal_changed=signal_changed, log=log)

if __name__ == '__main__':
    FlaskScriptTask().run()
