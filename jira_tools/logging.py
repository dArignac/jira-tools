import sys


class Logging:
    def log(self, message):
        if self.options.debug:
            print(message, file=sys.stderr)
