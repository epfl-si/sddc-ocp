#!/usr/bin/python
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.flask import run_flask_postcondition
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import Postcondition

class _QuayRobotAccountPostconditionBase (Postcondition):
    def __init__ (self, organization, robot_shortname):
        self.organization = organization
        self.robot_shortname = robot_shortname

    @property
    def _org (self):
        from data.model.organization import get_organization

        return get_organization(self.organization)  # Throws if unknown

    @property
    def _robot_and_token (self):
        from data.model.user import get_robot_and_metadata
        from data.model import InvalidRobotException
        try:
            robot, token, metadata = get_robot_and_metadata(self.robot_shortname, self._org)
            return [robot, token]
        except InvalidRobotException:
            return None

    @property
    def _robot_qualified_name (self):
        from util.names import format_robot_username

        return format_robot_username(self.organization, self.robot_shortname)

    @property
    def token (self):
        robot_and_token = self._robot_and_token
        return robot_and_token[1] if robot_and_token else None


class QuayRobotAccountCreatedPostcondition (_QuayRobotAccountPostconditionBase):
    def holds (self):
        return self._robot_and_token is not None

    def enforce (self):
        from data.model.user import create_robot

        robot, password = create_robot(
            self.robot_shortname, self._org,
            description="Created by `xaasible`")
        return True


class QuayRobotAccountDeletedPostcondition (_QuayRobotAccountPostconditionBase):
    def holds (self):
        return self._robot_and_token is None

    def enforce (self):
        from data.model.user import delete_robot

        delete_robot(self._robot_qualified_name)
        return True


class QuayRobotAccountTask (object):
    module_spec = dict(
        argument_spec=dict(
            state=dict(type='str', default="present"),
            organization=dict(type='str', default=None),
            robot_shortname=dict(type='str')))

    def run (self):
        module = AnsibleModule(**self.module_spec)
        state = module.params['state']
        if state == 'present':
            postcondition = QuayRobotAccountCreatedPostcondition(
                organization=module.params['organization'],
                robot_shortname=module.params['robot_shortname'])
        elif state == 'absent':
            postcondition = QuayRobotAccountDeletedPostcondition(
                organization=module.params['organization'],
                robot_shortname=module.params['robot_shortname'])
        else:
            raise ValueError('Unknown state: %s' % state)

        result = run_flask_postcondition(postcondition)
        if postcondition.token:
            result['token'] = postcondition.token

        module.exit_json(**result)


if __name__ == '__main__':
    QuayRobotAccountTask().run()
