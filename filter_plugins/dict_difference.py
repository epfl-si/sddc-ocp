class FilterModule(object):
    """
    Like `| difference(...)`, except on dict keys.
    """
    def filters(self):
        return {
            'dict_difference': self.dict_difference
        }

    def dict_difference(self, dict, exclude):
        ret = dict.copy()
        for k in exclude:
            del ret[k]
        return ret
