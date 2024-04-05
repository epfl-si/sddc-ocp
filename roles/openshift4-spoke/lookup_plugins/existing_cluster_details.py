from base64 import b64decode
import os
import re
import subprocess
import yaml
from ansible.plugins.lookup import LookupBase
from jinja2.runtime import Undefined

class OCError(Exception):
    def __new__ (cls, subprocess_error):
        if re.search(r'\bUnauthorized\b', subprocess_error.stderr):
            return super().__new__(OCUnauthorizedError)
        elif re.search(r'\bClient.Timeout exceeded\b', subprocess_error.stderr):
            return super().__new__(OCTimeoutError)
        else:
            return super().__new__(OCError)

    def __init__(self, subprocess_error):
        self.stderr = subprocess_error.stderr
        super(OCError, self).__init__("%s stderr: %s" % (subprocess_error, self.stderr))

    @property
    def first_error_line(self):
        stderr_lines = self.stderr.splitlines()
        return stderr_lines[0] if stderr_lines else None


class OCUnauthorizedError(OCError):
    pass


class OCTimeoutError(OCError):
    pass


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
        except OCUnauthorizedError as e:
            return [Undefined(e.first_error_line)]
        except OCTimeoutError as e:
            return [Undefined(e.first_error_line)]

        return [returned]

    def _oc_stdout (self, *args):
        try:
            return subprocess.run(["oc", "--request-timeout=5s"] + list(args), capture_output=True, check=True,
                                  env=self._oc_env,
                                  encoding="ascii").stdout
        except subprocess.CalledProcessError as e:
            raise OCError(e)

    @property
    def _oc_env (self):
        env = {**os.environ}
        env["KUBECONFIG"] = self.kubeconfig
        return env
