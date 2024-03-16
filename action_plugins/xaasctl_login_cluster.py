import os
import subprocess
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display
from ansible_collections.epfl_si.actions.plugins.module_utils.ansible_api import AnsibleActions

display = Display()


class ActionModule (ActionBase):
    """Custom Ansible action to ensure working OpenShift credentials.

    Task arguments:
       to_cluster     The name of the cluster to log into; defaults to
                      `inventory_hostname`.
    """
    @AnsibleActions.run_method
    def run (self, task_args, ansible_api, task_vars):
        to_cluster = task_args.get("to_cluster")
        if to_cluster is not None:
            kubeconfig = task_vars["hostvars"][to_cluster]["xaasible_kubeconfig"]
        else:
            to_cluster = task_vars["inventory_hostname"]
            kubeconfig = task_vars["xaasible_kubeconfig"]

        env = dict(**os.environ)
        env["KUBECONFIG"] = ansible_api.expand_var(kubeconfig)
        try:
            subprocess.run(
                ["oc", "get", "namespaces"],
                check=True, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {}
        except subprocess.CalledProcessError:
            cmd = ["./xaasctl", "login-cluster", to_cluster]
            display.v(" ".join(cmd))
            subprocess.run(cmd, check=True, env=env)
            return { "changed": True }
