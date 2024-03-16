#!/usr/bin/python
# -*- coding: utf-8 -*-

from functools import cached_property

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import Postcondition
from ansible.module_utils.flask import run_flask_postcondition


class QuayRepositoryCreatedPostcondition(Postcondition):
    def __init__(self,  organization, name, owner, visibility, permissions):
        self.organization = organization
        self.name = name
        self.owner = owner
        self.visibility = visibility if visibility is not None else "public"
        self.permissions = permissions

    def holds(self):
        return self._exists and self._permissions_match

    @property
    def _exists(self):
        from data.model.repository import get_repository
        return get_repository(self.organization, self.name) is not None

    @property
    def _permissions_match(self):
        for p in self.permissions:
            subject = _QuayRepositorySubject.construct(
                self.organization, self.name, p['subject'])
            if (subject.has(p['role']) !=
                (p.get('state', 'present') == 'present')):
                return False
        return True

    def enforce(self):
        from data.model.repository import create_repository
        from data.model.user import get_user

        changed = {}

        if not self._exists:
            user = get_user(self.owner)
            create_repository(
                self.organization, self.name, user, self.visibility)
            changed['created'] = True

        for p in self.permissions:
            subject = _QuayRepositorySubject.construct(
                self.organization, self.name, p['subject'])

            if 'permissions' not in changed:
                changed['permissions'] = {}
            if subject.moniker not in changed['permissions']:
                changed['permissions'][subject.moniker] = {}

            role = p['role']
            desired = p.get('state', 'present')
            if desired == 'present':
                subject.grant(role)
                changed['permissions'][subject.moniker][role] = 'granted'
            else:
                subject.revoke(role)
                changed['permissions'][subject.moniker][role] = 'revoked'

        return changed


class _QuayRepositorySubject (object):
    @classmethod
    def construct (cls, organization_name, repository_name, subject):
        if 'robot_account' in subject:
            return _QuayRepositoryRobotAccountSubject(
                organization_name, repository_name,
                robot_shortname=subject['robot_account']['shortname'])
        else:
            raise ValueError("Unknown kind of subject with keys: %s" %
                             " ".join(subject.keys()))

    def __init__ (self, organization, repository):
        self.organization = organization
        self.repository = repository


class _QuayRepositoryRobotAccountSubject (_QuayRepositorySubject):
    def __init__ (self, organization, repository, robot_shortname):
        super(_QuayRepositoryRobotAccountSubject, self).__init__(
            organization, repository)
        self.robot_shortname = robot_shortname

    @property
    def _robot_qualified_name (self):
        from util.names import format_robot_username

        return format_robot_username(self.organization, self.robot_shortname)

    @property
    def moniker(self):
      return self._robot_qualified_name

    @cached_property
    def _current_permissions (self):
        from data.model.permission import list_robot_permissions

        return list_robot_permissions(self._robot_qualified_name)

    def _invalidate_current_permissions(self):
        self.__dict__.pop('_current_permissions', None)

    def has (self, role):
        for rp in self._current_permissions:
            if rp.role.name == role:
                return True
        return False

    def grant (self, role):
        from data.model.permission import set_user_repo_permission
        set_user_repo_permission(
            self._robot_qualified_name,
            self.organization,
            self.repository,
            role)

    def revoke (self, unused_role):
        self.__revoke_all_roles()

    def __revoke_all_roles (self):
        from data.model.permission import delete_user_permission
        delete_user_permission(self._robot_qualified_name, self.organization,
                               self.repository)


class QuayRepositoryDeletedPostcondition(Postcondition):
    def __init__(self,  organization, name):
        self.organization = organization
        self.name = name

    def holds(self):
        return not self._exists

    def enforce(self):
        from data.model.user import User, delete_user
        delete_user(User.get(User.username == self.name), [])
        return dict(changed="Deleted organization %s" % self.name)


class QuayRepositoryTask(object):
    module_spec = dict(
        argument_spec=dict(
            state=dict(type='str', default="present"),
            organization=dict(type='str', default=None),
            name=dict(type='str', default=None),
            owner=dict(type='str', default=None),
            visibility=dict(type='str', default=None),
            permissions=dict(type='list', default=[])))

    def run(self):
        module = AnsibleModule(**self.module_spec)
        state = module.params['state']
        if state == 'present':
            postcondition = QuayRepositoryCreatedPostcondition(
                organization=module.params['organization'],
                name=module.params['name'],
                owner=module.params['owner'],
                visibility=module.params['visibility'],
                permissions=module.params['permissions'])
        elif state == 'absent':
            postcondition = QuayRepositoryDeletedPostcondition(
                module.params['organization'],
                module.params['name'])
        else:
            raise ValueError('Unknown state: %s' % state)

        module.exit_json(**run_flask_postcondition(postcondition))


if __name__ == '__main__':
    QuayRepositoryTask().run()
