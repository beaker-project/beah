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
        d.update(d='e')
        ad.update({None: 'e', 'e': None, 'f': 'g'})
        d.update({'f': 'g'})
        assert ad == dict(b='c', d='e', f='g')
        assert ad == d
        ad = core.addict(a=None, b='c')
        assert ad == dict(b='c')

