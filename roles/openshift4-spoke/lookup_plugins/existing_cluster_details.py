from base64 import b64decode
import os
import re
import subprocess
from ansible.plugins.lookup import LookupBase
from jinja2.runtime import Undefined

class OCError(Exception):
    def __init__(self, e):
        super(OCError, self).__init__("%s stderr: %s" % (e, e.stderr))
        self.stderr = e.stderr

    @property
    def unauthorized_message(self):
        stderr_lines = self.stderr.splitlines()
        if len(stderr_lines) == 0:
            return None
        if re.search(r'\bUnauthorized\b', stderr_lines[0]):
            return stderr_lines[0]
        else:
            return None

class LookupModule(LookupBase):
    """
    Checks whether a given cluster is already installed, and provide its Hive (meta)data

    Usage:
      lookup("existing_cluster_details", kubeconfig="/path/to/kubeconfig")

    Returns:
      { "clusterID": uuid,
        "infraID": "%s-%s" % (clusterShortname, uniqueRandomSuffix),
        "kubeconfig": a_giant_spew_of_yaml,
        "admin_credentials": { 'username': username, 'password': password }
      }                             # If successful

      jinja2.runtime.Undefined()    # If the passed kubeconfig file does not exist or contains stale credentials

      jinja2.runtime.Undefined()    # If the cluster is unreachable
    """
    def run(self, terms, kubeconfig, **kwargs):
        self.kubeconfig = kubeconfig

        returned = {}

        try:
            open(kubeconfig)
        except FileNotFoundError as e:
            return [Undefined(str(e))]

        try:
            returned["kubeconfig"] = self._oc_stdout("config", "view", "--flatten")

            # Gleaned from https://access.redhat.com/solutions/3826921 :
            returned["clusterID"] = self._oc_stdout("get", "clusterversion", "-o", "jsonpath={.items[].spec.clusterID}")
            returned["infraID"] = self._oc_stdout("get", "infrastructure", "-o", "jsonpath={.items[].status.infrastructureName}")

            # Courtesy of ../tasks/spoke-backdoor.yml:
            returned["admin_credentials"] = {
                "username": "kubeadmin",
                "password": b64decode(self._oc_stdout("get", "-n", "kube-system", "secret/kubeadmin",
                                                          "-o", "jsonpath={.data.kubeadmin-cleartext}"))
            }
        except OCError as e:
            unauthorized = e.unauthorized_message
            if unauthorized:
                return [Undefined(unauthorized)]
            else:
                raise e

        return [returned]

    def _oc_stdout (self, *args):
        try:
            return subprocess.run(["oc"] + list(args), capture_output=True, check=True,
                                  env=self._oc_env,
                                  encoding="ascii").stdout
        except subprocess.CalledProcessError as e:
            raise OCError(e)

    @property
    def _oc_env (self):
        env = {**os.environ}
        env["KUBECONFIG"] = self.kubeconfig
        return env
