# -*- test-case-name: beah.wires.internals.test.test_repeatingproxy -*-

import exceptions
import xmlrpclib
import time
import sys

from twisted.web import server, xmlrpc
from twisted.internet import reactor, defer
from twisted.trial import unittest
from twisted.python import failure
from twisted.internet.base import DelayedCall

from beah.wires.internals import repeatingproxy
from beah.misc.log_this import log_this
from beah.misc import make_class_verbose


VERBOSE = False


if VERBOSE:
    DelayedCall.debug = True


    def printf_w_timestamp(s):
        #ts = time.strftime("%Y%m%d-%H%M%S")
        ts = time.time()
        print("%.2f: %s" % (ts, s))
        sys.stdout.flush()
    printf = printf_w_timestamp
    print_this = log_this(printf)


class TestRepeaters(unittest.TestCase):

    def testRepeatAlways(self):
        for i in range(7):
            assert repeatingproxy.repeatAlways(i)

    def testRepeatTimes(self):
        repeat6Times = repeatingproxy.repeatTimes(6)
        try:
            for i in range(6):
                assert repeat6Times(i)
            assert not repeat6Times(7)
        finally:
            del repeat6Times

    def testRepeatWithHandle(self):

        class repeatWithMemory(repeatingproxy.repeatWithHandle):
            def __init__(self, repeat):
                self.x = None
                repeatingproxy.repeatWithHandle.__init__(self, repeat)
            def first_time(self, fail):
                self.x = fail

        def check(repeater, i, expected_return, expected_x):
            ret = repeater(i)
            if ret != expected_return:
                assert False, "repeater(i) is %s and not %s as expected." % (ret, expected_return)
            if repeater.x != expected_x:
                assert False, "repeater.x is %s and not %s as expected." % (repeater.x, expected_x)

        repeater = repeatWithMemory(repeatingproxy.repeatTimes(6))
        assert repeater.x is None
        check(repeater, 0, True, 0)
        check(repeater, 1, True, 0)
        repeater.x = None
        for i in range(4):
            check(repeater, 2+i, True, None)
        check(repeater, 7, False, None)
        try:
            check(repeater, 8, False, 0)
            raise Exception("Failure was expected.")
        except AssertionError:
            pass
        try:
            check(repeater, 8, True, None)
            raise Exception("Failure was expected.")
        except AssertionError:
            pass


class TestConstTimeout(unittest.TestCase):

    def test(self):
        ct = repeatingproxy.ConstTimeout(10)
        assert ct.get() == 10
        assert ct.incr() == 10
        assert ct.incr() == 10
        assert ct.incr() == 10
        assert ct.decr() == 10
        assert ct.decr() == 10
        assert ct.decr() == 10
        assert ct.get() == 10


class TestIncreasingTimeout(unittest.TestCase):

    def test(self):
        def check(it, itn):
            assert itn == it.get()
            assert itn == it.decr()
            assert itn <= it.max
            assert itn >= it.timeout
        it = repeatingproxy.IncreasingTimeout(10)
        itn = itp = it.get()
        assert itp == 10
        while itn < it.max:
            itn = it.incr()
            #printf(itn)
            check(it, itn)
            assert itn > itp
            itp = itn
        assert itn == it.max
        itn = it.incr()
        check(it, itn)
        assert itn == it.max


class TestAddaptiveTimeout(unittest.TestCase):

    def test(self):
        def check(it, itn):
            assert itn == it.get()
            assert itn <= it.max
            assert itn >= it.timeout
        it = repeatingproxy.AdaptiveTimeout(10)
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


class TestHandler(xmlrpc.XMLRPC):
    _VERBOSE = ('xmlrpc_test', 'xmlrpc_test_exc', 'xmlrpc_test_exc2',
            'xmlrpc_test_long_call')
    def raise_(self, exc):
        #try:
        #    raise exc
        #except:
        #    return failure.Failure()
        return xmlrpc.Fault(xmlrpc.FAILURE, failure.Failure(exc))
    def xmlrpc_retry_set(self, n):
        self.retries = n
        return n
    def xmlrpc_retry(self):
        self.retries -= 1
        if self.retries >= 0:
            return self.raise_(exceptions.RuntimeError("Sorry. Try again..."))
        return "Finally OK"
    def xmlrpc_test(self): return "OK"
    def xmlrpc_test_exc(self):
        return self.raise_(exceptions.RuntimeError())
    def xmlrpc_test_exc2(self):
        return self.raise_(exceptions.NotImplementedError())
    def xmlrpc_test_long_call(self, delay=12):
        d = defer.Deferred()
        reactor.callLater(delay, d.callback, True)
        return d


class TestRepeatingProxy(unittest.TestCase):

    _VERBOSE = ('chk', 'rem_call', 'accepted_failure')

    def chk(self, result, method, result_ok, expected_ok):
        pass_ = result_ok == expected_ok
        message = ("%s: method %s resulted in %s %s%s" % (
                pass_ and "OK" or "ERROR",
                method,
                pass_ and "expected" or "unexpected",
                result_ok and "pass" or "failure",
                '', #":\n%s" % result,
                ))
        self.failUnlessEqual(result_ok, expected_ok, message)
        return True

    def rem_call(self, proxy, method, exp_, args=(), repeat=None):
        if repeat is None:
            return proxy.callRemote(method, *args) \
                    .addCallbacks(self.chk, self.chk,
                            callbackArgs=[method, True, exp_],
                            errbackArgs=[method, False, exp_])
        else:
            return proxy.repeatedRemote(repeat, method, *args) \
                    .addCallbacks(self.chk, self.chk,
                            callbackArgs=[method, True, exp_],
                            errbackArgs=[method, False, exp_])

    def accepted_failure(self, fail):
        if fail.check(exceptions.NotImplementedError):
            # This does not work :-(
            return True
        if fail.check(xmlrpclib.Fault):
            # This would work:
            return True
        return False

    def setUp(self):
        p = self.proxy = repeatingproxy.RepeatingProxy(xmlrpc.Proxy(url='http://127.0.0.1:54123/'))
        #p.is_accepted_failure = self.accepted_failure
        p.RPC_TIMEOUT = 0.75
        p.TIMEOUT_FACTOR = 1.5
        p.DELAY_TIMEOUT = 0.5
        p.LONG_CALL = 3.0
        p.delay = repeatingproxy.AdaptiveTimeout(p.DELAY_TIMEOUT, factor=p.TIMEOUT_FACTOR)
        p.set_timeout(repeatingproxy.IncreasingTimeout(p.RPC_TIMEOUT, factor=p.TIMEOUT_FACTOR))
        p.max_retries = 6
        p.serializing = True
        self.handler = TestHandler()
        self.site = server.Site(self.handler, timeout=30)
        self.tcp_port = None

    def tearDown(self):
        #self.site.doStop()
        if self.tcp_port:
            self.tcp_port.stopListening()
            self.tcp_port = None

    def startServer(self):
        self.tcp_port = reactor.listenTCP(54123, self.site, interface='127.0.0.1')

    def test01Serializing(self):
        reactor.callLater(5, self.startServer)
        p = self.proxy
        self.rem_call(p, 'test', True)
        self.rem_call(p, 'test', True)
        self.rem_call(p, 'test2', False)
        self.rem_call(p, 'test_exc', False)
        self.rem_call(p, 'test_exc2', False)
        self.rem_call(p, 'test_long_call', True, (p.LONG_CALL,))
        self.rem_call(p, 'test_long_call', True, (p.LONG_CALL,))
        self.rem_call(p, 'test_long_call', True, (2*p.LONG_CALL,))
        self.rem_call(p, 'retry_set', True, (2,))
        self.rem_call(p, 'retry', True, args=(), repeat=repeatingproxy.repeatAlways)
        self.rem_call(p, 'retry_set', True, (3,))
        self.rem_call(p, 'retry', False, args=(), repeat=repeatingproxy.repeatTimes(2))
        return p.when_idle()

    def test02NotSerializing(self):
        reactor.callLater(0, self.startServer)
        p = self.proxy
        p.serializing = False
        p.set_timeout(repeatingproxy.IncreasingTimeout(p.DELAY_TIMEOUT, factor=p.TIMEOUT_FACTOR))
        self.handler.retries = 2
        self.rem_call(p, 'test', True)
        self.rem_call(p, 'test', True)
        self.rem_call(p, 'test2', False)
        self.rem_call(p, 'test_exc', False)
        self.rem_call(p, 'test_exc2', False)
        self.rem_call(p, 'test_long_call', True, (p.LONG_CALL,))
        self.rem_call(p, 'test_long_call', True, (2*p.LONG_CALL,))
        self.rem_call(p, 'retry', True, args=(), repeat=repeatingproxy.repeatAlways)
        return p.when_idle()


if VERBOSE:
    repeatingproxy.RepeatingProxy._VERBOSE = repeatingproxy.RepeatingProxy._VERBOSE + repeatingproxy.RepeatingProxy._MORE_VERBOSE
    make_class_verbose(repeatingproxy.RepeatingProxy, print_this)
    make_class_verbose(TestHandler, print_this)
    make_class_verbose(TestRepeatingProxy, print_this)


