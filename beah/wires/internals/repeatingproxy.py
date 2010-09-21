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
from twisted.web.xmlrpc import Proxy, _QueryFactory, QueryProtocol
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


class RepeatingProxy(Proxy):

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

    def __init__(self, *args, **kwargs):
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
        Proxy.__init__(self, *args, **kwargs)
        # use factory with timeout...
        self.queryFactory = QueryFactoryWithTimeout

    def set_timeout(self, timeout):
        self.queryFactory.rpc_timeout = timeout

    def on_idle(self):
        if self.__on_idle is not None:
            d = self.__on_idle
            self.__on_idle = None
            d.callback(True)

    def when_idle(self):
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
            return
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
                return
        if self.serializing:
            self.insert(m)
        else:
            self.push(m)
        reactor.callLater(self.delay.incr(), self.resend)
        self.__sleep = True

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
        answ = Proxy.callRemote(self, method, *args, **kwargs)
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
    _MORE_VERBOSE = ('is_auto_retry_condition', 'is_accepted_failure', 'on_ok', 'on_error',
                'resend', 'send_next', 'when_idle', 'is_empty', 'is_idle',
                'pop', 'insert', 'push')
    _VERBOSE_CLASSES = (QueryWithTimeoutProtocol, QueryFactoryWithTimeout, )

if __name__ == '__main__':

    import exceptions
    import xmlrpclib
    from twisted.web.xmlrpc import XMLRPC
    from twisted.web import server
    import time
    import sys
    from beah.misc.log_this import log_this
    from beah.misc import make_class_verbose

    for i in range(7):
        assert repeatAlways(i)
    r6 = repeatTimes(6)
    for i in range(6):
        assert r6(i)
    assert not r6(7)
    del r6
    class repeatWithMemory(repeatWithHandle):
        def __init__(self, repeat):
            self.x = None
            repeatWithHandle.__init__(self, repeat)
        def first_time(self, fail):
            self.x = fail
    def testr6(i, expected_return, expected_x):
        ret = r6(i)
        if ret != expected_return:
            assert False, "r6(i) is %s and not %s as expected." % (ret, expected_return)
        if r6.x != expected_x:
            assert False, "r6.x is %s and not %s as expected." % (r6.x, expected_x)
    r6 = repeatWithMemory(repeatTimes(6))
    assert r6.x is None
    testr6(0, True, 0)
    testr6(1, True, 0)
    r6.x = None
    for i in range(4):
        testr6(2+i, True, None)
    testr6(7, False, None)
    try:
        testr6(8, False, 0)
        raise Error("Failure was expected.")
    except AssertionError:
        pass
    try:
        testr6(8, True, None)
        raise Error("Failure was expected.")
    except AssertionError:
        pass

    def printf_w_timestamp(s):
        #ts = time.strftime("%Y%m%d-%H%M%S")
        ts = time.time()
        print("%.2f: %s" % (ts, s))
        sys.stdout.flush()
    printf = printf_w_timestamp
    print_this = log_this(printf)

    ct = ConstTimeout(10)
    assert ct.get() == 10
    assert ct.incr() == 10
    assert ct.incr() == 10
    assert ct.incr() == 10
    assert ct.decr() == 10
    assert ct.decr() == 10
    assert ct.decr() == 10
    assert ct.get() == 10

    def TestIT():
        def check(it, itn):
            assert itn == it.get()
            assert itn == it.decr()
            assert itn <= it.max
            assert itn >= it.timeout
        it = IncreasingTimeout(10)
        itn = itp = it.get()
        assert itp == 10
        while itn < it.max:
            itn = it.incr()
            printf(itn)
            check(it, itn)
            assert itn > itp
            itp = itn
        assert itn == it.max
        itn = it.incr()
        check(it, itn)
        assert itn == it.max
    TestIT()

    def TestAT():
        def check(it, itn):
            assert itn == it.get()
            assert itn <= it.max
            assert itn >= it.timeout
        it = AdaptiveTimeout(10)
        itn = itp = it.get()
        assert itp == 10
        while itn < it.max:
            itn = it.incr()
            check(it, itn)
            assert itn > itp
            itp = itn
        assert itn == it.max
        itn = it.incr()
        check(it, itn)
        assert itn == it.max
        while itn > it.timeout:
            itn = it.decr()
            check(it, itn)
            assert itn < itp
            itp = itn
        assert itn == it.timeout
        itn = it.decr()
        check(it, itn)
        assert itn == it.timeout
    TestAT()

    class Result(object):

        def __init__(self, print_passed=False):
            self.results = []
            self.result = [0, 0]
            self.print_passed = print_passed

        def add(self, pass_, message):
            self.results.append((pass_, message))
            if pass_:
                self.result[1] += 1
            else:
                self.result[0] += 1

        def __str__(self):
            answ = ""
            for result in self.results:
                if not self.print_passed and result[0]:
                    continue
                answ += "%s\n" % result[1]
            answ += "%d Passed\n%d Failed" % (self.result[1], self.result[0])
            return answ

    results = Result()

    def chk(result, method, result_ok, expected_ok):
        pass_ = result_ok == expected_ok
        message = ("%s: method %s resulted in %s %s%s" % (
                pass_ and "OK" or "ERROR",
                method,
                pass_ and "expected" or "unexpected",
                result_ok and "pass" or "failure",
                '', #":\n%s" % result,
                ))
        results.add(pass_, message)
        printf(message)
        return None
    chk = print_this(chk)

    def rem_call(proxy, method, exp_, args=(), repeat=None):
        if repeat is None:
            return proxy.callRemote(method, *args) \
                    .addCallbacks(chk, chk,
                            callbackArgs=[method, True, exp_],
                            errbackArgs=[method, False, exp_])
        else:
            return proxy.repeatedRemote(repeat, method, *args) \
                    .addCallbacks(chk, chk,
                            callbackArgs=[method, True, exp_],
                            errbackArgs=[method, False, exp_])
    rem_call = print_this(rem_call)

    class TestHandler(XMLRPC):
        _VERBOSE = ('xmlrpc_test', 'xmlrpc_test_exc', 'xmlrpc_test_exc2',
                'xmlrpc_test_long_call')
        def xmlrpc_retry_set(self, n):
            self.retries = n
        def xmlrpc_retry(self):
            self.retries -= 1
            if self.retries >= 0:
                raise exceptions.RuntimeError("Sorry. Try again...")
            return "Finally OK"
        def xmlrpc_test(self): return "OK"
        def xmlrpc_test_exc(self): raise exceptions.RuntimeError
        def xmlrpc_test_exc2(self): raise exceptions.NotImplementedError
        def xmlrpc_test_long_call(self, delay=12):
            d = Deferred()
            reactor.callLater(delay, d.callback, True)
            return d

    make_class_verbose(RepeatingProxy, print_this)
    make_class_verbose(TestHandler, print_this)
    p = RepeatingProxy(url='http://127.0.0.1:54123/')
    #def accepted_failure(fail):
    #    if fail.check(exceptions.NotImplementedError):
    #        # This does not work :-(
    #        return True
    #    if fail.check(xmlrpclib.Fault):
    #        # This would work:
    #        return True
    #    return False
    #accepted_failure = print_this(accepted_failure)
    #p.is_accepted_failure = accepted_failure
    p.RPC_TIMEOUT = 0.75
    p.TIMEOUT_FACTOR = 1.5
    p.DELAY_TIMEOUT = 0.5
    p.LONG_CALL = 3.0

    p.delay = AdaptiveTimeout(p.DELAY_TIMEOUT, factor=p.TIMEOUT_FACTOR)
    p.set_timeout(IncreasingTimeout(p.RPC_TIMEOUT, factor=p.TIMEOUT_FACTOR))
    p.max_retries = 6
    print 80*"="
    print "Serializing RepeatingProxy:"
    print 80*"="
    p.serializing = True
    def run_again(result):
        print 80*"="
        print "Not serializing RepeatingProxy:"
        print 80*"="
        p.serializing = False
        p.set_timeout(IncreasingTimeout(p.DELAY_TIMEOUT, factor=p.TIMEOUT_FACTOR))
        p.when_idle().addCallback(stopper(1))
        rem_call(p, 'test', True)
        rem_call(p, 'test', True)
        rem_call(p, 'test2', False)
        rem_call(p, 'test_exc', False)
        rem_call(p, 'test_exc2', False)
        rem_call(p, 'test_long_call', True, (p.LONG_CALL,))
        rem_call(p, 'test_long_call', True, (2*p.LONG_CALL,))
        rem_call(p, 'retry_set', True, (2,))
        rem_call(p, 'retry', True, args=(), repeat=repeatAlways)
    def stopper(delay=1):
        def cb(result):
            reactor.callLater(delay, reactor.stop)
        return cb
    p.when_idle().addCallback(run_again)
    def run_first():
        rem_call(p, 'test', True)
        rem_call(p, 'test', True)
        rem_call(p, 'test2', False)
        rem_call(p, 'test_exc', False)
        rem_call(p, 'test_exc2', False)
        rem_call(p, 'test_long_call', True, (p.LONG_CALL,))
        rem_call(p, 'test_long_call', True, (p.LONG_CALL,))
        rem_call(p, 'test_long_call', True, (2*p.LONG_CALL,))
        rem_call(p, 'retry_set', True, (2,))
        rem_call(p, 'retry', True, args=(), repeat=repeatAlways)
        rem_call(p, 'retry_set', True, (3,))
        rem_call(p, 'retry', False, args=(), repeat=repeatTimes(2))
    reactor.callWhenRunning(run_first)
    #reactor.callWhenRunning(rem_call, p, 'test', True)
    #reactor.callWhenRunning(rem_call, p, 'test2', False)
    #reactor.callWhenRunning(rem_call, p, 'test_exc', False)
    #reactor.callWhenRunning(rem_call, p, 'test_exc2', False)
    #reactor.callWhenRunning(rem_call, p, 'test_long_call', True, (p.LONG_CALL,))
    #reactor.callWhenRunning(rem_call, p, 'test_long_call', True, (p.LONG_CALL,))
    #reactor.callWhenRunning(rem_call, p, 'test_long_call', True, (2*p.LONG_CALL,))
    reactor.callLater(5, reactor.listenTCP, 54123, server.Site(TestHandler(), timeout=30), interface='127.0.0.1')
    reactor.run()
    print 80*"="
    print "Results:"
    print 80*"="
    print results

