# -*- test-case-name: beah.core.test.test_event -*-

import traceback, sys
import base64
import zlib
import bz2

from twisted.trial import unittest

from beah.core import event

class TestCommand(unittest.TestCase):

    def testEvent(self):

        def make_evt(*args, **kwargs):
            return list(event.Event(*args, **kwargs))

        self.failUnlessEqual(['Event', 'ping', '99', {}, None, {}], make_evt('ping', id='99'))
        self.failUnlessRaises(TypeError, make_evt, 1)
        self.failUnlessEqual(['Event', 'ping', '99', {}, None, {}], make_evt(evt='ping', id='99'))
        self.failUnlessRaises(TypeError, make_evt, evt=1)
        self.failUnlessRaises(TypeError, make_evt, evt='ping', origin={}, timestamp='')
        self.failUnlessEqual(['Event', 'ping', '99', {}, None, {'value':1}], make_evt(evt='ping', value=1, id='99'))
        self.failUnlessEqual(['Event', 'ping', '99', {}, None, {'value':1}], make_evt(**{'evt':'ping', 'value':1, 'id':'99'}))
        self.failUnlessEqual(['Event', 'ping', '99', {}, None, {'value':1}], make_evt(value=1, evt='ping', id='99'))
        self.failUnlessEqual(['Event', 'ping', '99', {}, None, {'value':1}], make_evt(**{'value':1, 'evt':'ping', 'id':'99'}))
        evt = event.Event(evt='file_write', id='99', data='DATA', file_id='FID')
        self.failUnlessIsInstance(evt, event.file_write_)
        self.failUnlessEqual(['Event', 'file_write', '99', {}, None, {'file_id':'FID', 'data':'DATA'}], evt)

        # self.failUnlessRaises(TypeError, make_evt, evt='ping', origin='') # dict('') is all right!

    def testOverridenMethods(self):
        s = "Data to be written but not displayed"
        fw = event.file_write('FID', s)
        self.failUnlessEqual(fw.__str__().find(s), -1)
        self.failUnlessEqual(fw.__repr__().find(s), -1)

    def testContructors(self):
        """test copy constructors"""
        def test_copy(e, copy):
            self.failUnless(copy.same_as(e))
            self.failUnlessEqual(copy.id(), e.id())
        def test_constructors(e):
            test_copy(e, event.Event(e))
            test_copy(e, event.Event(list(e)))
            test_copy(e, event.event(list(e)))
            if isinstance(e, event.Event):
                self.failUnless(e is event.event(e))
        test_constructors(event.pong(message='Hello World!'))
        test_constructors(event.file_write('FID', 'DATA'))


class TestEncoderDecoder(unittest.TestCase):

    def testMain(self):
        # test encoder/decoder:
        def test(codec, f):
            for s in ["Hello World!"]:
                assert event.decode(codec, f(s)) == s
                assert event.decode(codec, event.encode(codec, s)) == s
        test('', lambda x: x)
        test(None, lambda x: x)
        test('|||', lambda x: x)
        test('base64', lambda x: base64.encodestring(x))
        #test('base64', lambda x: base64.b64encode(x))
        test('gz', lambda x: zlib.compress(x))
        test('bz2', lambda x: bz2.compress(x))
        test('bz2|base64', lambda x: base64.encodestring(bz2.compress(x)))
        test('|bz2||base64|', lambda x: base64.encodestring(bz2.compress(x)))
        #test('bz2|base64', lambda x: base64.b64encode(bz2.compress(x)))
        #test('|bz2||base64|', lambda x: base64.b64encode(bz2.compress(x)))
        #test('utf8', lambda x: x) # THIS WILL FAIL!

