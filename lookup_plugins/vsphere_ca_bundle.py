#!/usr/bin/env python3
from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError
import urllib.request
import ssl
import zipfile
import io
import fnmatch

class LookupModule(LookupBase):
    def run(self, terms, variables=None):
        url = terms[0]

        response = urllib.request.urlopen(url, context=ssl._create_unverified_context())
        if response.getcode() != 200:
            raise AnsibleError("Bad response code %d from %s", response.getcode(), url)

        cert_bundle = b""

        with zipfile.ZipFile(io.BytesIO(response.read()), 'r') as zip:
            for path in zip.namelist():
                if fnmatch.fnmatch(path, "certs/lin/*.0"):
                    with zip.open(path) as pseudo_file:
                        cert_bundle = cert_bundle + pseudo_file.read()

        # For whatever reason, Ansible wants us to return an array.
        return [cert_bundle.decode("ascii")]

if __name__ == '__main__':
    import sys
    print(LookupModule().run([sys.argv[1]])[0])
