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

import traceback
import exceptions
import logging
from beah.core import event, command
from beah.core.constants import ECHO
from beah.misc import Raiser, localhost, format_exc, dict_update, log_flush
from beah import config

from beah.system import Executable

################################################################################
# Logging:
################################################################################
log = logging.getLogger('beah')


################################################################################
# MasterTask:
################################################################################
class MasterTask(object):

    """
    Class keeping task's status and common task data.

    Use make_new to create a new instance.

    """

    def make_new(cls, task_id, runtime, make_new=False):
        """
        Make a new instance of MasterTask from runtime.

        make_new - if True allows creating a new object from scratch, otherwise
                   None is returned when no data exist in runtime.
        """
        t = runtime.tasks.get(task_id, None)
        if t is None and not make_new:
            instance = None
        else:
            instance = cls(task_id, runtime)
            if t:
                # get defaults from runtime:
                instance.done = t.get('done', False)
                instance.exit_code = t.get('exit_code', 0)
            else:
                # write defaults to runtime
                instance.set_done(False,  0)
        return instance
    make_new = classmethod(make_new)

    def __init__(self, task_id, runtime):
        self.task_id = task_id
        self.runtime = runtime
        self.done = False
        self.exit_code = 0
        self.details = {}

    def dump(self, indent='', verbose=False):
        if self.get_done():
            status = "Finished(exit_code=%s)" % (self.get_exit_code(),)
        else:
            status = "Running"
        answ = "%s%s: %s\n" % (indent, self.task_id, status)
        if verbose:
            if self.details:
                answ += "%s  %s\n" % (indent, self.details)
        return answ

    def update_details(self, details):
        self.details.update(details)

    def get_done(self):
        return self.done

    def get_exit_code(self):
        return self.exit_code

    def set_done(self, done, exit_code):
        self.done = done
        self.exit_code = exit_code
        task_info = self.runtime.tasks.get(self.task_id, {})
        task_info.update({'done': done, 'exit_code': exit_code})
        self.runtime.tasks[self.task_id] = task_info

################################################################################
# Controller class:
################################################################################
from beah.core.errors import ServerKilled
class Controller(object):
    """Controller class. Processing commands and events. Creating tasks."""

    __origin = {'class':'controller'}

    __ON_KILLED = staticmethod(Raiser(ServerKilled, "Aaargh, I was killed!"))
    _VERBOSE = ('add_backend', 'remove_backend', 'add_task', 'remove_task',
            'find_task', 'proc_evt', 'send_evt', 'task_started',
            'task_finished', 'handle_exception', 'proc_cmd', 'generate_evt',
            'proc_cmd_forward', 'proc_cmd_variable_value', 'proc_cmd_ping',
            'proc_cmd_PING', 'proc_cmd_config', 'proc_cmd_run',
            'proc_cmd_run_this', 'proc_cmd_kill', 'proc_cmd_dump',
            'proc_cmd_no_input', 'proc_cmd_no_output')

    def __init__(self, spawn_task, on_killed=None):
        self.spawn_task = spawn_task
        self.tasks = [] # list of connected tasks
        self.backends = []
        self.masters = {} # task objects
        self.out_backends = []
        self.conf = {}
        self.killed = False
        self.on_killed = on_killed or self.__ON_KILLED
        self.__waiting_tasks = {}

    def add_backend(self, backend):
        if backend and not (backend in self.backends):
            self.backends.append(backend)
            self.out_backends.append(backend)
            for k, v in self.__waiting_tasks.items():
                backend.proc_evt(v[0])
            return True

    def remove_backend(self, backend):
        if backend and backend in self.backends:
            self.backends.remove(backend)
            if backend in self.out_backends:
                self.out_backends.remove(backend)
            if self.killed and not self.backends:
                # All backends were removed and controller was killed - call
                # on_killed handler
                self.on_killed()
            return True

    def add_task(self, task):
        if task and not (task in self.tasks):
            if 'origin' not in dir(task):
                task.origin = {}
            task_id = getattr(task, 'task_id', None)
            origin_id = task.origin.get('id', None)
            if origin_id is not None:
                if task_id is None:
                    task.task_id = origin_id
                elif task_id != origin_id:
                    log.error("Task %r: origin id (%r) and task_id (%r) do not match. Setting to origin id.", task, origin_id, task_id)
                    task.task_id = origin_id
            else:
                task.task_id = task.origin['id'] = task_id
            self.tasks.append(task)
            return True

    def remove_task(self, task):
        if task and task in self.tasks:
            self.tasks.remove(task)
            return True

    def find_task(self, task_id):
        for task in self.tasks:
            if (task.task_id == task_id):
                return task
        return None

    def get_master(self, task_id, make_new=False):
        master = self.masters.get(task_id, None)
        if master is None:
            master = MasterTask.make_new(task_id, self.runtime, make_new=make_new)
            if master is not None:
                self.masters[task_id] = master
        return master

    def set_task(self, task, evt):
        if task.task_id is None:
            task_id =  evt.task_id()
            if task_id:
                task.task_id = task.origin['id'] = task_id
                return True
            else:
                return False
        else:
            return False

    def proc_local_variable_set(self, evt):
        key = evt.arg('key')
        method = evt.arg('method', event.VARIABLE_SET_METHOD.SET)
        value = evt.arg('value')
        if method != event.VARIABLE_SET_METHOD.SET:
            val = value
            value = self.runtime.vars.get(key, [])
            if method == event.VARIABLE_SET_METHOD.APPEND:
                value.append(val)
            elif method == event.VARIABLE_SET_METHOD.ADD:
                if val not in value:
                    value.append(val)
                else:
                    return False
            elif method == event.VARIABLE_SET_METHOD.DELETE:
                if val in value:
                    value.remove(val)
                else:
                    return False
            else:
                log.warning("variable_set: method %s not supported.", method)
                return False
        self.runtime.vars[key] = value
        return True

    PROC_VARIABLES = {
            event.VARIABLE_METHOD.COUNT:(lambda: [0], lambda x, k, v: x.__setitem__(0, x[0]+1)),
            event.VARIABLE_METHOD.LIST:(lambda: [], lambda x, k, v: x.append(k)),
            event.VARIABLE_METHOD.DICT:(lambda: {}, lambda x, k, v: x.__setitem__(k, v)),
            }

    def proc_local_variables(self, evt):
        method = evt.arg('method', event.VARIABLE_METHOD.DEFINED)
        answ, foldf = self.PROC_VARIABLES.get(method, (lambda: False, None))
        answ = answ()
        if foldf is None:
            for key in evt.arg('keys'):
                if self.runtime.vars.has_key(key):
                    answ = True
                    break
        else:
            for key in evt.arg('keys'):
                if self.runtime.vars.has_key(key):
                    foldf(answ, key, self.runtime.vars[key])
        if method == event.VARIABLE_METHOD.COUNT:
            return answ[0]
        return answ

    def log_event(self, task, evt):
        evev = evt.event()
        if evev == 'completed':
            log.info('Task %s finished and has submitted all results.', task.task_id)

    def proc_evt(self, task, evt):
        """
        Process Event received from task.

        @task is the Task, which sent the event.
        @evt is an event. Should be an instance of Event class.

        This is the only method mandatory for Task side Controller-Adaptor.
        """
        log.debug("Controller: proc_evt(..., %r)", evt)
        self.log_event(task, evt)
        evev = evt.event()
        handler = getattr(self, "proc_evt_"+evev, None)
        if handler:
            try:
                if handler(task, evt):
                    return
            except:
                self.handle_exception("Handling %s raised an exception." %
                        evt.event())
        orig = evt.origin()
        if not orig.has_key('id'):
            orig['id'] = task.task_id
        self.send_evt(evt, to_all=(evev in ('flush',)))

    def proc_evt_introduce(self, task, evt):
        """Process introduce event."""
        self.set_task(task, evt)
        task.origin['source'] = "socket"
        # Returning now as the event is not necessary any more.
        return True

    def proc_evt_variable_set(self, task, evt):
        """Process variable_set event."""
        handle = evt.arg('handle', '')
        dest = evt.arg('dest', '')
        if handle == '' and localhost(dest):
            self.proc_local_variable_set(evt)
            return True
        else:
            pass

    def proc_evt_variable_get(self, task, evt):
        """Process variable_get event."""
        handle = evt.arg('handle', '')
        dest = evt.arg('dest', '')
        if handle == '' and localhost(dest):
            key = evt.arg('key')
            if self.runtime.vars.has_key(key):
                value = self.runtime.vars[key]
                task.proc_cmd(command.variable_value(key, value,
                    handle=handle, dest=dest))
            else:
                task.proc_cmd(command.variable_value(key, None,
                    handle=handle, error="Undefined variable.", dest=dest))
            return True
        else:
            key = evt.arg('key')
            s = repr(("command.variable_value", key, handle, dest))
            if self.__waiting_tasks.has_key(s):
                _, l = self.__waiting_tasks[s]
                if task not in l:
                    l.append(task)
                    log.debug("Controller.__waiting_tasks=%r", self.__waiting_tasks)
                return True
            _, l = self.__waiting_tasks[s] = (evt, [task])
            log.debug("Controller.__waiting_tasks=%r", self.__waiting_tasks)

    def proc_evt_variables(self, task, evt):
        """Process variables event."""
        handle = evt.arg('handle', '')
        dest = evt.arg('dest', '')
        if handle == '' and localhost(dest):
            task.proc_cmd(command.answer(evt.id(), self.proc_local_variables(evt)))
            return True
        else:
            s = repr(("command.answer", evt.id()))
            self.__waiting_tasks[s] = (evt, [task])

    def send_evt(self, evt, to_all=False):
        #cmd_str = "%s\n" % json.dumps(evt)
        if not to_all:
            (backends, flags) = (self.out_backends, {})
        else:
            (backends, flags) = (self.backends, {'broadcast': True})
        for backend in backends:
            try:
                backend.proc_evt(evt, **flags)
            except:
                self.handle_exception("Writing to backend %r failed." % backend)

    def task_started(self, task):
        log.info("Task %s has started.", task.task_id)
        self.add_task(task)
        self.generate_evt(event.start(task.task_id))

    def task_finished(self, task, rc):
        self.generate_evt(event.end(task.task_id, rc))
        self.remove_task(task)
        master = self.get_master(task.task_id)
        if master:
            master.set_done(True, rc)
        log.info("Task %s has finished.", task.task_id)
        log_flush(log)

    def handle_exception(self, message="Exception raised."):
        log.error("Controller: %s %s", message, format_exc())

    def proc_cmd(self, backend, cmd):
        """Process Command received from backend.

        @backend is the backend, which issued the command.
        @cmd is a command. Should be an instance of Command class.

        This is the only method mandatory for Backend side
        Controller-Adaptor."""
        log.debug("Controller: proc_cmd(..., %r)", cmd)
        handler = getattr(self, "proc_cmd_"+cmd.command(), None)
        if not handler:
            evt = event.echo(cmd, ECHO.NOT_IMPLEMENTED, origin=self.__origin)
        else:
            evt = event.echo(cmd, ECHO.OK, origin=self.__origin)
            try:
                handler(backend, cmd, evt)
            except:
                self.handle_exception("Handling %s raised an exception." %
                        cmd.command())
                dict_update(evt.args(),
                        rc=ECHO.EXCEPTION,
                        exception=format_exc())
        log.debug("Controller: echo(%r)", evt)
        backend.proc_evt(evt, explicit=True)

    def generate_evt(self, evt, to_all=False):
        """Send a new generated event.

        Use this method for sending newly generated events, i.e. not an echo,
        and not when forwarding events from tasks.

        to_all - if True, send to all backends, including no_output BE's
        """
        log.debug("Controller: generate_evt(..., %r, %r)", evt, to_all)
        self.send_evt(evt, to_all)

    class BackendFakeTask(object):
        def __init__(self, controller, backend, forward_id):
            self.controller = controller
            self.backend = backend
            self.forward_id = forward_id
            self.origin = {'signature':'BackendFakeTask'}
            self.task_id = 'no-id'

        def proc_cmd(self, cmd):
            evt = event.forward_response(cmd, self.forward_id)
            self.backend.proc_evt(evt, explicit=True)

    def proc_cmd_forward(self, backend, cmd, echo_evt):
        evt = event.event(cmd.arg('event'))
        evev = evt.event()
        # FIXME: incomming events filter - CHECK
        if evev not in ['variable_get', 'variable_set', 'variables', 'completed', 'extend_watchdog', 'update_watchdog']:
            echo_evt.args()['rc'] = ECHO.EXCEPTION
            echo_evt.args()['message'] = 'Event %r is not permitted here.' % evev
            return
        fake_task = self.BackendFakeTask(self, backend, cmd.id())
        self.proc_evt(fake_task, evt)

    def proc_answer(self, cmd, wait_id):
        _, l = self.__waiting_tasks.get(wait_id, (None, None))
        log.debug("Controller.__waiting_tasks[%r]=%r", wait_id, l)
        if l is not None:
            for task in l:
                log.debug("Controller: %s.proc_cmd(%r)", task, cmd)
                task.proc_cmd(cmd)
            del self.__waiting_tasks[wait_id]
        log.debug("Controller.__waiting_tasks=%r", self.__waiting_tasks)

    def proc_cmd_answer(self, backend, cmd, echo_evt):
        s = repr(("command.answer", cmd.arg("request_id")))
        self.proc_answer(cmd, s)

    def proc_cmd_variable_value(self, backend, cmd, echo_evt):
        s = repr(("command.variable_value", cmd.arg("key"), cmd.arg("handle"), cmd.arg("dest")))
        self.proc_answer(cmd, s)

    def proc_cmd_ping(self, backend, cmd, echo_evt):
        evt = event.Event('pong', message=cmd.arg('message', None))
        log.debug("Controller: backend.proc_evt(%r)", evt)
        backend.proc_evt(evt, explicit=True)

    def proc_cmd_PING(self, backend, cmd, echo_evt):
        self.generate_evt(event.Event('PONG', message=cmd.arg('message', None)))

    def proc_cmd_config(self, backend, cmd, echo_evt):
        self.conf.update(cmd.args())

    # REFACTOR: This should be a class
    def run_task(self, backend, task_info, task_env, task_args, echo_evt):
        task_id = task_info['id']
        master = self.get_master(task_id, make_new=True)
        master.update_details({'info': task_info, 'env': task_env, 'args': task_args})
        if master.get_done():
            echo_evt.args()['rc'] = ECHO.EXCEPTION
            echo_evt.args()['message'] = 'Task %r finished, exit code %s.' % (task_id, master.get_exit_code())
            return
        if self.find_task(task_id) is not None:
            echo_evt.args()['rc'] = ECHO.DUPLICATE
            echo_evt.args()['message'] = 'The task with id == %r is already running.' % task_id
            return
        self.spawn_task(self, backend, task_info, task_env, task_args)

    def proc_cmd_run(self, backend, cmd, echo_evt):
        task_info = dict(cmd.arg('task_info'))
        task_id = cmd.id()
        task_info['id'] = task_id
        task_env = dict(cmd.arg('env') or {})
        task_args = list(cmd.arg('args') or [])
        self.run_task(backend, task_info, task_env, task_args, echo_evt)

    def proc_cmd_run_this(self, backend, cmd, echo_evt):
        # FIXME: This looks dangerous! Is future BE filter enough? Disable!
        se = Executable()
        # FIXME: windows? need different ext and different default.
        se.content = lambda: se.write_line(cmd.arg('script', "#!/bin/sh\nexit 1"))
        se.make()
        task_info = dict(cmd.arg('task_info'))
        task_info['id'] = cmd.id()
        task_info['file'] = se.executable
        # FIXME!!! save task_info
        task_env = dict(cmd.arg('env') or {})
        task_args = list(cmd.arg('args') or [])
        self.run_task(backend, task_info, task_env, task_args, echo_evt)

    def proc_cmd_kill(self, backend, cmd, echo_evt):
        # FIXME: are there any running tasks? - expects kill --force
        # FIXME: [optional] broadcast SIGINT to children
        # FIXME: [optional] add timeout - if there are still some backends
        # running, close anyway...
        self.killed = True
        self.generate_evt(event.Event('bye', message='killed'), to_all=True)
        self.on_killed()

    def proc_cmd_flush(self, backend, cmd, echo_evt):
        self.generate_evt(event.flush(), to_all=True)

    def proc_cmd_dump(self, backend, cmd, echo_evt):
        answ = ""

        answ += "\n== Backends ==\n"
        if self.backends:
            for be in self.backends:
                if be:
                    str = " "
                else:
                    str = "-"
                answ += "%s %s\n" % (str, be)
        else:
            answ += "None\n"

        answ += "\n== Tasks ==\n"
        if self.masters:
            for master in self.masters.values():
                answ += master.dump(indent='', verbose=True) + "\n"
        else:
            answ += "None\n"

        answ += "\n=== Connections ===\n"
        if self.tasks:
            for t in self.tasks:
                answ += "%s\n" % t
        else:
            answ += "None\n"

        if self.conf:
            answ += "\n== Config ==\n%s\n" % (self.conf,)

        if self.runtime.vars:
            answ += "\n== Variables ==\n"
            for k in sorted(self.runtime.vars.keys()):
                answ += "%r=%r\n" % (k, self.runtime.vars[k])

        if self.killed:
            answ += "\n== Killed ==\nTrue\n"

        evt = event.Event('dump', message=answ)
        log.debug("Controller: backend.proc_evt(%r)", evt)
        backend.proc_evt(evt, explicit=True)

        log.info('%s', answ)

    def proc_cmd_no_input(self, backend, cmd, echo_evt):
        pass

    def proc_cmd_no_output(self, backend, cmd, echo_evt):
        if backend in self.out_backends:
            self.out_backends.remove(backend)

