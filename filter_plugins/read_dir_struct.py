import fnmatch
import os

class FilterModule(object):
    """
    Turn a directory into a structure (in order to make a ConfigMap out of it)
    """
    def filters(self):
        return {
            'read_dir_struct': self.read_dir_struct
        }

    def read_dir_struct(self, path, glob):
        ret = {}
        with os.scandir(path) as entries:
            for entry in entries:
                if fnmatch.fnmatch(entry.name, glob) and entry.is_file():
                    with open(entry.path) as r:
                        ret[entry.name] = r.read()
        return ret
