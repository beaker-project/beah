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
Events are used to communicate events from Task to Controller and finally back
to Backend.

Classes:
    Event(list[, ...]) - class used for all events.

Function:
    event(list) - make Event from list if necessary.

Module contains many helper functions (e.g. idle, pong, start, end, etc.) to
instantiate Event of particular type.

Event is basically a list ['Event', evt, origin, timestamp, args] where:
    isinstance(evt, string)
    isinstance(origin, dict)
    isinstance(timestamp, float) or timestamp is None
    isinstance(args, dict)
"""


import exceptions
import base64
import zlib
import bz2
import sys
from beah.core.constants import RC, LOG_LEVEL
from beah.core import new_id, check_type
from beah.misc import setfname


################################################################################
# PUBLIC INTERFACE:
################################################################################
def idle():
    """Event sent to newly registerred backend when Controller is idle"""
    return Event('idle')

def pong(origin={}, timestamp=None, message=None):
    """Event generated as a reposne to ping command"""
    if message:
        return Event('pong', origin={}, timestamp=None, message=message)
    return Event('pong', origin, timestamp)

def start(task_id, origin={}, timestamp=None):
    """Event generated when task is started"""
    return Event('start', origin, timestamp, task_id=task_id)

def end(task_id, rc, origin={}, timestamp=None):
    """Event generated when task finished"""
    return Event('end', origin, timestamp, task_id=task_id, rc=rc)

def completed(task_id, success, origin={}, timestamp=None):
    """
    Task was fully handled by the originating backend.
    
    """
    return Event('completed', origin, timestamp, task_id=task_id, success=success)

def flush(origin={}, timestamp=None):
    """Event to request a memory-flush."""
    return Event('flush', origin, timestamp)

def introduce(task_id, origin={}, timestamp=None):
    return Event('introduce', origin=origin, timestamp=timestamp,
            task_id=task_id)

def query_watchdog(origin={}, timestamp=None):
    return Event('query_watchdog', origin, timestamp)

def extend_watchdog(timeout, origin={}, timestamp=None):
    return Event('extend_watchdog', origin, timestamp, timeout=timeout)

def abort(type, target=None, message=None, origin={}, timestamp=None):
    """
    Abort given {recipe,recipeset,job}.

    Abort currently running recipe, recipeset or job, if no target is specified.
    """
    if type not in ('task', 'recipe', 'recipeset', 'job'):
        raise exceptions.NotImplementedError('type must be recipe, recipeset or job. %r given' % type)
    return Event('abort', origin, timestamp, type=type, target=target,
            message=message)

def echo(cmd, rc, message="", origin={}, timestamp=None, **kwargs):
    """
    Event generated as a response to a command.

    Parameters:
    - cmd - a command-tuple or command id
    - rc - response as defined by beah.core.constants.ECHO
    - message - explanatory message
    """
    if isinstance(cmd, Event.TESTTYPE):
        cmd_id = cmd
    else:
        cmd_id = cmd.id()
    return Event('echo', origin, timestamp, cmd_id=cmd_id, rc=rc, message=message, **kwargs)

def nop(origin={}, timestamp=None):
    """Null Event."""
    return Event('nop', origin, timestamp)

def lose_item(data, origin={}, timestamp=None):
    """Event generated when unformatted data are received."""
    return Event('lose_item', origin, timestamp, data=data)

def section(parent_id, handle, origin={}, timestamp=None, **kwargs):
    """Event which identifies new section, which can contain other events."""
    return Event('section', origin, timestamp, handle=handle, parent_id=parent_id, **kwargs)

def output(data, out_handle="", origin={}, timestamp=None):
    return Event('output', origin, timestamp, out_handle=out_handle, data=data)
def stdout(data, origin={}, timestamp=None):
    return output(data, "stdout", origin, timestamp)
def stderr(data, origin={}, timestamp=None):
    return output(data, "stderr", origin, timestamp)

def log(message="", log_level=LOG_LEVEL.INFO, log_handle="", origin={},
        timestamp=None, **kwargs):
    return Event('log', origin, timestamp, log_level=log_level,
            log_handle=log_handle, message=message, **kwargs)

def mk_log_level(log_level):
    def logf(message="", log_handle="", origin={}, timestamp=None, **kwargs):
        return Event('log', origin, timestamp, log_level=log_level,
                log_handle=log_handle, message=message, **kwargs)
    setfname(logf, "log_level_%s" % log_level)
    logf.__doc__ = "Create log event with log_level = %s" % log_level
    return logf

lfatal = mk_log_level(LOG_LEVEL.FATAL)
lcritical = mk_log_level(LOG_LEVEL.CRITICAL)
lerror = mk_log_level(LOG_LEVEL.ERROR)
lwarning = mk_log_level(LOG_LEVEL.WARNING)
linfo = mk_log_level(LOG_LEVEL.INFO)
ldebug1 = mk_log_level(LOG_LEVEL.DEBUG1)
ldebug2 = mk_log_level(LOG_LEVEL.DEBUG2)
ldebug3 = mk_log_level(LOG_LEVEL.DEBUG3)
ldebug = ldebug1

def result_ex(rc, handle='', message='', statistics={}, origin={},
        timestamp=None, **kwargs):
    """Create a result event.

    rc - a return code. See beah.core.constants.RC for definition.
    handle - a human readable id of the result. Not necessarily an unique
    identifier.
    message - description/explanation of result.
    statistics - a numerical metric used for statistics.
    """
    return Event('result', origin, timestamp, rc=rc, handle=handle,
            message=message, statistics=statistics, **kwargs)

def result(rc, message=None, origin={}, timestamp=None, **kwargs):
    return result_ex(rc, origin=origin, timestamp=timestamp, message=message,
            **kwargs)

def mk_result(rc, message):
    def resf(message=message, origin={}, timestamp=None, **kwargs):
        return result(rc, message=message, origin=origin, timestamp=timestamp,
                **kwargs)
    setfname(resf, "result_%s" % rc)
    resf.__doc__ = "Create result with rc = %s and default message = %s" % (rc, message)
    return resf

passed = mk_result(RC.PASS, 'PASS')
warning = mk_result(RC.WARNING, 'WARNING')
failed = mk_result(RC.FAIL, 'FAIL')
critical = mk_result(RC.CRITICAL, 'CRITICAL')
fatal = mk_result(RC.FATAL, 'FATAL')
aborted = mk_result(RC.FATAL, 'FATAL - ABORTED')

def result_stats(result_id, statistics, origin={}, timestamp=None,
        **kwargs):
    """
    Attach additional metrics to already submitted result.

    Parameters:
    - result_id - an identifier of result event this event is related to.
    - statistics - a dictionary containing metrics. These have individual
      meaning from test to test.
    """
    return Event('result_stats', origin=origin, timestamp=timestamp,
            result_id=result_id, statistics=statistics, **kwargs)

def file(name=None, digest=None, size=None, codec=None, content_handler=None,
        origin={}, timestamp=None, **kwargs):
    """
    Create a new file.

    This event will define header of a new file to be submitted. For any such a
    file only one file event is allowed.

    Parameters:
    - name - a human readable file name. Should be unique within a test.
    - digest - a pair of (method, checksum), where method is "md5", "sha1",
      "sha256" or "sha512", and checksum is a checksum of the whole decoded
      file created using given method. Checksum component can be None, and
      method is used to verify particular code chunks only.
    - size - the size of the file.
    - codec - transformations applied to single chunks of data. E.g. "base64", "gz",
      "bz2". These can be concatenated using "|". Example: "base64|gz".
      - if whole file is compressed, use content_handler please.
    - content_handler - class of file (like mime type, but allowing more levels).
      These are useful e.g. for filtering and displaying file. E.g. in some
      files we want to delete timestamps, before applying diff.
      Example: "T|ls -l", "B|gz|T|dmesg", "B|core" {'T':text, 'B':binary}
    """
    return Event('file', origin=origin, timestamp=timestamp,
            name=name, digest=digest, size=size, codec=codec,
            content_handler=content_handler,
            **kwargs)

def file_meta(file_id, name=None, digest=None, size=None, content_handler=None,
        codec=None, origin={}, timestamp=None, **kwargs):
    """
    Attach metadata to already created file.

    Parameters:
    - file_id - an id of file event used to create a file,
    - see file for the rest.
    """
    # FIXME? change to use metadata
    return Event('file_meta', origin=origin, timestamp=timestamp,
            file_id=file_id, name=name, digest=digest, size=size, codec=codec,
            content_handler=content_handler,
            **kwargs)

def metadata(obj_id, origin={}, timestamp=None, **kwargs):
    """
    Attach metadata to the object with given id.

    - kwargs - free form metadata.
    """
    # FIXME: add at least some specification
    return Event('metadata', origin=origin, timestamp=timestamp, **kwargs)

def file_write(file_id, data, digest=None, codec=None, offset=None, origin={},
        timestamp=None, **kwargs):
    """
    Write a chunk of data to already created file.

    Parameters:
    - file_id - an id of file event used to create a file,
    - data - chunk of data encoded by codec to be written to the file at
      offset,
    - size - size of decoded data,
    - digest - digest of decoded data,
    - offset - position of data in the file. If None, data are to be appended
      at the end of file. Messages are expected to arrive in correct order.
    - codec - codec(s) applied to the chunk of data before transfer. Examples:
      "", "base64", "gz", "bz2" or combinations "gz|base64", "bz2|base64".
    """
    return Event('file_write', origin=origin, timestamp=timestamp,
            file_id=file_id, data=data, offset=offset, digest=digest,
            codec=codec, **kwargs)

def file_close(file_id, origin={}, timestamp=None, **kwargs):
    """
    Marks the end of the file.

    This is for information only. No more chunks to be written to the file.
    Backend might use this to keep the file open for writing.
    """
    return Event('file_close', origin=origin, timestamp=timestamp,
            file_id=file_id, **kwargs)

class VARIABLE_SET_METHOD:
    SET=0 # set the value
    APPEND=1 # add value to a list
    ADD=2 # add value to a list if not present already
    DELETE=3 # delete value from a list

def variable_set(key, value, handle='', method=VARIABLE_SET_METHOD.SET,
        origin={}, timestamp=None, **kwargs):
    """
    Set a "variable's" value.

    Variable is identified by tuple (handle, key, REST), where REST is
    dependent on handle and kwargs. See e.g. dest.

    Parameters:
    - key - variable's name. A string.
    - value - a value to store in the variable. No type restrictions - anything
      allowed by JSON.
    - handle - "pool" to look for the variable. A string. The default ('')
      means to store in Controller's default pool.
      Other values are to be handled by backends.
    Other recognized parameters (as keyword arguments):
    - dest - used with handle == '': the FQDN of remote machine.
    """
    return Event('variable_set', origin=origin, timestamp=timestamp,
            key=key, value=value, handle=handle, method=method, **kwargs)

def variable_get(key, handle='', origin={}, timestamp=None, **kwargs):
    """
    Get a "variable's" value.

    Parameters: see variable_set for meaning of parameters.
    """
    return Event('variable_get', origin=origin, timestamp=timestamp,
            key=key, handle=handle, **kwargs)

class VARIABLE_METHOD:
    DEFINED=0
    COUNT=1
    LIST=2
    DICT=3

def variables(keys, handle='', method=VARIABLE_METHOD.DEFINED, origin={}, timestamp=None, **kwargs):
    """
    Check existence of variable(s).

    A command.answer is expected in answer.

    Parameters:
    - keys - variable names to look-up.
    - method - function used to produce result. Return value in answer
      depending on method will be:
      - VARIABLE_METHOD.DEFINED - True if any of variables exists
      - VARIABLE_METHOD.COUNT - count of defined variables
      - VARIABLE_METHOD.LIST - list of names
      - VARIABLE_METHOD.DICT - dictionary of (name, value) tuples
    See variable_set for meaning of handle and other parameters.
    """
    return Event('variables', origin=origin, timestamp=timestamp,
            keys=keys, handle=handle, method=method, **kwargs)

def forward_response(command, forward_id, origin={}, timestamp=None,
        **kwargs):
    """
    Used internally by Controller, in response to incomming command.forward.

    @command - command generated in response to forwarded event
    @forward_id - id of incomming command.forward

    There could be multiple responses.
    It is required all these response is sent before event.echo.
    """
    return Event('forward_response', origin=origin, timestamp=timestamp,
            command=command, forward_id=forward_id, **kwargs)

def relation(handle, id1, id2, title=None, n2m=False, title1=None, origin={},
        timestamp=None, **kwargs):
    """
    Define a relation between two objects .

    Parameters:
    - handle - a "table" name - identifier of type of relation.
    - id1, id2 - identifiers of the objects. UUID used by event defining the
      object (e.g. task, section, result, file, stream, ...)
    - title1, title - names of objects intended for human consumption.
      Generated from objects' metadata if None. title is name for id2. title1
      is name for id1, and used only by many-to-many relations.
    - n2m - if True the relation is defining many-to-many relation.
    """
    return Event('relation', origin=origin, timestamp=timestamp, handle=handle,
            id1=id1, id2=id2, title=title, n2m=n2m, title1=title1, **kwargs)

################################################################################
# AUXILIARY:
################################################################################
def encode(codec, data):
    """
    Function to code chunk of data.

    Data to be sent in event file_write, using codec defined in file, file_meta
    or file_write.
    """
    if codec is None:
        cs = [""]
    else:
        cs = codec.split("|")
    for c in cs:
        if c=="base64":
            data = base64.encodestring(data)
        elif c=="bz2":
            data = bz2.compress(data)
        elif c=="gz":
            data = zlib.compress(data)
        elif c=="":
            continue
        else:
            raise exceptions.NotImplementedError("unknow codec '%s'" % codec)
    return data

def decode(codec, data):
    """
    Function to decode chunk of data.

    Data received in event file_write, using codec defined in file, file_meta
    or file_write.
    """
    if codec is None:
        cs = [""]
    else:
        cs = codec.split("|")
        cs.reverse()
    for c in cs:
        if c=="base64":
            data = base64.decodestring(data)
        elif c=="bz2":
            data = bz2.decompress(data)
        elif c=="gz":
            data = zlib.decompress(data)
        elif c=="":
            continue
        else:
            raise exceptions.NotImplementedError("unknow codec '%s'" % codec)
    return data

################################################################################
# IMPLEMENTATION:
################################################################################
class EventFactory(object):

    event_classes = {}

    def __init__(self):
        """
        This is a zero-ton class.
        """
        raise exceptions.NotImplementedError("This class is not to be instantiated")

    def register_class(cls, class_):
        """
        aaa

        This method can be used as decorator.
        """
        cls.event_classes[getattr(class_, "_", class_.__name__)] = class_
        return class_
    register_class = classmethod(register_class)

    def get_constructor(cls, event):
        return cls.event_classes.get(event, Event)
    get_constructor = classmethod(get_constructor)

    def make(cls, evt):
        return cls.get_constructor(evt[Event.EVENT])(evt)
    make = classmethod(make)


def event(evt):
    if isinstance(evt, Event):
        return evt
    return EventFactory.make(evt)


import time
class Event(list):

    """
    Events are used to communicate events from Task to Controller and finally back
    to Backend.

    Event is basically a list ['Event', evt, origin, timestamp, args] where:
        isinstance(evt, string)
        isinstance(origin, dict)
        isinstance(timestamp, float) or timestamp is None
        isinstance(args, dict)

    The list inheritance is important to be able to serialize to JSON object.
    """

    EVENT = 1
    ID = 2
    ORIGIN = 3
    TIMESTAMP = 4
    ARGS = 5

    if sys.version_info[1] < 4:
        # FIXME: Tweak to make it Python 2.3 compatible
        TESTTYPE = (str, unicode)
    else:
        TESTTYPE = str

    def __new__(cls, evt, origin={}, timestamp=None, id=None, **kwargs):
        if not isinstance(evt, Event):
            if isinstance(evt, list):
                event = evt[Event.EVENT]
            else:
                event = evt
            class_ = EventFactory.get_constructor(event)
        else:
            class_ = cls
        return super(Event, cls).__new__(class_, evt, origin, timestamp, id, **kwargs)

    def __init__(self, evt, origin={}, timestamp=None, id=None, **kwargs):
        if isinstance(evt, list):
            list.__init__(self, evt)
            self[self.ORIGIN] = dict(evt[self.ORIGIN]) # make a copy
            self[self.ARGS] = dict(evt[self.ARGS]) # make a copy
            if isinstance(evt, Event):
                return
        else:
            list.__init__(self, ['Event', None, None, None, None, None])
            self[self.EVENT] = evt
            self[self.ID] = id
            self[self.ORIGIN] = dict(origin)
            self[self.TIMESTAMP] = timestamp
            self[self.ARGS] = dict(kwargs)

        if self[self.TIMESTAMP] == True:
            self[self.TIMESTAMP] = time.time()

        if self[self.ID] is None:
            self[self.ID] = new_id()

        self.check()

    def check(self):
        if self[0] != 'Event':
            raise exceptions.TypeError('%r not permitted as %r[0]. Has to be \'Event\'' % (self[0]))
        check_type("event", self.event(), self.TESTTYPE)
        check_type("id", self.id(), self.TESTTYPE)
        check_type("origin", self.origin(), dict)
        check_type("args", self.args(), dict)
        check_type("timestamp", self.timestamp(), float, True)

    def event(self): return self[self.EVENT]
    def id(self): return self[self.ID]
    def origin(self): return self[self.ORIGIN]
    def timestamp(self): return self[self.TIMESTAMP]
    def args(self): return self[self.ARGS]
    def arg(self, name, val=None):
        return self.args().get(name, val)
    def same_as(self, evt):
        if not isinstance(evt, Event):
            evt = Event(evt)
        if self.event() != evt.event():
            return False
        if self.origin() != evt.origin():
            return False
        if self.args() == evt.args():
            return True
        # FIXME: are there any other exceptions?
        return False
    def register_class(cls):
        return EventFactory.register_class(cls)
    register_class = classmethod(register_class)

    def printable(self):
        return self

    def __repr__(self):
        return list.__repr__(self.printable())

    def task_id(self):
        evev = self.event()
        if evev in ('start', 'end', 'completed', 'introduce'):
            tid = self.arg('task_id')
        elif evev == 'echo':
            tid = self.arg('cmd_id')
        else:
            tid = self.origin().get('id', None)
        return tid



################################################################################
# SUBCLASSES:
################################################################################
class file_write_(Event):
    _ = 'file_write'
    _f = file_write
    def printable(self):
        e = Event(self)
        e.args()['data'] = '...%sB hidden...' % len(self.arg('data'))
        return e
file_write_.register_class()


################################################################################
# TESTING:
################################################################################
if __name__=='__main__':
    import traceback, sys

    # test constructor:
    def test(expected, evt, origin={}, timestamp=None, cls=Event, **kwargs):
        try:
            answ = Event(evt, origin=origin, timestamp=timestamp, **kwargs)
            if not isinstance(answ, cls):
                print >> sys.stderr, \
                    "--- ERROR: Event(%r, %r) is a %s != %s" % (evt,
                            kwargs, answ.__class__.__name__, cls.__name__)
            answ = list(answ)
            if answ != expected:
                print >> sys.stderr, "--- ERROR: Event(%r, %r) == %r != %r" % (evt,
                        kwargs, answ, expected)
        except:
            answ = sys.exc_type.__name__
            if answ != expected:
                print >> sys.stderr, "--- ERROR: Event(%r, %r) raised %r != %r" % (evt,
                        kwargs, answ, expected)
                traceback.print_exc()

    test(['Event', 'ping', '99', {}, None, {}], 'ping', id='99')
    test('TypeError', 1)
    test(['Event', 'ping', '99', {}, None, {}], evt='ping', id='99')
    test('TypeError', evt=1)
    #test('TypeError', evt='ping', origin='') # dict('') is all right!
    test('TypeError', evt='ping', origin={}, timestamp='')
    test(['Event', 'ping', '99', {}, None, {'value':1}], evt='ping', value=1, id='99')
    test(['Event', 'ping', '99', {}, None, {'value':1}], **{'evt':'ping', 'value':1, 'id':'99'})
    test(['Event', 'ping', '99', {}, None, {'value':1}], value=1, evt='ping', id='99')
    test(['Event', 'ping', '99', {}, None, {'value':1}], **{'value':1, 'evt':'ping', 'id':'99'})
    test(['Event', 'file_write', '99', {}, None, {'file_id':'FID', 'data':'DATA'}], evt='file_write', id='99', data='DATA', file_id='FID', cls=file_write_)

    # test overridden methods:
    s = "Data to be written but not displayed"
    fw = file_write('FID', s)
    assert fw.__str__().find(s) == -1
    assert fw.__repr__().find(s) == -1

    # test copy constructors:
    def test_copy(e, copy):
        assert copy.same_as(e)
        assert copy.id() == e.id()

    def test_constructors(e):
        test_copy(e, Event(e))
        test_copy(e, Event(list(e)))
        test_copy(e, event(list(e)))
        if isinstance(e, Event):
            assert e is event(e)

    test_constructors(pong(message='Hello World!'))
    test_constructors(file_write('FID', 'DATA'))

    # test encoder/decoder:
    def test(codec, f):
        for s in ["Hello World!"]:
            assert decode(codec, f(s)) == s
            assert decode(codec, encode(codec, s)) == s
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

