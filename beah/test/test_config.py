# -*- test-case-name: beah.test.test_config -*-

import tempfile
import os
from optparse import OptionParser

from twisted.trial import unittest

from beah import config
from beah.misc import parse_bool


def _tst_eq(result, expected):
    """Check test result against expected value and assert on
    missmatch."""
    try:
        assert result == expected
    except:
        print "Failed: result:%r == expected:%r" % (result, expected)
        raise

def _tst_ne(result, expected):
    """Check test result against expected value and assert on
    missmatch."""
    try:
        assert result != expected
    except:
        print "Failed: result:%r != expected:%r" % (result, expected)
        raise

def _try_beah_conf():
    config.beah_conf(overrides={'BEAH_CONF':'', 'TEST':'Test'}, args=[])
    def dump_config(cfg):
        print "\n=== Dump:%s ===" % cfg.id
        print "files: %s + %s" % (cfg._conf_runtime(None), cfg._conf_files())
        print "file: %s" % (cfg._get_conf_file({}), )
    #config._get_config('beah').print_()
    config._Config._remove('beah')

def _try_backend_conf():
    config.backend_conf('BEAH_BEAKER_CONF', 'beah_beaker.conf',
            {'MY_OWN':'1', 'TEST.MY_OWN':'2', 'TEST2.DEF':'3'},
            {'DEFAULT.MY_OWN':'4', 'TEST.MY_OWN':'3'})
    #config._get_config('beah-backend').print_()
    #config._get_config('beah-backend').print_(defaults_display='exclude')
    #config._get_config('beah-backend').print_(defaults_display='show')
    #config._get_config('beah-backend').print_(raw=True)
    #config._get_config('beah-backend').print_(raw=True, defaults_display='exclude')
    #config._get_config('beah-backend').print_(raw=True, defaults_display='show')
    #dump_config(config._get_config('beah-backend'))
    config._Config._remove('beah-backend')

def _try_conf():
    #_try_beah_conf()
    _try_backend_conf()

def _try_conf2():
    overrides = config.backend_opts(args=[])
    config.backend_conf(
            defaults={'NAME':'beah_demo_backend'},
            overrides=overrides)
    config._Config._remove('beah-backend')


def test_parse_bool(arg):
    return parse_bool(arg) and True or False


def _test_conf():

    """Self test."""

    _tst_eq(config._Config.parse_conf_name('NAME'), ('DEFAULT', 'NAME'))
    _tst_eq(config._Config.parse_conf_name('SEC.NAME'), ('SEC', 'NAME'))

    fd, fn = tempfile.mkstemp()
    try:
        os.close(fd)
        c = config._BeahConfig('test', '_BEAH_CONF', '_beah.conf',
                config.beah_defaults(),
                dict(ROOT='/mnt/testarea', LOG='False', DEVEL='True', _BEAH_CONF=fn))
        _tst_eq(c._get_conf_file(fn), fn)
        _tst_eq(c._get_conf_file(), '')
        _tst_eq(c._get_conf_file('empty-beah.conf.tmp'), '')

        cfg = c.conf
        cfg.set('BACKEND', 'INTERFACE', "127.0.0.1")
        _tst_eq(test_parse_bool(cfg.get('DEFAULT', 'DEVEL')), True)
        _tst_eq(test_parse_bool(cfg.get('DEFAULT', 'LOG')), False)
        _tst_eq(cfg.get('BACKEND', 'INTERFACE'), "127.0.0.1")
        _tst_eq(int(cfg.get('BACKEND', 'PORT')), 12432)
        _tst_eq(cfg.get('DEFAULT', 'ROOT'), "/mnt/testarea")

        cfg.set('DEFAULT', 'LOG', 'True')
        _tst_eq(test_parse_bool(cfg.get('DEFAULT', 'DEVEL')), True)
        _tst_eq(test_parse_bool(cfg.get('DEFAULT', 'LOG')), True)
        _tst_eq(cfg.get('BACKEND', 'INTERFACE'), "127.0.0.1")
        _tst_eq(int(cfg.get('BACKEND', 'PORT')), 12432)
        _tst_eq(cfg.get('DEFAULT', 'ROOT'), "/mnt/testarea")

        config._Config._remove('test')
    finally:
        os.remove(fn)


    try:
        c = config._Config('test2', None, 'empty-missing-no.conf',
                dict(GREETING="Hello %(NAME)s!"), dict(NAME="World"))
        try:
            config._Config._remove('test2')
        except:
            pass
        raise RuntimeError("this should have failed with exception")
    except:
        pass

    c = config._Config('test3', None, None,
            dict(GREETING="Hello %(NAME)s!"),
            dict(NAME="World"))
    _tst_eq(c.conf.get('DEFAULT', 'GREETING'), 'Hello World!')
    _tst_eq(config.get_conf('test3').get('DEFAULT', 'GREETING'), 'Hello World!')
    config._Config._remove('test3')

def _test_opt():
    conf = {}
    opt = config.beah_opt(OptionParser(), conf)
    #print opt.get_usage()
    #opt.print_help()
    #print opt.format_help()

    cmd_args = '-v -v -q -L info -O arg1 arg2'.split(' ')
    opts, args = opt.parse_args(cmd_args)
    #print opts, args, conf
    assert opts.verbose == 2
    assert opts.quiet == 1
    assert conf['LOG'] == 'info'
    assert conf['CONSOLE_LOG'] == 'True'

    cmd_args = "-v -v -v -v -q -p 1234 -i '' -P 4321 -I 127.0.0.1 -c conf -L debug -O arg1 arg2".split(" ")
    opts, args = opt.parse_args(cmd_args)
    #print opts, args, conf

    if 0:
        def cb_test(option, opt_str, value, parser):
            print option, opt_str, value, parser
            #print dir(option)
            #print dir(parser)
            print option.dest
            print option.metavar
        opt.add_option("--cb", "--test-cb", "--cb-test", action="callback", callback=cb_test)
        opt.parse_args(['--cb'])

class TestConfig(unittest.TestCase):

    def test_all(self):
        #from beah.misc import log_this, make_class_verbose
        #make_class_verbose(config._BeahConfig, log_this.print_this)
        _try_conf()
        _test_conf()
        _test_opt()
        _try_conf2()


