# -*- test-case-name: beah.backends.test.test_forwarder -*-

from twisted.trial import unittest
from twisted.internet import reactor

from beah.core import command, event
from beah.backends import forwarder

class TestIntegration(unittest.TestCase):

    def testIntegration(self):
        from beah.bin.srv import main_srv
        srv = main_srv()

        class FakeTask(object):
            origin = {'signature':'FakeTask'}
            task_id = 'no-id'
            def proc_cmd(self, cmd):
                log.debug("FakeTask.proc_cmd(%r)", cmd)
        t = FakeTask()
        reactor.callLater(2, srv.proc_evt, t, event.variable_set('say_hi', 'Hello World!'))
        #reactor.callLater(2.1, srv.proc_evt, t, event.variable_get('say_hi'))
        reactor.callLater(2.2, srv.proc_evt, t, event.variable_get('say_hi', dest='test.loop'))

        class FakeBackend(object):
            def proc_evt(self, evt, **kwargs):
                log.debug("FakeBackend.proc_evt(%r, **%r)", evt, kwargs)
        b = FakeBackend()
        reactor.callLater(3, srv.proc_cmd, b, command.kill())

        forwarder.main()


