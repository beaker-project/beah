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

from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol, ReconnectingClientFactory
from twisted.internet.error import DNSLookupError, NoRouteError
from beah.wires.internals import twadaptors, twmisc
from beah import config
from beah.core import event
from beah.misc import dict_update, jsonenv
import logging
import os

log = logging.getLogger('beah')

ENV_PATHNAME_TEMPLATE = 'beah_task_%s.env'

class TaskStdoutProtocol(ProcessProtocol):
    def __init__(self, task_id, task_protocol=twadaptors.TaskAdaptor_JSON):
        self.task_id = task_id
        self.task_protocol = task_protocol or twadaptors.TaskAdaptor_JSON
        self.task = None
        self.controller = None
        self.master = None

    def set_master(self):
        self.master = self.controller.get_master(self.task_id)
        self.master.timeout_handler = TimeoutHandler(self)
        self.master.killer = Killer(self)

    def connectionMade(self):
        log.info("%s:connectionMade", self.__class__.__name__)
        self.task = self.task_protocol()
        # FIXME: this is not very nice...
        self.task.send_cmd = lambda obj: self.transport.write(self.task.format(obj))
        self.task.task_id = self.task_id
        self.task.set_controller(self.controller)
        self.set_master()
        self.controller.task_started(self.task)

    def outReceived(self, data):
        self.task.dataReceived(data)

    def errReceived(self, data):
        self.task.lose_item(data)

    def processExited(self, reason):
        log.info("%s:processExited(%s)", self.__class__.__name__, reason)
        self.transport.closeStdin()

    def release(self):
        if self.master.timeout_handler is not None:
            self.master.timeout_handler.release()
            self.master.timeout_handler = None
        if self.master.killer is not None:
            self.master.killer.release()
            self.master.killer = None


    def processEnded(self, reason):
        log.info("%s:processEnded(%s)", self.__class__.__name__, reason)
        self.controller.task_finished(self.task, rc=twmisc.reason2rc(reason))
        self.release()

    def kill(self, signal='TERM', message=''):
        log.debug("%s:kill(%r, %r)", self.__class__.__name__, signal, message)
        self.transport.signalProcess(signal)
        evt = event.lwarning("Sending %s signal. Reason: %s" % (signal, message))
        self.task.proc_input(evt)

    def die(self, message):
        log.debug("%s:die(%r)", self.__class__.__name__, message)
        evt = event.warning("Giving Up. Reason: %s" % message)
        self.task.proc_input(evt)
        evt = event.end(self.task_id, -1)
        self.task.proc_input(evt)
        self.release()


def Spawn(host, port, proto=None, socket=''):
    def spawn(controller, backend, task_info, env, args):
        task_env = dict(env)
        # 1. set env.variables
        # BEAH_THOST - host name
        # BEAH_TPORT - port
        # BEAH_TSOCKET - socket
        # BEAH_TID - id of task - used to introduce itself when opening socket
        task_id = task_info['id']
        conf = config.get_conf('beah')
        env_file = os.path.join(conf.get('TASK', 'VAR_ROOT'),
                ENV_PATHNAME_TEMPLATE % task_id)
        dict_update(task_env,
                CALLED_BY_BEAH="1",
                BEAH_THOST=str(host),
                BEAH_TPORT=str(port),
                BEAH_TSOCKET=str(socket),
                BEAH_TID=str(task_id),
                BEAH_ROOT=conf.get('TASK', 'ROOT'),
                BEAH_ENV=env_file,
                )
        ll = conf.get('TASK', 'LOG')
        task_env.setdefault('BEAH_TASK_LOG', ll)
        task_env.setdefault('BEAH_TASK_CONSOLE', conf.get('TASK', 'CONSOLE_LOG', 'False'))
        task_env.setdefault('TERM', 'dumb')
        val = os.getenv('PYTHONPATH')
        if val:
            task_env['PYTHONPATH'] = val
        jsonenv.export_env(env_file, task_env)
        # 2. spawn a task
        protocol = (proto or TaskStdoutProtocol)(task_id)
        protocol.controller = controller
        log.debug('spawn: Environment: %r.', task_env)
        reactor.spawnProcess(protocol, task_info['file'],
                args=[task_info['file']]+(args or []), env=task_env)
        # FIXME: send an answer to backend(?)
        return protocol.task_protocol
    return spawn

class TaskFactory(ReconnectingClientFactory):
    def __init__(self, task, controller_protocol):
        self.task = task
        self.controller_protocol = controller_protocol

    ########################################
    # INHERITED METHODS:
    ########################################
    def startedConnecting(self, connector):
        log.info('%s: Started to connect.', self.__class__.__name__)

    def buildProtocol(self, addr):
        log.info('%s: Connected.  Address: %s', self.__class__.__name__, addr)
        log.info('%s: Resetting reconnection delay', self.__class__.__name__)
        self.resetDelay()
        controller = self.controller_protocol()
        controller.add_task(self.task)
        return controller

    def clientConnectionLost(self, connector, reason):
        log.info('%s: Lost connection.  Reason:%s',
                self.__class__.__name__, reason)
        self.task.set_controller()
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.info('%s: Connection failed. Reason:%s', self.__class__.__name__,
                reason)
        self.task.set_controller()
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

def start_task(conf, task, host=None, port=None,
        adaptor=twadaptors.ControllerAdaptor_Task_JSON, socket=None,
        ):
    factory = TaskFactory(task, adaptor)
    if os.name == 'posix':
        socket = socket or conf.get('TASK', 'SOCKET')
        if socket != '':
            return reactor.connectUNIX(socket, factory)
    host = host or conf.get('TASK', 'INTERFACE')
    port = port or int(conf.get('TASK', 'PORT'))
    if port != '':
        try:
            return reactor.connectTCP(host, int(port), factory)
        except (NoRouteError, DNSLookupError):
            return reactor.connectTCP('127.0.0.1', int(port), factory)

    raise EnvironmentError('Either socket or port must be given.')


def _cancel_delayed_call(instance, attr):
    """Stops and clears delayed call."""
    if instance and attr:
        delayed_call = getattr(instance, attr)
        if delayed_call is not None:
            if delayed_call.active():
                delayed_call.cancel()
            setattr(instance, attr, None)


class TimeoutHandler(object):

    def __init__(self, task_protocol):
        self.task_protocol = task_protocol
        self.delayed_call = None

    def set_timeout(self, timeout):
        if timeout <= 0:
            self.stop()
        else:
            self.start(timeout)

    def stop(self):
        log.debug("%s:stop()", self.__class__.__name__)
        _cancel_delayed_call(self, "delayed_call")

    def start(self, timeout):
        log.debug("%s:start(%s)", self.__class__.__name__, timeout)
        if self.delayed_call is not None:
            self.delayed_call.reset(timeout)
        else:
            self.delayed_call = reactor.callLater(timeout, self.kill)

    def kill(self):
        log.debug("%s:kill()", self.__class__.__name__)
        _cancel_delayed_call(self, "delayed_call")
        self.task_protocol.kill(message='Timeout has expired.')

    def release(self):
        self.stop()
        self.task_protocol = None


class Killer(object):

    """
    Handler for kill event.

    Class' kill method is used by controller to handle the event.

    This implementation attempts to send SIGTERM first and after further
    {TIMEOUT} seconds SIGKILL. If the process still runs we give up and let
    task_protocol handle the situation.

    """

    SIGNALS = ['TERM', 'KILL']
    TIMEOUT = 10

    def __init__(self, task_protocol):
        self.task_protocol = task_protocol
        self.signal = 0
        self.delayed_call = None

    def kill(self, message=None):
        """The main entry point."""
        log.debug("%s:kill()", self.__class__.__name__)
        _cancel_delayed_call(self, "delayed_call")
        if self.signal < len(self.SIGNALS):
            self.task_protocol.kill(signal=self.SIGNALS[self.signal],
                    message=message)
            self.signal += 1
            self.delayed_call = reactor.callLater(self.TIMEOUT, self.kill, message)
        else:
            # giving up!
            self.task_protocol.die("Process can not be killed.")

    def stop(self):
        """Stop kill in progress releasing delayed calls."""
        log.debug("%s:stop()", self.__class__.__name__)
        self.signal = 0
        _cancel_delayed_call(self, "delayed_call")

    def release(self):
        """Release resources."""
        self.stop()
        self.task_protocol = None

