# -*- test-case-name: beah.core.test.test_core -*-

from twisted.trial import unittest

from beah import core


class TestEscName(unittest.TestCase):

    def test_esc_name(self):
        assert core.esc_name('') == ''
        assert core.esc_name('a') == 'a'
        assert core.esc_name('1') == '1'
        assert core.esc_name('_') == '__'
        assert core.esc_name('-') == '_%x' % ord('-')
        assert core.esc_name('a_b') == 'a__b'
        assert core.esc_name('a-b') == 'a_%xb' % ord('-')

class TestAddict(unittest.TestCase):

    def test_addict(self):
        ad = core.addict()
        d = dict()
        ad[None] = 'a'
        ad['a'] = None
        d['b'] = ad['b'] = 'c'
        ad.update(c=None, d='e')
        d.update({'d': 'e'})
        ad.update({None: 'e', 'e': None, 'f': 'g'})
        d.update({'f': 'g'})
        assert ad == dict(b='c', d='e', f='g')
        assert ad == d
        ad = core.addict(a=None, b='c')
        assert ad == dict(b='c')


class TestPrettyprintList(unittest.TestCase):

    def test_empty(self):
        self.failUnlessEqual(core.prettyprint_list([]), "")

    def test_single(self):
        self.failUnlessEqual(core.prettyprint_list([1]), "1")

    def test_two(self):
        self.failUnlessEqual(core.prettyprint_list([1, 2]), "1 or 2")

    def test_many(self):
        self.failUnlessEqual(core.prettyprint_list([1, 2, 3]), "1, 2 or 3")

    def test_many_all(self):
        self.failUnlessEqual(
                core.prettyprint_list([1, 2, 3], last_join="and"),
                "1, 2 and 3")


class TestCheckType(unittest.TestCase):

    def test_single(self):
        self.failUnlessEqual(
                core.check_type("NAME", "hello", str, allows_none=False),
                None)

    def test_tuple(self):
        self.failUnlessEqual(
                core.check_type("NAME", 1, (str, int), allows_none=False),
                None)

    def test_none(self):
        self.failUnlessEqual(
                core.check_type("NAME", None, str, allows_none=True),
                None)
        self.failUnlessEqual(
                core.check_type("NAME", None, (str, int), allows_none=True),
                None)

    def test_single_fail(self):
        self.failUnlessRaises(
                TypeError,
                core.check_type, "NAME", 1, str, allows_none=False)

    def test_tuple_fail(self):
        self.failUnlessRaises(
                TypeError,
                core.check_type, "NAME", (), (str, int), allows_none=False)

    def test_none_fail(self):
        self.failUnlessRaises(
                TypeError,
                core.check_type, "NAME", None, str, allows_none=False)

