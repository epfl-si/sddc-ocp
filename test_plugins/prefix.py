class TestModule(object):
    def tests(self):
        return {
            'prefix': self.prefix
        }

    def prefix(self, what, prefix):
        return what.startswith(prefix)
