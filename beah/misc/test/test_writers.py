# -*- test-case-name: beah.misc.test.test_writers -*-

from twisted.trial import unittest

from beah.misc import writers


class TestWriter(unittest.TestCase):

    def testWriter(self):
        l = []
        wr = writers.Writer()
        wr.repr = lambda obj: "%r\n" % obj
        wr.send = l.append
        wr.write(1)
        self.failUnlessEqual(l, ['1\n'])
        wr.write('a')
        self.failUnlessEqual(l, ['1\n', "'a'\n"])


class TestCachingWriter(unittest.TestCase):

    def testNoSplit(self):
        l = []
        wr = writers.CachingWriter(4)
        wr.repr = lambda obj: "%s" % obj
        wr.send = l.append
        wr.write('012345')
        self.failUnlessEqual(l, ['0123'])
        wr.write('')
        self.failUnlessEqual(l, ['0123'])
        wr.write('6')
        self.failUnlessEqual(l, ['0123'])
        wr.write('789012')
        self.failUnlessEqual(l, ['0123', '4567', '8901'])
        wr.flush()
        self.failUnlessEqual(l, ['0123', '4567', '8901', '2'])
        wr.write('012345')
        self.failUnlessEqual(l, ['0123', '4567', '8901', '2', '0123'])
        wr.close()
        self.failUnlessEqual(l, ['0123', '4567', '8901', '2', '0123', '45'])

    def testSplit(self):
        l = []
        wr = writers.CachingWriter(4, True)
        wr.repr = lambda obj: "%s" % obj
        wr.send = l.append
        wr.write('0')
        self.failUnlessEqual(l, [])
        wr.write('12')
        self.failUnlessEqual(l, [])
        wr.write('345678')
        self.failUnlessEqual(l, ['012345678'])
        wr.write('0')
        self.failUnlessEqual(l, ['012345678'])
        wr.write('1')
        self.failUnlessEqual(l, ['012345678'])
        wr.write('2')
        self.failUnlessEqual(l, ['012345678'])
        wr.write('3')
        self.failUnlessEqual(l, ['012345678', '0123'])
        wr.write('012')
        wr.close()
        self.failUnlessEqual(l, ['012345678', '0123', '012'])


class FakeWriter(writers.JournallingWriter):
    def __init__(self, ss, l, offs=-1, wroff=lambda x: None):
        self.l = l
        self.wroff = wroff
        writers.JournallingWriter.__init__(self, ss, offs, 4)
    def set_offset(self, offs):
        self.wroff(offs)
        writers.JournallingWriter.set_offset(self, offs)
    def repr(self, obj): # pylint: disable=E0202
        return "%s" % obj
    def send(self, data): # pylint: disable=E0202
        self.l.append(data)
    def clear(self):
        # close without flushing
        self.wroff = lambda x: None
        self.cache_pop(len(self.cache_get()))
        self.close()


class MemoryCell(object):
    def __init__(self, value=0): self.value = value
    def set(self, offset): self.value = offset
    def get(self): return self.value


class TestJournallingWriter(unittest.TestCase):

    def _test(self):
        self.failUnlessEqual(self.l, self.l_expected)
        self.failUnlessEqual(self.ss.getvalue(), self.ss_expected.getvalue())
        self.failUnlessEqual(self.mem.get(), sum([len(str_) for str_ in self.l_expected]))

    def _test_wr(self, str_, new_items):
        self.ss_expected.write(str_)
        self.wr.write(str_)
        self.l_expected.extend(new_items)
        self._test()

    def testMain(self):
        from StringIO import StringIO

        self.mem = MemoryCell()
        wroff = self.mem.set
        self.l = []
        self.l_expected = []
        self.ss = StringIO()
        self.ss_expected = StringIO()

        self.wr = FakeWriter(self.ss, self.l, -1, wroff)
        self._test()
        self._test_wr('012345', ['0123'])
        self._test_wr('', [])
        self._test_wr('6', [])
        self._test_wr('7', ['4567'])
        self._test_wr('8901', ['8901'])
        self._test_wr('2', [])
        self.wr.clear()
        self._test()

        self.wr = FakeWriter(self.ss, self.l, self.mem.get(), wroff)
        self._test()

        self._test_wr('34', [])

        self.wr.flush()
        self.l_expected.append('234')
        self._test()

        self._test_wr('012345', ['0123'])

        self.wr.close()
        self.l_expected.append('45')
        self._test()

