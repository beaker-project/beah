# -*- test-case-name: beah.core.test.test_backends -*-

# Beah - Test harness. Part of Beaker project.
#
# Copyright (C) 2009 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from beah.core.errors import KilledException
class GoodBye(KilledException): pass

class BasicBackend(object):
    """Simple Backend, with no command input."""
    def __init__(self):
        self.controller = None
    def set_controller(self, controller=None):
        self.controller = controller
    def proc_error(self, evt):
        return False
    def proc_evt(self, evt, **flags):
        f = getattr(self, "proc_evt_"+evt.event(), None)
        if f:
            try:
                answ = f(evt)
                if answ is None:
                    return True
                return answ
            except:
                return self.proc_error(evt)
        return False
    def proc_evt_bye(self, evt):
        raise GoodBye("Controller said: \"bye\".")
    def close(self):
        pass

class ExtBackend(BasicBackend):
    def pre_proc(self, evt):
        return False
    def post_proc(self, evt, answ):
        return answ
    def proc_evt(self, evt, **flags):
        if self.pre_proc(evt):
            return True
        answ = BasicBackend.proc_evt(self, evt, **flags)
        return self.post_proc(evt, answ)


class ListQueue(object):

    def __init__(self):
        self.queue = []

    def _enqueue(self, obj):
        self.queue.append(obj)

    def push(self, obj):
        self._enqueue(obj)

    def top(self):
        return self.queue[0]

    def pop(self):
        return self.queue.pop(0)

    def ready(self):
        return True

    def empty(self):
        return not self.queue


class SerializingBackend(ExtBackend):

    """
    Backend to serialize events.

    event handlers (pre_proc, post_proc, proc_evt_*) have to call set_busy and
    set_idle. idle could be overridden, but implementor has to ensure _next_evt
    is called, e.g. by calling set_idle().
    """

    def __init__(self, queue):
        self.__idle = True
        self.__pop = False
        self.__evt_queue = queue
        ExtBackend.__init__(self)

    def set_busy(self, busy=True):
        self.set_idle(not busy)

    def set_idle(self, idle=True):
        self.__idle = idle
        self._next_evt()

    def idle(self):
        """
        Method returning True when backend is idle indicating next event could
        be processed.
        """
        return self.__idle

    def _queue_ready(self):
        return self.__evt_queue.ready()

    def _queue_evt(self, evt, **flags):
        self.__evt_queue.push([evt, flags])

    def _get_evt(self):
        return self.__evt_queue.top()

    def _pop_evt(self):
        return self.__evt_queue.pop()

    def proc_evt(self, evt, **flags):
        self._queue_evt(evt, **flags)
        self._next_evt()

    def _next_evt(self):
        if not self._queue_ready():
            return
        if self.idle() and self.__pop:
            self._pop_evt()
            self.__pop = False
        while not self.__evt_queue.empty() and self.idle():
            evt, flags = self._get_evt()
            try:
                ExtBackend.proc_evt(self, evt, **flags)
            finally:
                if self.idle():
                    self._pop_evt()
                else:
                    self.__pop = True

import pprint
class PprintBackend(ExtBackend):
    def __init__(self, width=80):
        self.width = 80
        self.pprinter = pprint.PrettyPrinter(width=width)
    def pre_proc(self, evt):
        self.pprinter.pprint(list(evt.printable()))
        return False

from simplejson import dumps
class PrintBackend(ExtBackend):
    def pre_proc(self, evt):
        print dumps(evt)
        return False

from sys import stderr
from beah.filters.cmdfilter import CmdFilter
from beah.core.constants import ECHO
class CmdBackend(ExtBackend):
    from sys import stdout

    def __init__(self):
        self.cf = CmdFilter()
        self.wait = False
        ExtBackend.__init__(self)

    def connection_made(self):
        print "\n" + self.prompt(),
        self.stdout.flush()

    def line_received(self, line):
        self.proc_input(line)
        if not self.wait:
            print self.prompt(),
            self.stdout.flush()

    def prompt(self):
        if self.controller:
            return "beah> "
        else:
            return "waiting for controller... "

    def set_controller(self, controller=None):
        ExtBackend.set_controller(self, controller)
        print "\n" + self.prompt(),
        self.stdout.flush()

    def proc_input(self, data):
        if not self.wait:
            cmd = self.cf.proc_line(data)
            if cmd:
                self.controller.proc_cmd(self, cmd)
                self.wait = True
        else:
            print "busy. waiting for echo..."

    def proc_evt_echo(self, evt):
        if self.wait:
            try:
                self.wait = False
                if evt.args()['rc'] == ECHO.OK:
                    print "OK"
                    return
                if evt.args()['rc'] == ECHO.NOT_IMPLEMENTED:
                    print "--- ERROR: Command is not implemented."
                    return
                if evt.args()['rc'] == ECHO.EXCEPTION:
                    print "--- ERROR: Command raised an exception."
                    print evt.args()['exception']
                    return
            finally:
                print self.prompt(),
                self.stdout.flush()

    def post_proc(self, evt, answ):
        if self.wait:
            pprint.pprint(evt)
        return answ

from beah.core import command
class CmdOnlyBackend(CmdBackend):
    def set_controller(self, controller=None):
        CmdBackend.set_controller(self, controller)
        if controller:
            self.controller.proc_cmd(self, command.no_output())


