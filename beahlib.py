"""
Python API for Beah harness.

Usage:
    t = get_task()
    t.upload("path/name", "/the/real/file/name")
    r = t.passed("sub/test/result", "Additional text")
    r.upload("result/log", "/the/real/file/name")
"""

import sys
import os
import socket
from beah.core import event, new_id, command
from beah.core.constants import RC, LOG_LEVEL
import simplejson as json


"""
TODO:

we need to keep id's somewhere:
- if file with same handle is queried for task/result we should get the same
  object!
- file offsets need to be cached too
- what about results?

think about this:
- file content: do not send (unless explicitly asked to) just copy and send a
  link
"""


def a_command(str):
    return command.command(json.loads(str))


class BeahError(Exception):
    """Generic beah error."""
    pass


def check_answ(evt, cmd):
    if cmd.command() != "answer":
        raise BeahError("Unexpected event %s" % cmd)
    id = cmd.arg("request")
    if id != evt.id():
        raise BeahError("Unexpected answer %s" % id)
    error = evt.arg("error")
    if error:
        raise BeahError("%s" % error)
    return evt.arg("value")


def an_answer(evt, str):
    return check_answ(evt, a_command(str))


def stdout_send(evt):
    print json.dumps(evt)
    answ = sys.stdin.readline()
    return an_answer(evt, answ)


def stdout_send_noanswer(evt):
    print json.dumps(evt)
    return 0


def StdoutSender(nowait=True):
    if nowait:
        return stdout_send_noanswer
    else:
        return stdout_send


class SocketSender(object):

    def __init__(self, nowait=True):
        self.buffer = ""
        self.nowait = nowait
        # if available: use Unix socket:
        tsocket = os.getenv('BEAH_TSOCKET')
        if tsocket:
            self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.s.connect(tsocket)
            return
        # otherwise: TCP/IP socket:
        thost = os.getenv('BEAH_THOST')
        tport = os.getenv('BEAH_TPORT')
        if thost and tport:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((thost, tport))
            return
        # unavailable:
        self.s = None
        raise Exception('None of BEAH_TSOCKET or (BEAH_THOST, BEAH_TPORT) are defined!')

    def __del__(self):
        self.close()

    def close(self):
        if self.s is not None:
            self.s.close()
            self.s = None

    def __call__(self, evt):
        self.s.send(json.dumps(evt)+"\n")
        if self.nowait:
            return
        while True:
            answ = self.s.recv(4096)
            self.buffer += answ
            ht = self.buffer.split("\n", 1)
            if len(ht) > 1:
                (head, self.buffer) = ht
                return an_answer(evt, head)


def DefaultSender():
    return SocketSender()


# FIXME: Add fallback wrapper for SocketSender - if BEAH_TSOCKET is not defined: write
# to a file (what file?) or use stdout.

def get_task(sender=None):
    if sender is None:
        sender = DefaultSender()
    return BeahTask.the_task(sender=sender)


class BeahObject(object):

    def __init__(self, parent):
        self._parent = parent
        self._task = parent.task()

    def task(self):
        return self._task

    def send(self, evt):
        return self._parent.send(evt)


class BeahEventObject(BeahObject):

    def __init__(self, parent):
        BeahObject.__init__(self, parent)

    def the_event(self, evt):
        self.set_id(evt.id())
        self.send(evt)

    def set_id(self, id):
        self._id = id

    def id(self):
        return self._id


def _mk_log(log_level):
    def logf(self, message=None):
        return self.log(log_level, message)
    return logf


def _mk_result(rc):
    def resultf(self, handle=None, message=None, statistics=None):
        return self.result(RC.PASS, handle=handle, message=message,
                statistics=statistics)
    return resultf


class IBeahLog(object):

    """
    Interface for objects which accept log events.

    Implementation of this interface must provide send method.

    """

    def log(self, log_level, message):
        return self.send(event.log(message=message, log_level=log_level)) # pylint: disable=E1101

    lfatal = _mk_log(LOG_LEVEL.FATAL)
    lcritical = _mk_log(LOG_LEVEL.CRITICAL)
    lerror = _mk_log(LOG_LEVEL.ERROR)
    lwarning = _mk_log(LOG_LEVEL.WARNING)
    linfo = _mk_log(LOG_LEVEL.INFO)
    ldebug1 = _mk_log(LOG_LEVEL.DEBUG1)
    ldebug2 = _mk_log(LOG_LEVEL.DEBUG2)
    ldebug3 = _mk_log(LOG_LEVEL.DEBUG3)
    ldebug = ldebug1


class IBeahResult(object):

    def result(self, rc, handle=None, message=None, statistics=None):
        return BeahResult(self, rc, handle=handle, message=message, statistics=statistics)

    passed = _mk_result(RC.PASS)
    warning = _mk_result(RC.WARNING)
    failed = _mk_result(RC.FAIL)
    critical = _mk_result(RC.CRITICAL)
    fatal = _mk_result(RC.FATAL)
    aborted = fatal


class IBeahUpload(object):

    def _attach(self, file):
        raise NotImplementedError

    def upload(self, handle, filename):
        file = BeahFile(self, handle)
        self._attach(file)
        file.upload(filename)
        file.close()
        return None

    def file(self, handle):
        file = BeahFile(self, handle)
        self._attach(file)
        return file


class IBeahOutput(object):

    def output(self, handle):
        return BeahStream(self, handle)


class IBeahOrigin(object):

    """
    Interface for objects which may want to update origin of the event.

    Implementation of this interface must either provide _origin instance
    variable or override origin method.

    """


    def origin(self):
        return self._origin # pylint: disable=E1101

    def update_event(self, evt):
        origin = self.origin()
        if origin:
            origin = dict(origin)
            origin.update(evt.origin())
            evt[event.Event.ORIGIN] = origin
        return evt


class IBeahSection(IBeahResult, IBeahLog, IBeahUpload, IBeahOutput, IBeahOrigin):

    def section(self, handle, origin=None):
        return BeahSection(self, handle, origin=origin)


class BeahSection(BeahEventObject, IBeahSection):

    def __init__(self, parent, handle, origin=None):
        BeahEventObject.__init__(self, parent)
        self._handle = handle
        self._origin = dict(origin or {})
        #self._origin.setdefault('id', parent.origin().get('id'))
        self.the_event(event.section(parent.id(), self._handle))
        self._origin['parent_id'] = self.id()

    def _attach(self, file):
        self.send(event.relation('section_file', self.id(), file.id()))

    def send(self, evt):
        return BeahEventObject.send(self, self.update_event(evt))


class BeahTask(IBeahSection):

    _the_task = None

    def the_task(cls, sender=None, **kwargs):
        if cls._the_task is None:
            cls._the_task = cls(sender=sender, **kwargs)
        return cls._the_task
    the_task = classmethod(the_task)

    def __init__(self, sender=None, origin=None):
        #assert sender, "Seneder must be defined."
        self._sender = sender or DefaultSender()
        self._id = os.getenv('BEAH_TID')
        self._origin = origin or {}
        if not self._id:
            self._id = new_id()
            self._origin.setdefault('id', self._id)
            os.environ['BEAH_TID'] = self._id
            self.log(LOG_LEVEL.WARNING, "Task ID (BEAH_TID) is not defined. Making new one.")
        else:
            self._origin.setdefault('id', self._id)
        self.introduce()

    def clone(self, origin=None, sender=None):
        if origin is None:
            origin = self._origin
        if sender is None:
            sender = self._sender
        return BeahTask(sender=sender, origin=origin)

    def send(self, evt):
        return self._sender(self.update_event(evt))

    def id(self):
        return self._id

    def task(self):
        return self

    def introduce(self):
        return self.send(event.introduce(self.id()))

    def lose_item(self, o):
        return self.send(event.lose_item(o))

    def flush(self):
        return self.send(event.flush())

    def set_timeout(self, timeout):
        return self.send(event.set_timeout(timeout))

    def suicide(self, message):
        return self.send(event.kill(message))

    kill = suicide

    def end(self, exit_code=0):
        return self.send(event.end(self.id(), exit_code))

    def _attach(self, file):
        pass


class BeahStream(BeahObject):

    def __init__(self, parent, handle):
        BeahObject.__init__(self, parent)
        self._handle = handle

    def write(self, data):
        self.send(event.output(data, out_handle=self._handle))
        return None


class BeahResult(BeahEventObject, IBeahUpload):

    def __init__(self, parent, rc, handle=None, message=None, statistics=None):
        BeahEventObject.__init__(self, parent)
        self.the_event(event.result_ex(rc, handle=handle, message=message, statistics=statistics))

    def _attach(self, file):
        self.send(event.relation('result_file', self.id(), file.id()))


class BeahFile(BeahEventObject):

    MAX_CHUNK_SIZE = 128*1024
    CODEC = 'base64'

    def __init__(self, parent, handle):
        BeahEventObject.__init__(self, parent)
        self.offset = 0
        self.handle = handle
        self.the_event(event.file(name=handle))

    def upload(self, filename):
        # FIXME: this will need an extra event, so it does not require reading
        # and sending whole file. Just copy it to known location. Event that
        # could be avoided
        f = open(filename, 'r')
        try:
            offset = 0
            while True:
                data = f.read(self.MAX_CHUNK_SIZE)
                if not data:
                    break
                self.upload_chunk(offset, data)
                offset += len(data)
        finally:
            f.close()
        return None

    def upload_chunk(self, offset, data):
        if offset is None:
            new_offset = self.tell() + len(data)
        else:
            new_offset = offset + len(data)
        self.send(event.file_write(self.id(), event.encode(self.CODEC, data),
            offset=offset, codec=self.CODEC))
        self.seek(new_offset)
        return None

    def write(self, data):
        self.upload_chunk(None, data)
        return len(data)

    def seek(self, offset):
        self.offset = offset

    def tell(self):
        return self.offset

    def close(self):
        self.send(event.file_close(self.id()))
        return None


if __name__ == "__main__":

    class MySender(object):

        def __init__(self):
            self.events = []

        def print_(self, evt):
            #print "got '%s' event" % evt.event()
            print evt

        def check(self, evt):
            #self.print_(evt)
            pass

        def __call__(self, evt):
            self.events.append(evt)
            self.check(evt)
            return 0

        def flush(self):
            self.events = []

        def all(self, predicate):
            for evt2 in self.events:
                assert predicate(evt2)
            return evt2

        def any(self, predicate):
            for evt2 in self.events:
                if predicate(evt2):
                    return evt2
            assert False,  "No matching event."

        def has(self, evt):
            return self.any(lambda evt2: evt2.same_as(evt))

    sender = MySender()
    t = get_task(sender)

    def check_task(id):
        sender.all(lambda evt: evt.origin()['id'] == id)

    def check_parent(parent_id):
        sender.all(lambda evt: evt.origin()['parent_id'] == parent_id)

    #print "\n== USING THE TASK =="
    t.passed("result/passed", "Hooray!")
    r = t.failed("result/...happens", "...!")
    the_file = os.path.expanduser("~/.vimrc")
    #print the_file
    t.upload("TASK.log", the_file)
    r.upload("RESULT.log", the_file)
    o = t.output("stream")
    o.write("line1\n")
    o.write("line2\n")
    tf = t.file('task_file')
    tf.upload_chunk(None, 'chunk1\n')
    tf.upload_chunk(None, 'chunk2\n')
    tf.close()
    rf = r.file('result_file')
    rf.upload_chunk(0, 'chunk1\n')
    rf.upload_chunk(0, 'chunk2\n')
    rf.close()
    #print "\n== USING CLONED TASK =="
    tc = t.clone(origin=dict(file=__file__, module=__name__))
    tc.linfo("cloned")
    tc.passed("cloned", "Pass!")
    #print "\n== USING SECTION =="
    s = t.section("new section")
    check_task(t.id())
    sender.flush()
    s.linfo("section")
    s.upload("SECTION.log", the_file)
    so = s.output("stream")
    so.write("hello")
    sr = s.passed("section/pass", "Passed!")
    sr.upload("SECTION_RESULT.log", the_file)
    #print "\n== USING SUB-SECTION =="
    ss = s.section("subsection")
    check_task(t.id())
    check_parent(s.id())
    sender.flush()
    ss.lwarning("Have a look at this!")
    ss.ldebug("Have a look at this!")
    ssr = ss.passed("subsection/pass", "Passed")
    ssrf = ssr.file("subsection_result.log")
    ssrf.write("Hello ")
    ssrf.write("World!")
    ssrf.write("\n")
    ssrf.close()
    check_task(t.id())
    check_parent(ss.id())
    sender.flush()

