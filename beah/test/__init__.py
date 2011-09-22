from twisted.internet.base import DelayedCall


class twisted_debug(object):

    def set(self):
        self.saved = DelayedCall.debug
        DelayedCall.debug = True

    def restore(self):
        DelayedCall.debug = self.saved
        del self.saved

    def __call__(self, call, *args, **kwargs):
        self.set()
        try:
            call(*args, **kwargs)
        finally:
            self.restore()

