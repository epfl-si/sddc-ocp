class FilterModule(object):
    def filters(self):
        return {
            'any_starts_with': self.any_starts_with
        }

    def any_starts_with(self, list_of_strings, prefix):
        for s in list_of_strings:
            if s.startswith(prefix):
                return True
        return False
