# -*- test-case-name: beah.core.test.test_command -*-

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

"""
Commands are used to send instructions from Backend to Controller (and
eventually Task.)
"""

import exceptions
import sys
from beah.core import event, new_id, check_type
from beah.misc import setfname

################################################################################
# PUBLIC INTERFACE:
################################################################################
def ping(message=None):
    if message:
        return Command('ping', message=message)
    return Command('ping')

def PING(message=None):
    if message:
        return Command('PING', message=message)
    return Command('PING')

def run(file, name=None, env=None, args=None):
    if name is None:
        name = file
    return Command('run', task_info={'file':file, 'name':name}, env=env, args=args)

def run_this(script, name=None, env=None, args=None):
    return Command('run_this', script=script, task_info={'name':name}, env=env, args=args)

def flush():
    return Command('flush')

def kill():
    return Command('kill')

def no_input():
    return Command('no_input')

def no_output():
    return Command('no_output')

def variable_value(key, value, handle='', error=None, **kwargs):
    """Used to return a "variable's" value to task."""
    return Command('variable_value', key=key, value=value, handle=handle,
            error=error, **kwargs)

def answer(request, value, error=None):
    """Command used as an answer to an event identified by request.
    
    request - either an event instance or id."""
    request_id = request
    if not isinstance(request, basestring):
        request_id = event.event(request).id()
    return Command('answer', request_id=request_id, value=value, error=error)

def forward(event):
    """
    Used to forward an event to another controller.

    @event - the original event.

    event.forward_response could be used in answer. Sending answer is required
    before sending event.echo. command.forward is recommended afterwards, as
    connection could be closed.
    """
    return Command('forward', event=event)

################################################################################
# IMPLEMENTATION:
################################################################################
def command(cmd):
    if isinstance(cmd, Command):
        return cmd
    return Command(cmd)

def mkcommand(cmd, __doc__="", **kwargs):
    def cmdf(**kwargs):
        return Command(cmd)
    setfname(cmdf, cmd)
    cmdf.__doc__ = __doc__ or "Command %s" % cmd
    return cmdf

class Command(list):

    COMMAND = 1
    ID = 2
    ARGS = 3

    TESTTYPE = basestring

    def __init__(self, cmd, id=None, **kwargs):
        if isinstance(cmd, list):
            list.__init__(self, cmd)
            self[self.ARGS] = dict(cmd[self.ARGS]) # make a copy
            if isinstance(cmd, Command):
                return
        else:
            list.__init__(self, ['Command', None, None, None])
            self[self.COMMAND] = str(cmd)
            self[self.ID] = id
            self[self.ARGS] = dict(kwargs)
        if self[self.ID] is None:
            self[self.ID] = new_id()
        self.check()

    def check(self):
        if self[0] != 'Command':
            raise exceptions.TypeError('%r not permitted as %r[0]. Has to be \'Command\'' % (self[0], self))
        check_type("command", self.command(), self.TESTTYPE)
        check_type("id", self.id(), self.TESTTYPE)
        check_type("args", self.args(), dict)

    def command(self):
        return self[self.COMMAND]
    def id(self):
        return self[self.ID]
    def args(self):
        return self[self.ARGS]
    def arg(self, name, val=None):
        return self.args().get(name, val)
    def same_as(self, cmd):
        """
        Compare commands.

        This ignores id, which will be (usually) different.
        """
        if not isinstance(cmd, Command):
            cmd = Command(cmd)
        if self.command() != cmd.command():
            return False
        if self.command() == 'forward':
            a = self.args()
            ca = cmd.args()
            for k in a.keys():
                if k == 'event':
                    if not event.Event(a['event']).same_as(event.Event(ca.get('event', None))):
                        return False
                else:
                    if a[k] != ca.get(k, None):
                        return False
            return True
        return self.args() == cmd.args()

