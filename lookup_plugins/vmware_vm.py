from ansible_collections.community.vmware.plugins.module_utils.vmware import connect_to_api, get_all_objs
from ansible.plugins.lookup import LookupBase
from jinja2.runtime import Undefined
from pyVmomi import vim

# TODO: cache this on disk. (As each Ansible task creates another
# Python process, an in-memory cache is useless.)
def all_vms(hostname, port, username, password, validate_certs):
    api = connect_to_api(None, hostname=hostname, port=port, username=username, password=password, validate_certs=validate_certs)
    return get_all_objs(api, [vim.VirtualMachine], folder=None, recurse=True)

class LookupModule(LookupBase):
    def run(self, terms, credentials, variables=None, validate_certs=False, **kwargs):
        hostname = credentials["host"] if "host" in credentials else credentials["hostname"]
        port = credentials["port"] if "port" in credentials else 443
        username = credentials["user"] if "user" in credentials else credentials["username"]
        password = credentials["password"]

        def matches(vm, terms):
            for term in terms:
                if 'guest_name' in term:
                    if vm.summary.config.name != term['guest_name']:
                        return False

            return True

        matched = [vm for vm in all_vms(hostname, port, username, password, validate_certs)
                   if matches(vm, terms)]
        if len(matched) == 0:
            return [Undefined('lookup("vmware_vm", %s): not found in vSphere' % terms)]
        else:
            return matched
