# -*- test-case-name: beah.core.test.test_backends -*-

from twisted.trial import unittest

from beah.core import backends, command

class FakeController(object):

    def __init__(self, test_case, expected=None):
        self.expected = expected
        self.test_case = test_case

    def proc_cmd(self, backend, cmd):
        if not cmd.same_as(self.expected):
            self.test_case.failUnlessEqual(cmd, self.expected)

class TestCmdOnlyBackend(unittest.TestCase):

    def testMain(self):

        be = backends.CmdOnlyBackend()
        be.set_controller(FakeController(test_case=self, expected=command.no_output()))

        def test(be, input, output):
            be.controller.expected = output
            be.proc_input(input)

        test(be, 'ping', command.ping())
        test(be, 'PING a message', command.PING('a message'))
        test(be, 'run a_task', command.run('a_task'))


