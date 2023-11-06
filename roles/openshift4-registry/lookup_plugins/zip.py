"""
Look up a single file in a GitHub-style Zip archive.

Usage:

  lookup("zip",
              url="https://github.com/epfl-si/satosa-tequila/archive/refs/tags/v1.0.0.zip",
              path="config/saml2_backend.yaml")

"""

from collections import Counter
from io import BytesIO
import os
import urllib.request
from zipfile import ZipFile

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase

def cached_method (method):
    @functools.wraps(method)
    def wrapper (self, *args, **kwargs):
        key = (method.__name__, args, frozenset(kwargs.items()))

        if not hasattr(self, '_cache'):
            self._cache = {}

        if key not in self._cache:
            self._cache[key] = method(self, *args, **kwargs)

        return self._cache[key]

    return wrapper


class CloudZipfile(object):
    _cache = {}

    @classmethod
    def get(cls, uri):
        cache = cls._cache
        if uri not in cache:
            cache[uri] = cls(urllib.request.urlopen(uri).read())
        return cache[uri]

    def __init__(self, zipstring):
        self.zip = ZipFile(BytesIO(zipstring))

    @property
    def topdir(self):
        c = Counter()
        c.update(info.filename.split(os.pathsep)[0]
                 for info in self.zip.infolist())
        path, count = c.most_common()[0]
        return path

    def read_bytes(self, path_relative_to_topdir):
        with self.zip.open(self.topdir + path_relative_to_topdir) as f:
            return f.read()

    def read(self, path_relative_to_topdir):
        return self.read_bytes(path_relative_to_topdir).decode('utf-8')


class LookupModule (LookupBase):
    def run (self, terms, variables, url, path):

        return [CloudZipfile.get(url).read(path)]
