#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Manage Quay's OAuth tokens (and OAuth applications)."""

from base64 import b64encode
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.epfl_si.actions.plugins.module_utils.postconditions import Postcondition
from ansible.module_utils.flask import run_flask_postcondition

class QuayTokenDeletedPostcondition(Postcondition):
    def __init__(self, token):
        self.token = token

    def holds(self):
        return len(self._get_tokens()) == 0

    def enforce(self):
        from data.database import OAuthAccessToken
        delete = self._get_tokens(for_delete=True)
        return { "tokens_deleted": delete.execute() }

    def _get_tokens(self, for_delete=False):
        from data.database import OAuthAccessToken
        from data.model.oauth import ACCESS_TOKEN_PREFIX_LENGTH
        query = OAuthAccessToken.delete if for_delete else OAuthAccessToken.select
        return query().where(
            OAuthAccessToken.token_name == self.token[:ACCESS_TOKEN_PREFIX_LENGTH])

class QuayTokenCreatedPostcondition(Postcondition):
    def __init__(self, organization, user, oauth_app, oauth_scopes, expires_seconds):
        self.organization = organization
        self.user = user
        self.oauth_app = oauth_app
        self.oauth_scopes = oauth_scopes
        self.expires_seconds = expires_seconds

    def holds(self):
        # TODO: we should (at least optionally) take the existing
        # (clear text) token as a parameter and validate it
        return False

    def enforce(self):
        from data.database import User, OAuthApplication, OAuthAccessToken
        from data.model.organization import get_organization
        from data.model.user import get_user
        from data.model.oauth import create_application, create_user_access_token

        changed = {}

        if 0 == len(OAuthApplication.select().join(User)
                    .where(User.username == self.organization,
                           OAuthApplication.name == self.oauth_app)):
            org = get_organization(self.organization)
            create_application(org, self.oauth_app, "", "")
            changed['application'] = 'created'

        user = get_user(self.user)
        oauth_app = OAuthApplication.select().where(OAuthApplication.name == self.oauth_app).get()

        created, access_token = create_user_access_token(
              user, oauth_app.client_id,
              self.oauth_scopes, expires_in=self.expires_seconds)
        changed['token'] = {
            'id': created.id
        }
        self.access_token = access_token

        return changed


class QuayTokenTask(object):
    module_spec = dict(
        argument_spec=dict(
            state=dict(type='str', default="present"),
            token=dict(type='str', default=None),
            organization=dict(type='str', default=None),
            user=dict(type='str', default=None),
            oauth_app=dict(type='str', default=None),
            oauth_scopes=dict(type='str', default=None),
            expires_seconds=dict(type='int', default=None)))

    def run(self):
        module = AnsibleModule(**self.module_spec)
        state = module.params['state']
        if state == 'present':
            postcondition = QuayTokenCreatedPostcondition(
                organization=module.params['organization'],
                user=module.params['user'],
                oauth_app=module.params['oauth_app'],
                oauth_scopes=module.params['oauth_scopes'],
                expires_seconds=module.params['expires_seconds'])
        elif state == 'absent':
            postcondition = QuayTokenDeletedPostcondition(
                module.params['token'])
        else:
            raise ValueError('Unknown state: %s' % state)

        result = run_flask_postcondition(postcondition)
        if hasattr(postcondition, "access_token"):
            result['access_token_base64'] = b64encode(
                postcondition.access_token.encode('ascii'))

        module.exit_json(**result)


if __name__ == '__main__':
    QuayTokenTask().run()
