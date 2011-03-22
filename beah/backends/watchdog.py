# Beah - Test harness. Part of Beaker project.
#
# Copyright (C) 2011 Red Hat, Inc.
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

'''
Backend to handle watchdogs.

This backend will watch relevant events and before watchdog expires will run
certain handlers to collect data and analyse them.

WatchdogBackend creates Task instance per each task id it encounters and the
Task maintains task's status, handles the events and also calls the handlers
before the watchdog expires.

To register a handler create new distribute/setuptools plugin with entrypoint
as defined by WATCHDOG_ENTRYPOINT.

To start the client use the main function.

'''

import os
import logging

from twisted.internet import reactor, defer

from beah import config
from beah.core import command, event
from beah.core.backends import ExtBackend
from beah.wires.internals.twbackend import start_backend, log_handler
from beah.wires.internals.twmisc import CallRegularly
from beah.misc import make_class_verbose
from beah.misc.log_this import log_this
from beah.plugins import load_plugins


WATCHDOG_ENTRYPOINT = 'beah.watchdog_expired'
MIN_TIMEOUT = 300


def beah_check(task):
    '''
    Run beah-check.

    Try running as "original" task - i.e. with same BEAH_TID.

    If it can not be started via beah run it anyway...

    '''
    run_cmd = command.run('/bin/bash',
            name='beah-check',
            env={'TASKID': task.id_},
            args=('-c', 'BEAH_TID=%s beah-check' % task.id_))
    if not task.backend.send_cmd(run_cmd):
        os.spawnlp(os.P_WAIT, 'beah-check')


DEFAULT_HANDLERS = {'beah_check': beah_check}


class Task(object):

    '''
    Object handling events for a particular task.

    On instantiation:
    - has to ensure the watchdog is obtained.
    - call the expired handlers if watchdog can not be obtained.

    Before the watchdog expires:
    - check its value against the server
    - call the expired handlers if it is really low or can not be obtained.

    Class variables:

    - QUERY_TIMEOUT - status_watchdog call will expire after QUERY_TIMEOUT
                      seconds

    - QUERY_EXPIRED - after status_watchdog expires QUERY_EXPIRED times expier
                      handlers are called

    '''

    _VERBOSE = ['start', 'online', 'query_watchdog', 'on_expired', 'on_watchdog', 'query_timeout', '_set_watchdog', 'set_watchdog', ]

    QUERY_TIMEOUT = 60
    QUERY_EXPIRED = 5

    def __init__(self, backend, id_, handlers):
        self.backend = backend
        self.id_ = id_
        self.origin = {'id': id_, 'source': backend.name}
        self.watchdog_call = None # call which will trigger on watchdog
        self.timeout_call = None # call which will trigger on query timeout
        self.query_timed_out = 0 # number of times the query has timed out
        self.has_expired = False # has the watchdog expired already?
        self.handlers = handlers

    def start(self):
        '''Initialize the instance.'''
        if not self.watchdog_call:
            self.query_watchdog()

    def online(self):
        '''Backend is connected to controller.'''
        if self.timeout_call:
            self.timeout_call.cance()
            self.timeout_call = None
            self.query_watchdog()
        elif not self.watchdog_call:
            self.query_watchdog()

    def query_watchdog(self):
        '''Try to read the actual value of watchdog.'''
        if not self.timeout_call:
            if self.backend.send_cmd(command.forward(event.query_watchdog(origin=self.origin))):
                self.timeout_call = reactor.callLater(self.QUERY_TIMEOUT, self.query_timeout)
            elif self.watchdog_call is None:
                # we can not make call to the controller: set expired handler:
                self._set_watchdog(self.QUERY_EXPIRED * self.QUERY_TIMEOUT)

    def on_expired(self):
        '''Armageddon! Watchdog expiration is near!'''
        # run all watchdog handlers - use plugins here...
        self.backend.log.error('The task %s has expired! Triggering handlers.', self.id_)
        for name, handler in self.handlers.iteritems():
            try:
                handler(self)
            except:
                self.backend.log.exception('Handler %r raised an exception.', name)

    def on_watchdog(self):
        '''\
        Watchdog expiration about to happen.

        Try to query the value first. Only then call on_expired.

        '''
        self.watchdog_call = None
        if self.has_expired:
            self.on_expired()
        else:
            self.has_expired = True
            self.query_watchdog()

    def query_timeout(self):
        '''Handler for wathcdog query timeout.'''
        self.timeout_call = None
        if self.has_expired:
            self.backend.log.error('Watchdog call for task %s has timed out. Triggering expired handler.', self.id_)
            self.on_expired()
        else:
            self.query_timed_out += 1
            if self.query_timed_out == self.QUERY_EXPIRED:
                # could not obtain watchdog in resonable time: trigger expired handler
                self.backend.log.error('Watchdog call for task %s has timed out %s times. Triggering expired handler.', self.id_, self.query_timed_out)
                self.on_expired()
            else:
                if self.query_timed_out == 1:
                    self.backend.log.warning('Watchdog call for task %s has timed out.', self.id_)
                self.query_watchdog()

    def _set_watchdog(self, timeout):
        '''Schedule a call to handle approaching watchdog expiration.'''
        if self.watchdog_call:
            self.watchdog_call.reset(timeout)
        else:
            self.watchdog_call = reactor.callLater(timeout, self.on_watchdog)

    def set_watchdog(self, watchdog):
        '''Method called on changes to watchdog's value.'''
        if self.timeout_call:
            self.timeout_call.cancel()
            self.timeout_call = None
            self.query_timed_out = 0
        timeout = watchdog - self.backend.timeout
        expired = timeout <= 0
        if expired:
            if not self.has_expired:
                self.has_expired = True
                self.on_expired()
        else:
            if self.has_expired:
                self.backend.log.info('The task %s was extended...', self.id_)
                self.has_expired = False
            self._set_watchdog(timeout)

    def clean(self, attrs):
        '''
        Clean-up attributes requiring special handling.

        attrs - list of attributes to reset. Reset all when empty.

        '''
        if attrs is None:
            attrs = ('watchdog_call', 'timeout_call')
        for attr in attrs:
            if attr in ('watchdog_call', 'timeout_call'):
                call = getattr(self, attr, None)
                if call:
                    setattr(self, attr, None)
                    call.cancel()

    def close(self):
        '''
        Clean Up method called when task is deleted.

        This must stop all timeouts.

        '''
        self.clean(None)


class WatchdogBackend(ExtBackend):

    '''
    Dispatcher object to create and maintain collection of Task instances and
    route events to them.

    Watchdog is queried if task without known watchdog is met so it is not
    necessary to keep state. This is also more reliable, as on reboot e.g. the
    system clock could be changed (obtained from ntp server) and estimated
    watchdog time may be wrong.

    If event is received and the task instance does not exist the objects it
    created anyway - we may still want to wait for completed event in case of
    end event or the service might have been restarted in case of
    extend_watchdog.

    '''

    _VERBOSE = ['set_controller', 'query_watchdogs', 'send_cmd',
            'proc_evt_start', 'proc_evt_end', 'proc_evt_completed',
            'proc_evt_extend_watchdog', ]

    def __init__(self, conf, log, handlers, Task=Task):
        self.conf = conf
        self.timeout = max(int(conf.get('DEFAULT', 'TIMEOUT')), MIN_TIMEOUT)
        self.name = conf.get('DEFAULT', 'NAME')
        self.log = log
        self.handlers = handlers
        self.Task = Task
        self.tasks = {}

    def start(self):
        '''Initialize instance.'''
        # it may be desirable to call query_watchdogs to send query_watchdog to
        # all running tasks
        pass

    def set_controller(self, controller=None):
        '''Handle server going online/offline.'''
        ExtBackend.set_controller(self, controller)
        if controller:
            for task in self.tasks.values():
                task.online()

    def proc_evt_start(self, evt):
        '''Process start event.'''
        tid = evt.task_id()
        t = self.tasks.get(tid, None)
        if t is None:
            t = self.tasks[tid] = self.Task(self, tid, self.handlers)
            t.start()
        else:
            self.log.warning('Task %r already exists!', tid)

    def proc_evt_end(self, evt):
        '''Process end event.'''
        tid = evt.task_id()
        t = self.tasks.get(tid, None)
        if t is None:
            self.log.warning('Task %r does not exist. Creating new one.', tid)
            t = self.tasks[tid] = self.Task(self, tid, self.handlers)
        t.start()

    def proc_evt_completed(self, evt):
        '''Process completed event.'''
        tid = evt.task_id()
        t = self.tasks.pop(tid, None)
        if t:
            t.close()
        else:
            self.log.warning('Task %r does not exist!', tid)

    def proc_evt_extend_watchdog(self, evt):
        '''Process extend_watchdog event.'''
        tid = evt.task_id()
        t = self.tasks.get(tid, None)
        if t is None:
            self.log.warning('Task %r does not exist. Creating new one.', tid)
            t = self.tasks[tid] = self.Task(self, tid, self.handlers)
        t.start()
        t.set_watchdog(evt.arg('timeout'))

    def query_watchdogs(self):
        '''Broadcasts query_watchdog to all tasks.'''
        for task in self.tasks.values():
            task.query_watchdog()

    def send_cmd(self, cmd):
        '''Sends a command to controller.'''
        if self.controller:
            self.controller.proc_cmd(self, cmd)
            return True
        else:
            return False


def start_watchdog_backend(conf):
    '''Starts a watchdog backend with specified configuration.'''
    log = logging.getLogger('backend')
    if config.parse_bool(conf.get('DEFAULT', 'DEVEL')):
        print_this = log_this(lambda s: log.debug(s), log_on=True)
        make_class_verbose(WatchdogBackend, print_this)
        make_class_verbose(Task, print_this)
    handlers = dict(DEFAULT_HANDLERS)
    load_plugins(WATCHDOG_ENTRYPOINT, handlers)
    backend = WatchdogBackend(conf=conf, log=log, handlers=handlers)
    query_interval = int(conf.get('DEFAULT', 'QUERY_WATCHDOG'))
    if query_interval > 0:
        watchdogs_request = CallRegularly(query_interval, backend.query_watchdogs)
        reactor.addSystemEventTrigger('before', 'shutdown', watchdogs_request.stop)
    # Start a default TCP client:
    backend.start()
    start_backend(backend)


def watchdog_opts(opt, conf):
    '''\
    Watchdog backend specific command line options.

    This is used to override OptionParser opt to store additional options into
    conf dictionary.

    '''
    def timeout_cb(option, opt_str, value, parser):
        '''Process timeout option.'''
        conf['TIMEOUT'] = str(value)
    opt.add_option('-t', '--timeout',
            action='callback', callback=timeout_cb, type='int',
            help='Fire watchdog handler TIMEOUT seconds before it exipres.')
    def query_cb(option, opt_str, value, parser):
        '''Process query-watchdog option.'''
        conf['QUERY_WATCHDOG'] = str(value)
    opt.add_option('-Q', '--query-watchdog', metavar='QUERY_WATCHDOG',
            action='callback', callback=query_cb, type='int',
            help='Query watchdog every QUERY_WATCHDOG seconds.')
    return opt


def defaults():
    '''Default configuration for watchdog backend.'''
    d = config.backend_defaults()
    d.update({
            'NAME':'beah_watchdog_backend',
            'TIMEOUT':'300',
            'QUERY_WATCHDOG':'-1',
            })
    return d


def configure():
    '''\
    Returns a watchdog backend configuration.

    This uses command line options, environment and config.file as sources in
    that order.

    '''
    config.backend_conf(env_var='BEAH_WATCHDOG_CONF', filename='beah_watchdog.conf',
            defaults=defaults(), overrides=config.backend_opts(option_adder=watchdog_opts))
    return config.get_conf('beah-backend')


def main():
    '''Configures and starts the backend.'''
    conf = configure()
    log_handler()
    start_watchdog_backend(conf)
    reactor.run()


