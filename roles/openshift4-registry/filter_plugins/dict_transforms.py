"""Parsing Python is hard, let's have Jinja filters instead."""

from copy import copy

class FilterModule(object):
    def filters(self):
        return {
            'dictify': self.dictify,
            'map_dict_defaults' : self.map_dict_defaults
        }

    def dictify(self, l, by_key):
        return dict((item[by_key], item) for item in l)

    def map_dict_defaults(self, l, defaults):
        return [self.dict_merge(defaults, item) for item in l]

    def dict_merge(self, d1, d2):
        d = d1.copy()
        d.update(d2)
        return d
