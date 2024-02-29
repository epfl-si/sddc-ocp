from base64 import b64decode
import os
import re
import subprocess
import yaml
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
      lookup("existing_cluster_details", cluster_name=inventory_hostname, kubeconfig="/path/to/kubeconfig")

    Returns:
      { "clusterID": uuid,
        "infraID": "%s-%s" % (clusterShortname, uniqueRandomSuffix),
        "kubeconfig": a_giant_spew_of_yaml,
        "admin_credentials": { 'username': username, 'password': password }
      }                             # If successful

      jinja2.runtime.Undefined()    # If the passed kubeconfig file does not exist or contains stale credentials

      jinja2.runtime.Undefined()    # If the cluster is unreachable
    """
    def run(self, terms, kubeconfig, cluster_name, **kwargs):
        self.kubeconfig = kubeconfig

        returned = {}

        try:
            with open(kubeconfig) as fd:
                kubeconfig_data = yaml.safe_load(fd)
        except FileNotFoundError as e:
            return [Undefined(str(e))]

        cluster_handle = None
        for context in kubeconfig_data["contexts"]:
            if context["name"] == kubeconfig_data["current-context"]:
                cluster_handle = context["context"]["cluster"]
                break

        if cluster_handle is None:
            return [Undefined("%s doesn't appear to have a valid current context" % kubeconfig)]

        cluster_server = None
        for cluster in kubeconfig_data["clusters"]:
            if cluster["name"] == cluster_handle:
                cluster_server = cluster["cluster"]["server"]
                break

        if cluster_server is None:
            raise ValueError("%s' current context doesn't appear to point to a functioning cluster" % kubeconfig)
        if cluster_name not in cluster_server:
            raise ValueError("It appears that %s is currently logged in to %s! (%s expected)" %
                             (kubeconfig, cluster_server, cluster_name))

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
