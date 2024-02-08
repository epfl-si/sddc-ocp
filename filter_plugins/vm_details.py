"""
Accessors for VM objects returned by `lookup("vmware_vm")`
"""

class FilterModule(object):
    """
    Coerce operators for Jinja
    """
    def filters(self):
        return {
            'vm_ipv4': self.vm_ipv4
        }

    def vm_ipv4(self, vm):
        return vm.guest.ipAddress
