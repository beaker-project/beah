# -*- test-case-name: beah.filters.test.test_cmdfilter -*-

import os

from twisted.trial import unittest

from beah.core import command
from beah.filters import cmdfilter

class TestCmdFilter(unittest.TestCase):

    cp = cmdfilter.CmdFilter()

    def _test_(self, line, expected):
        result = self.cp.proc_line(line)
        if not result.same_as(expected):
            self.failUnlessEqual(result, expected)

    def testRun(self):

        self._test_('r a',
                command.run(os.path.abspath('a'),
                    name='a', args=[], env={}))

        self._test_('run a_task',
                command.run(os.path.abspath('a_task'),
                    name='a_task', args=[], env={}))

        self._test_('run -n NAME a_task',
                command.run(os.path.abspath('a_task'),
                    name='NAME', args=[], env={}))

        self._test_('run -D VAR=VAL -D VAR2=VAL2 a_task',
                command.run(os.path.abspath('a_task'),
                    name='a_task', args=[], env={'VAR':'VAL', 'VAR2':'VAL2'}))

        self._test_('run a_task arg1 arg2',
                command.run(os.path.abspath('a_task'),
                    name='a_task', args=['arg1', 'arg2'], env={}))

    def testCommands(self):
        self._test_('ping', command.ping())
        self._test_('ping hello world', command.ping('hello world'))
        self._test_('PING', command.PING())
        self._test_('PING hello world', command.PING('hello world'))
        self._test_('kill', command.command('kill'))

        # self.cp.proc_line('help')

    def testQuit(self):
        self.failUnlessRaises(StopIteration, self.cp.proc_line, 'quit')

