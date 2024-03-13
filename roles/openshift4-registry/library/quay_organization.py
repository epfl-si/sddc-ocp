#!/usr/bin/python
# -*- coding: utf-8 -*-

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import Postcondition
from ansible_collections.epfl_si.xaasible.plugins.module_utils.flask import run_flask_postcondition


try:
    from ansible.errors import AnsibleError
except ImportError:
    AnsibleError = Exception

def _get_existing_organization(name):
    from data.model.organization import get_organization
    from data.model import InvalidOrganizationException
    try:
        return get_organization(name)
    except InvalidOrganizationException:
        return None


class QuayOrganizationCreatedPostcondition(Postcondition):
    def __init__(self, name, email, owner_name):
        self.name = name
        self.email = email
        self.owner = owner_name

    def holds(self):
        org = _get_existing_organization(self.name)
        if org is None:
            return False

        if org.email != self.email:
            return False
        if not self._is_owner(org, self.owner):
            return False
        return True

    def enforce(self):
        org = _get_existing_organization(self.name)
        if org is None:
            from data.model.organization import create_organization
            from data.model.user import get_user
            create_organization(self.name, self.email,
                                get_user(self.owner))
            return dict(created=True)

        changed = {}
        if org.email != self.email:
            changed["email"] = dict(before=org.email, after=self.email)
            org.email = self.email

        if not self._is_owner(org, self.owner):
            changed["owner"] = {}
            owners_team = self._get_owner_team(org)
            if not owners_team:
                changed["owners"]["team_created"] = True
                owners_team = team.create_team("owners", org, "admin")

            from data.model.team import add_user_to_team
            from data.model.user import get_user
            add_user_to_team(get_user(self.owner), owners_team)
            changed["owners"]["member_added"] = self.owner

        if changed:
            org.save()
            return changed
        else:
            return False

    def _get_owner_team(self, org):
        from data.database import Team
        owner_teams = org.team_set.select().where(Team.name == "owners")
        try:
            return owner_teams[0]
        except IndexError:
            return None

    def _is_owner(self, org, owner_name):
        owners = self._get_owner_team(org)
        if not owners:
            return False

        from data.database import TeamMember
        from data.model.user import get_user
        return 1 == len(owners.teammember_set.select().where(
            TeamMember.user == get_user(owner_name)))


class QuayOrganizationDeletedPostcondition(Postcondition):
    def __init__(self, name):
        self.name = name

    def holds(self):
        return not _get_existing_organization(self.name)

    def enforce(self):
        from data.model.user import User, delete_user
        delete_user(User.get(User.username == self.name), [])
        return dict(changed="Deleted organization %s" % self.name)


class QuayOrganizationTask(object):
    module_spec = dict(
        argument_spec=dict(
            state=dict(type='str', default="present"),
            name=dict(type='str', default=None),
            email=dict(type='str', default=None),
            owner=dict(type='str', default=None)))

    def run(self):
        module = AnsibleModule(**self.module_spec)
        if module.params['state'] == 'present':
            postcondition = QuayOrganizationCreatedPostcondition(
                module.params['name'],
                module.params['email'],
                module.params['owner'])
        elif module.params['state'] == 'absent':
            postcondition = QuayOrganizationDeletedPostcondition(
                module.params['name'])
        else:
            raise AnsibleError('Unknown state: %s' % state)

        module.exit_json(**run_flask_postcondition(postcondition))


if __name__ == '__main__':
    QuayOrganizationTask().run()
