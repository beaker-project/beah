# -*- test-case-name: beah.backends.test.test_forwarder -*-

import logging

from twisted.trial import unittest
from twisted.internet import reactor

from beah.core import command, event
from beah.backends import forwarder
from beah.wires.internals.twserver import start_server
from beah import config

class TestIntegration(unittest.TestCase):

    def testIntegration(self):
        # CONFIG:
        config.beah_conf(args=[])
        conf = config.get_conf('beah')
        srv = start_server(conf=conf)
        log = logging.getLogger('backend')

        class FakeTask(object):
            origin = {'signature':'FakeTask'}
            task_id = 'no-id'
            def proc_cmd(self, cmd):
                log.debug("FakeTask.proc_cmd(%r)", cmd)

        class FakeBackend(object):
            def proc_evt(self, evt, **kwargs):
                log.debug("FakeBackend.proc_evt(%r, **%r)", evt, kwargs)

        t = FakeTask()
        reactor.callLater(2, srv.proc_evt, t, event.variable_set('say_hi', 'Hello World!'))
        #reactor.callLater(2.1, srv.proc_evt, t, event.variable_get('say_hi'))
        reactor.callLater(2.2, srv.proc_evt, t, event.variable_get('say_hi', dest='test.loop'))

        b = FakeBackend()
        reactor.callLater(3, srv.proc_cmd, b, command.kill())

        forwarder.main(args=[])
    testIntegration.skip = "The test does not clean the reactor properly."


