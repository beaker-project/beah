# -*- test-case-name: beah.core.test.test_command -*-

import traceback, sys

from twisted.trial import unittest

from beah.core import command

class TestCommand(unittest.TestCase):

    def make_cmd(self, cmd, *args, **kwargs):
        return list(command.Command(cmd, *args, **kwargs))

    def testMake(self):

        self.failUnlessEqual(['Command', 'ping', '99', {}], self.make_cmd('ping', id='99'))
        self.failUnlessEqual(['Command', 'ping', '99', {}], self.make_cmd(cmd='ping', id='99'))

        self.failUnlessEqual(['Command', 'ping', '99', {'value':1}], self.make_cmd(cmd='ping', value=1, id='99'))
        self.failUnlessEqual(['Command', 'ping', '99', {'value':1}], self.make_cmd(**{'cmd':'ping', 'value':1, 'id':'99'}))
        self.failUnlessEqual(['Command', 'ping', '99', {'value':1}], self.make_cmd(value=1, cmd='ping', id='99'))
        self.failUnlessEqual(['Command', 'ping', '99', {'value':1}], self.make_cmd(**{'value':1, 'cmd':'ping', 'id':'99'}))

        #self.failUnlessRaises(TypeError, self.make_cmd, 1)

