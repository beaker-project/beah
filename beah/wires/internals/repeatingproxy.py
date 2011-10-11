# -*- test-case-name: beah.wires.internals.test.test_repeatingproxy -*-

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
Module to handle network failures when using XML-RPC.

CLASSES:

RepeatingProxy(twisted.web.xmlrpc.Proxy):
    handle network failures by auto-retrying after defined sublcass of
    failures.

"""

from twisted.internet import reactor
from twisted.web.xmlrpc import _QueryFactory, QueryProtocol
from twisted.protocols.policies import TimeoutMixin
from twisted.internet.defer import Deferred, TimeoutError, AlreadyCalledError
from twisted.internet.error import ConnectError, DNSLookupError, ConnectionLost, ConnectionDone

class ConstTimeout(object):
    """
    This object represents contant timeout: it will always return the same
    timeout.

    Call get() when the call is unsuccessful and get(False) should be called
    after successful call.
    """
    def __init__(self, timeout):
        self.timeout = float(timeout)
    def reset(self):
        return self.get()
    def incr(self):
        return self.get()
    def decr(self):
        return self.get()
    def get(self):
        return self.timeout

class IncreasingTimeout(object):
    """
    This object represents increasing timeout: every time incr() is called it
    will return larger timeout.
    """
    def __init__(self, timeout, max=600, factor=1.2, increment=0):
        self.timeout = float(timeout)
        self.max = float(max)
        self.factor = float(factor)
        self.increment = float(increment)
        self.reset()
    def reset(self):
        self._timeout = self.timeout
        return self.get()
    def incr(self):
        self._timeout = min(self.max, self._timeout * self.factor + self.increment)
        return self.get()
    def decr(self):
        return self.get()
    def get(self):
        return self._timeout

class AdaptiveTimeout(object):
    """
    This object represents adaptive timeout: every time incr() is called it
    will return larger timeout and decr() will return smaller value.
    """
    def __init__(self, timeout, max=600, factor=1.2, increment=0):
        self.timeout = float(timeout)
        self.max = float(max)
        self.factor = float(factor)
        self.increment = float(increment)
        self.reset()
    def reset(self):
        self._timeout = self.timeout
        return self.get()
    def incr(self):
        self._timeout = min(self.max, self._timeout * self.factor + self.increment)
        return self.get()
    def decr(self):
        self._timeout = max(self.timeout, self._timeout / self.factor)
        return self.get()
    def get(self):
        return self._timeout


class QueryWithTimeoutProtocol(QueryProtocol, TimeoutMixin):

    _VERBOSE = ('connectionMade', 'setTimeout', 'timeoutConnection',
            'connectionLost', 'handleResponseEnd')

    factory = None # Workaround to prevent pylint errors

    def connectionMade(self):
        QueryProtocol.connectionMade(self)
        if self.factory.rpc_timeout:
            self.setTimeout(self.factory.rpc_timeout.get())

    def connectionLost(self, reason):
        self.setTimeout(None)
        QueryProtocol.connectionLost(self, reason)

    def handleResponseEnd(self):
        QueryProtocol.handleResponseEnd(self)
        self.setTimeout(None)
        self.transport.loseConnection()

    def timeoutConnection(self):
        if self.factory.rpc_timeout:
            self.factory.rpc_timeout.incr()
        self.transport.loseConnection()

class QueryFactoryWithTimeout(_QueryFactory):
    protocol = QueryWithTimeoutProtocol
    rpc_timeout = IncreasingTimeout(10, max=60)
    _VERBOSE = ('startedConnecting', 'clientConnectionLost')


class repeatTimes(object):

    """
    Convenience repeat function to repeat call n times.
    """

    def __init__(self, n):
        self.n = n

    def __call__(self, fail):
        self.n -= 1
        return self.n >= 0


class repeatWithHandle(object):

    """
    Repeat wrapper with first_time handle, which is triggered on first failure
    only.
    """

    def __init__(self, repeat):
        self.repeat = repeat
        self.fired = False

    def first_time(self, fail):
        pass

    def __call__(self, fail):
        if not self.fired:
            self.first_time(fail)
            self.fired = True
        return self.repeat(fail)

        # FIXME: following does not work!
        #self.first_time(fail)
        #self.__call__ = self.repeat
        #return self.__call__(fail)


def repeatAlways(fail):
    """
    Convenience repeat function to repeat call forever.
    """
    return True


class RepeatingProxy(object):

    """
    Repeat XML-RPC until it is delivered.

    Set delay for retry timer and max_retries for maximal number of retries for
    individual calls.

    is_auto_retry_condition and is_accepted_failure are used to decide on
    action.

    Therte are two modes of operation: parallel and serializing.

    In parallel mode, submitted calls are processed in parallel: remote calls
    are considered independent, and when one fails it does not affect other
    already submitted calls.

    In serializing mode, submitted calls are cached, and are processed in
    order, later call waiting for previous to finish.

    This implementation will retry forever on ConnectError.

    There are two ways how to handle idle status:
    * by overriding on_idle
    * by calling when_idle which returns deferred (which is default on_idle's
      behavior.)
    """

    def __init__(self, proxy):
        """
        Initialize instance variables and pass all arguments to the base class.
        """
        # __cache: internal storage for pending remote calls and associated
        # deferreds
        self.__cache = []
        # __sleep: True when waiting for remore call to complete
        self.__sleep = False
        # __pending: number of pending requests
        self.__pending = 0
        # __on_idle: deferred which will be called when there are no more calls
        self.__on_idle = None
        # delay: number of seconds to wait before retrying
        self.delay = AdaptiveTimeout(60, max=600)
        # max_retries: maximal number of retrials. Unbound if none.
        self.max_retries = None
        # serializing: allow only one pending remote call when True
        self.serializing = False
        self.proxy = proxy
        # use factory with timeout...
        self.queryFactory = QueryFactoryWithTimeout

    def set_timeout(self, timeout):
        self.queryFactory.rpc_timeout = timeout

    def on_idle(self): # pylint: disable=E0202
        if self.__on_idle is not None:
            d = self.__on_idle
            self.__on_idle = None
            d.callback(True)

    def when_idle(self):
        if self.__on_idle is None:
            self.__on_idle = Deferred()
        return self.__on_idle

    def dump(self):
        return "%r %r" % (self,
                dict(cache=self.__cache, sleep=self.__sleep,
                    pending=self.__pending))

    def is_auto_retry_condition(self, fail):
        """
        Failures which are handled by retry unconditionally.

        When True is returned the call is rescheduled.
        """
        return fail.check(ConnectError, DNSLookupError, ConnectionLost, ConnectionDone)

    def is_accepted_failure(self, fail):
        """
        Accepted failures.

        When this method returns True, failure will be propagated to original
        deferred errback, otherwise will be retried.

        Example:
            return not fail.check(ConnectionRefusedError)
        """
        return True

    def on_ok(self, result, d):
        """
        Handler for successfull remote call.
        """
        self.__pending -= 1
        self.__sleep = False
        d.callback(result)
        self.delay.decr()
        self.send_next()

    def on_error(self, fail, m):
        """
        Handler for unsuccessfull remote call.
        """
        if fail.check(AlreadyCalledError):
            return -2
        self.__pending -= 1
        repeat = self.is_auto_retry_condition(fail)
        if m[5] is not None and m[5](fail):
            repeat = True
        if not repeat:
            if m[1] is None:
                count = 1
            else:
                m[1] -= 1
                count = m[1]
            if count <= 0 or self.is_accepted_failure(fail):
                self.__sleep = False
                m[0].errback(fail)
                self.delay.decr()
                self.send_next()
                return -1
        if self.serializing:
            self.insert(m)
        else:
            self.push(m)
        delay = self.delay.incr()
        reactor.callLater(delay, self.resend)
        self.__sleep = True
        return delay

    def resend(self):
        """
        Retry call after timeout.
        """
        self.__sleep = False
        self.send_next()

    def send_next(self):
        """
        Process next from queue.
        """
        if self.is_idle():
            self.on_idle()
            return False
        if self.is_empty() or self.__sleep:
            return False
        if self.serializing and self.__pending > 0:
            self.__sleep = True
            return False
        [d, count, method, args, kwargs, ffilter] = m = self.pop()
        if self.serializing:
            self.__sleep = True
        self.callRemote_(method, *args, **kwargs) \
                .addCallbacks(self.on_ok, self.on_error, callbackArgs=[d],
                        errbackArgs=[m])
        return True

    def callRemote_(self, method, *args, **kwargs):
        """
        Method to call superclass' callRemote
        """
        answ = self.proxy.callRemote(method, *args, **kwargs)
        self.__pending += 1
        return answ

    def _makeCall(self, method, args, kwargs, repeat):
        """
        Queue remote call.

        NOTE: Internal function. Do not use this directly.

        repeat: a callable allowing per-call failure handling.
        On failure, if this function returns True, call will be repeated.
        """
        # Method has to return new deferred, as the original one will be
        # consumed internally.
        d = Deferred()
        self.push([d, self.max_retries, method, args, kwargs, repeat])
        self.send_next()
        return d

    def repeatedRemote(self, repeat, method, *args, **kwargs):
        """
        Remote call allowing per-call failure handling.

        See _makeCall for repeat argument details.
        """
        return self._makeCall(method, args, kwargs, repeat)

    def callRemote(self, method, *args, **kwargs):
        """
        Overridden base class method, to handle retrying.
        """
        return self._makeCall(method, args, kwargs, None)

    def mustPassRemote(self, method, *args, **kwargs):
        """
        Remote call which accepts no failure.

        Call is repeated until it succeeds.
        """
        return self._makeCall(method, args, kwargs, repeatAlways)

    def is_idle(self):
        return self.__pending == 0 and self.is_empty()

    def is_empty(self):
        return not self.__cache

    def pop(self):
        return self.__cache.pop(0)

    def insert(self, m):
        self.__cache.insert(0, m)

    def push(self, m):
        self.__cache.append(m)

    _VERBOSE = ('callRemote', 'callRemote_', 'is_accepted_failure', 'is_auto_retry_condition')
    _MORE_VERBOSE = ('is_accepted_failure', 'on_ok', 'on_error',
                'resend', 'send_next', 'when_idle', 'is_empty', 'is_idle',
                'pop', 'insert', 'push')
    _VERBOSE_CLASSES = (QueryWithTimeoutProtocol, QueryFactoryWithTimeout, )

