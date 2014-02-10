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

from beah.wires.internals.twmisc import twisted_logging, listen_loopback
from beah.wires.internals.twadaptors import BackendAdaptor_JSON, TaskAdaptor_JSON
from beah.wires.internals.twtask import Spawn
from beah.core.controller import Controller, MasterTask
from beah.misc import runtimes, make_log_handler, make_class_verbose, \
    str2log_level, ensuredir, parse_bool
from beah.misc.log_this import log_this
from beah import config
from twisted.internet import protocol
from twisted.internet import reactor
import logging
import os

log = logging.getLogger('beah')

class BackendListener(protocol.ServerFactory):
    def __init__(self, controller, backend_protocol=BackendAdaptor_JSON):
        self.protocol = backend_protocol or BackendAdaptor_JSON
        self.controller = controller

    def buildProtocol(self, addr):
        log.info('%s: Connected.  Address: %s', self.__class__.__name__, addr)
        backend = self.protocol()
        backend.client_addr = addr
        # FIXME: filterring requests for remote backends
        # - configuration, filterring,...
        #backend.set_cmd_filter()
        #if backend.client_addr != (127,0,0,1):
        #    pass
        backend.set_controller(self.controller)
        log.debug('%s: Connected [Done]', self.__class__.__name__)
        return backend

class TaskListener(protocol.ServerFactory):
    def __init__(self, controller, task_protocol=TaskAdaptor_JSON):
        self.protocol = task_protocol or TaskAdaptor_JSON
        self.controller = controller

    def buildProtocol(self, addr):
        log.info('%s: Connected.  Address: %s', self.__class__.__name__, addr)
        task = self.protocol()
        task.set_controller(self.controller)
        log.debug('%s: Connected [Done]', self.__class__.__name__)
        return task

def start_server(conf=None, backend_host=None, backend_port=None,
        backend_adaptor=BackendAdaptor_JSON,
        task_host=None, task_port=None,
        task_adaptor=TaskAdaptor_JSON, spawn=None):

    # CONFIG:
    if not conf:
        config.beah_conf()
        conf = config.get_conf('beah')

    # LOGGING:
    twisted_logging(log, level=logging.WARNING)
    log.setLevel(str2log_level(conf.get('CONTROLLER', 'LOG')))

    # Create a directory for runtime
    # FIXME: should try to create a temp path if following fails:
    ensuredir(conf.get('CONTROLLER', 'VAR_ROOT'))

    # Create a directory for logging and check permissions
    lp = conf.get('CONTROLLER', 'LOG_PATH')
    make_log_handler(log, lp, conf.get('CONTROLLER', 'LOG_FILE_NAME'),
            syslog=True, console=conf.get('CONTROLLER', 'CONSOLE_LOG', False))
    if parse_bool(config.get_conf('beah').get('CONTROLLER', 'DEVEL')):
        print_this = log_this(log.debug, True)
        make_class_verbose(Controller, print_this)
        make_class_verbose(MasterTask, print_this)

    # RUN:
    backend_host = backend_host or conf.get('BACKEND', 'INTERFACE')
    backend_port = backend_port or conf.get('BACKEND', 'PORT')
    task_host = task_host or conf.get('TASK', 'INTERFACE')
    task_port = task_port or int(conf.get('TASK', 'PORT'))
    if os.name == 'posix':
        if backend_port != '':
            backend_port = int(backend_port)
        backend_socket = conf.get('BACKEND', 'SOCKET')
        if task_port != '':
            task_port = int(task_port)
        task_socket = conf.get('TASK', 'SOCKET')
    else:
        backend_port = int(backend_port)
        backend_socket = ''
        task_port = int(task_port)
        task_socket = ''
    runtime = runtimes.ShelveRuntime(conf.get('CONTROLLER', 'RUNTIME_FILE_NAME'))
    runtime.vars = runtimes.TypeDict(runtime, 'vars')
    runtime.tasks = runtimes.TypeDict(runtime, 'tasks')
    controller = Controller(spawn or Spawn(task_host, task_port, socket=task_socket),  runtime=runtime)
    def on_killed():
        if not controller.backends:
            reactor.stop()
            return
        reactor.callLater(2, reactor.stop)
    controller.on_killed = on_killed
    log.info("################################")
    log.info("#   Starting a Controller...   #")
    log.info("################################")
    backend_listener = BackendListener(controller, backend_adaptor)
    if backend_port != '':
        if backend_host:
            listening = reactor.listenTCP(backend_port, backend_listener, interface=backend_host)
        else:
            listening = listen_loopback(backend_port, backend_listener)
        log.info("Controller: BackendListener listening on %s port %s",
                listening.getHost().host, listening.getHost().port)
    if backend_socket:
        if os.path.exists(backend_socket):
            # clean-up after e.g. system crash:
            log.warning("Controller: BackendListener cleaning %s", backend_socket)
            os.remove(backend_socket)
        log.info("Controller: BackendListener listening on %s", backend_socket)
        reactor.listenUNIX(backend_socket, backend_listener)
    task_listener = TaskListener(controller, task_adaptor)
    if task_port != '':
        if task_host:
            listening = reactor.listenTCP(task_port, task_listener, interface=task_host)
        else:
            listening = listen_loopback(task_port, task_listener)
        log.info("Controller: TaskListener listening on %s port %s",
                listening.getHost().host, listening.getHost().port)
    if task_socket:
        if os.path.exists(task_socket):
            # clean-up after e.g. system crash:
            log.warning("Controller: TaskListener cleaning %s", task_socket)
            os.remove(task_socket)
        log.info("Controller: TaskListener listening on %s", task_socket)
        reactor.listenUNIX(task_socket, task_listener)
    return controller

if __name__ == '__main__':
    start_server()
    reactor.run()

