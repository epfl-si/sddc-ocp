from ansible.plugins.action import ActionBase
from ansible_collections.epfl_si.actions.plugins.module_utils.ansible_api import AnsibleActions

from copy import deepcopy


class PodNotFoundError (Exception):
    pass


class QuayActionBase (ActionBase):
    """Base class for actions that frob Quay's database.

    💡 Actions are run locally, inside Ansible's process. By contrast,
    modules are small pills of Python that get sent over the wire.
    """

    @AnsibleActions.run_method
    def run (self, task_args, ansible_api, task_vars):
        self.__ansible_api = ansible_api
        self.__task_vars = task_vars
        connection = ansible_api.make_connection(
            ansible_connection="oc",
            ansible_oc_kubeconfig=self.__kubeconfig,
            ansible_oc_namespace=self.__namespace,
            ansible_oc_pod=self.__any_pod_name,
            ansible_oc_container="quay-app",
            ansible_remote_tmp="/tmp")

        oc_friendly_task_vars = {}
        oc_friendly_task_vars.update(task_vars)
        oc_friendly_task_vars["ansible_python_interpreter"] = "/usr/bin/python3"

        return ansible_api.run_action(
            self.MODULE,
            task_args,
            vars=oc_friendly_task_vars,
            connection=connection)

    @property
    def __kubeconfig (self):
        if "inventory_hub_cluster" in self.__task_vars:
            return self.__ansible_api.expand_var(
                "{{ hostvars[inventory_hub_cluster].xaasible_kubeconfig }}")
        else:
            return self._get_task_var("xaasible_kubeconfig")

    @property
    def __namespace (self):
        return "redhat-quay"

    @property
    def __any_pod_name (self):
        """
        Returns the name of any `quay-app-*` pod.

        This is to use with `ansible_api.make_connection()`, so as to run
        Python code that accesses the Quay database.
        """
        pod_lookup_formula = """
          query('kubernetes.core.k8s', apiVersion='v1', kind='Pod',
                 kubeconfig=kubeconfig, namespace=namespace)
        """
        for pod in self.__ansible_api.expand_var(
            "{{ %s }}" % pod_lookup_formula,
            overrides=dict(
                kubeconfig=self.__kubeconfig,
                namespace=self.__namespace)):
            name = pod["metadata"]["name"]
            if "quay-app-" in name:
                return name
        raise PodNotFoundError("No pod named quay-app found in namespace %s" %
                               self.__namespace)


    def _get_task_var (self, var_name):
        unexpanded_var_value = self.__task_vars[var_name]
        return self.__ansible_api.expand_var(unexpanded_var_value)
