# -*- test-case-name: beah.misc.test.test_runtimes -*-

import pprint

from twisted.trial import unittest

from beah.misc import runtimes


class TestingRuntime(runtimes.ShelveRuntime):
    def __init__(self, fname):
        runtimes.ShelveRuntime.__init__(self, fname)
        self.vars = runtimes.TypeDict(self, 'var')
        self.files = runtimes.TypeDict(self, 'file')
        self.queue = runtimes.TypeList(self, 'queue')


def print_(runtime):
    for attr in ["vars", "files", "tasks"]:
        obj = getattr(runtime, attr, None)
        if obj:
            print "\n== %s ==" % attr
            for k in obj.keys():
                print "%r: %r" % (k, obj[k])
    print "\n== queue =="
    for ix, v in enumerate(runtime.queue):
        print "[%r]: %r" % (ix, v)


def pprint_(runtime):
    pprint.pprint(runtime.dump(sorted=True))


def print_runtime(runtime):
    print ""
    print_(runtime)
    pprint_(runtime)


class TestShelveRuntime(unittest.TestCase):

    def testAll(self):

        TESTDB='.test-runtime.db.tmp'
        tr = TestingRuntime(TESTDB)
        tr.tasks = runtimes.TypeDict(tr, 'tasks')
        tr.tqueue = runtimes.TypeList(tr, 'testqueue')
        tr.addict = runtimes.TypeAddict(tr, 'addict')
        tr.vars['var1'] = 'Hello'
        tr.vars['var2'] = 'World'
        tr.vars['var3'] = '!'
        tr.vars.update(x=1, y=2, d=dict(en="Hi", cz="Ahoj", sk="Ahoj"))
        tr.files['f1'] = dict(name='file/f1', id='f1')
        tr.files['f2'] = dict(name='file/f2', id='f2')
        tr.files['f3'] = dict(name='file/f3', id='f3')
        del tr.files['f3']
        tr.tasks['1'] = 'task1'
        tr.tasks['2'] = 'task2'
        while len(tr.queue) > 0:
            tr.queue.pop()
        assert len(tr.queue) == 0
        tr.queue.append('first')
        tr.queue.extend(['second', 'third', 'fourth'])
        tr.queue += 'fifth'
        assert tr.queue == ['first', 'second', 'third', 'fourth', 'fifth']
        assert tr.queue != ['first', 'second', 'third', 'fourth']
        assert tr.queue != ['first', 'second', 'third', 'fourth', 'fifth', 'sixth']
        tr.queue[0] = '1st'
        tr.queue[4] = '5th'
        assert tr.queue == ['1st', 'second', 'third', 'fourth', '5th']
        tr.queue[-5] = 'First'
        tr.queue[-1] = 'Fifth'
        assert tr.queue == ['First', 'second', 'third', 'fourth', 'Fifth']
        tr.queue.check()
        tr.tqueue.extend([0, 1, 2, 3])
        del tr.tqueue[3]
        del tr.tqueue[-1]
        del tr.tqueue[0]
        del tr.tqueue[0]
        assert tr.tqueue == []
        tr.tqueue.check()
        tr.addict[None] = 'b'
        tr.addict['a'] = None
        tr.addict['b'] = 'c'
        tr.addict.update(dict(c=None, d='e'))
        assert not tr.addict.has_key('a')
        assert tr.addict['b'] == 'c'
        assert not tr.addict.has_key('c')
        assert tr.addict['d'] == 'e'
        tr.close()

        tr = TestingRuntime(TESTDB)
        tr.tasks = runtimes.TypeDict(tr, 'tasks')
        tr.tqueue = runtimes.TypeList(tr, 'testqueue')
        tr.addict = runtimes.TypeAddict(tr, 'addict')
        assert tr.vars['var1'] == 'Hello'
        assert tr.vars['var2'] == 'World'
        assert tr.vars['var3'] == '!'
        assert tr.vars['x'] == 1
        assert tr.vars['y'] == 2
        assert tr.vars['d']['en'] == 'Hi'
        assert tr.files['f1'] == dict(name='file/f1', id='f1')
        assert tr.files['f2'] == dict(name='file/f2', id='f2')
        assert tr.files.get('f3', None) == None
        assert tr.tasks['1'] == 'task1'
        assert tr.tasks['2'] == 'task2'
        assert tr.queue == ['First', 'second', 'third', 'fourth', 'Fifth']
        assert tr.tqueue == []
        assert not tr.addict.has_key('a')
        assert tr.addict['b'] == 'c'
        assert not tr.addict.has_key('c')
        assert tr.addict['d'] == 'e'
        tr.close()

