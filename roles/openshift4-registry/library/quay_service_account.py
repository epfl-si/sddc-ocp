#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Manage Quay's service accounts."""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import Postcondition
from ansible_collections.epfl_si.xaasible.plugins.module_utils.flask import run_flask_postcondition


class QuayServiceAccountDeletedPostcondition(Postcondition):
    def __init__(self, name):
        self.name = name

    def holds(self):
        from data.model.user import get_user
        return get_user(self.name) is None

    def enforce(self):
        from data.model.user import get_user, delete_user

        service_account = get_user(self.name)
        if service_account is None:
            return False

        delete_user(service_account, [])
        return {'deleted': self.name}


class QuayServiceAccountCreatedPostcondition(Postcondition):
    def __init__(self, name):
        self.name = name

    def holds(self):
        from data.model.user import get_user
        return get_user(self.name) is not None

    def enforce(self):
        from data.model.user import create_user_noverify
        create_user_noverify(self.name, None, email_required=False).save()
        return {'created': self.name}


class QuayServiceAccountTask(object):
    module_spec = dict(
        argument_spec=dict(
            state=dict(type='str', default="present"),
            name=dict(type='str', default=None)))

    def run(self):
        module = AnsibleModule(**self.module_spec)
        name = module.params['name']
        if module.params['state'] == 'present':
            postcondition = QuayServiceAccountCreatedPostcondition(
                name=name)
        elif module.params['state'] == 'absent':
            postcondition = QuayServiceAccountDeletedPostcondition(
                name=name)
        else:
            raise AnsibleError('Unknown state: %s' % state)

        module.exit_json(**run_flask_postcondition(postcondition))


if __name__ == '__main__':
    QuayServiceAccountTask().run()
