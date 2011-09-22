# -*- test-case-name: beah.backends.test.test_beakerlc -*-

from twisted.trial import unittest

from beah.backends import beakerlc
from beah import config
from beah.test import twisted_debug


class TestConfigure(unittest.TestCase):

    def test_defaults(self):
        """Check the default options are present"""
        beakerlc.configure(args=[])
        cfg = config._get_config('beah-backend')
        conf = config.get_conf('beah-backend')
        #cfg.print_()
        #conf.write(sys.stdout)
        assert conf.has_option('DEFAULT', 'NAME')
        assert conf.has_option('DEFAULT', 'LAB_CONTROLLER')
        assert conf.has_option('DEFAULT', 'RECIPEID')
        assert conf.has_option('DEFAULT', 'HOSTNAME')
        assert conf.has_option('DEFAULT', 'INTERFACE')
        assert conf.has_option('DEFAULT', 'PORT')
        assert conf.has_option('DEFAULT', 'LOG')
        assert conf.has_option('DEFAULT', 'DEVEL')
        assert conf.has_option('DEFAULT', 'VAR_ROOT')
        assert conf.has_option('DEFAULT', 'LOG_PATH')
        assert conf.has_option('DEFAULT', 'RUNTIME_FILE_NAME')
        assert conf.has_option('DEFAULT', 'DIGEST')
        assert conf.has_option('DEFAULT', 'RPC_TIMEOUT')
        config._Config._remove('beah-backend')

    def test_defaults_twice(self):
        """Check the config is removed properly"""
        self.test_defaults()
        self.test_defaults()


#twisted_debug().set()

