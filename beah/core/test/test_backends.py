# -*- test-case-name: beah.core.test.test_backends -*-

from twisted.trial import unittest

from beah.core import backends, command

class TestCmdOnlyBackend(unittest.TestCase):

    def testMain(self):

        class FakeController(object):
            def __init__(self2, expected=None):
                self2.expected = expected
            def proc_cmd(self2, backend, cmd):
                if not cmd.same_as(self2.expected):
                    self.failUnlessEqual(cmd, self2.expected)

        be = backends.CmdOnlyBackend()
        be.set_controller(FakeController(command.no_output()))

        def test(be, input, output):
            be.controller.expected = output
            be.proc_input(input)

        test(be, 'ping', command.ping())
        test(be, 'PING a message', command.PING('a message'))
        test(be, 'run a_task', command.run('a_task'))


