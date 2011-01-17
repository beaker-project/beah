# -*- test-case-name: beah.misc.test.test_jsonenv -*-

from twisted.trial import unittest

from beah.misc import jsonenv

import shutil
import tempfile
import sys
import os

class TestAll(unittest.TestCase):

    def test_copy_dict_typecheck(self):

        env = {"S":"str", "O":object(), "T":(), "L":[], "U":u"hello"}

        env2 = {}
        assert not jsonenv._copy_dict_typecheck(env, env2, str, jsonenv.SKIP)
        assert env2 == {"S":"str"}

        env2 = {}
        assert not jsonenv._copy_dict_typecheck(env, env2, (str, unicode), jsonenv.SKIP)
        assert env2 == {"S":"str", "U":u"hello"}

        env2 = {}
        assert not jsonenv._copy_dict_typecheck(env, env2, str, jsonenv.ABORT)
        for key in ("O", "T", "L", "U"):
            assert not env2.has_key(key)

        env2 = {}
        try:
            jsonenv._copy_dict_typecheck(env, env2, str, jsonenv.RAISE)
            assert False
        except:
            pass


    def testMain(self):

        def unlink_failsafe(filename):
            try:
                os.unlink(fn)
            except:
                pass

        def check_empty_db(filename):
            env = {}
            assert jsonenv.update_env(fn, env, jsonenv.RAISE)
            assert env == {}
            env = {"ITEM":"val"}
            assert jsonenv.update_env(fn, env, jsonenv.RAISE)
            assert env == {"ITEM":"val"}

        def check_db(filename, expected=None):
            env = {}
            assert jsonenv.update_env(fn, env, jsonenv.SKIP)
            if expected is not None:
                if env != expected:
                    #print "got:", env
                    #print "file(%s): <<END" % filename
                    f = open(fn, "r")
                    try:
                        pass
                        #print f.read()
                    finally:
                        f.close()
                    #print "END"
                    assert env == expected

        d = tempfile.mkdtemp()
        try:
            #print >> sys.stderr, "Tempdir: %s" % d

            fn = os.path.join(d, "empty.db")
            try:
                check_empty_db(fn)
            finally:
                unlink_failsafe(fn)

            # check non-empty DB will add all values to dict:
            env = {"VAR1":"VAL1", "VAR2":"VAL2"}
            fn = os.path.join(d, "test.db")
            assert jsonenv.export_env(fn, env, jsonenv.RAISE)
            try:
                check_db(fn, env)
                env2 = {}
                assert jsonenv.update_env(fn, env2, jsonenv.RAISE)
                assert env == env2
            finally:
                unlink_failsafe(fn)

            # check RAISE:
            env = {"VAR1":"VAL1", "VAR2":"VAL2", "BAD":object()}
            fn = os.path.join(d, "test.db")
            try:
                try:
                    jsonenv.export_env(fn, env, jsonenv.RAISE)
                    assert False
                except:
                    pass
                check_empty_db(fn)
            finally:
                unlink_failsafe(fn)

            # check ABORT:
            env = {"VAR1":"VAL1", "VAR2":"VAL2", "BAD":object()}
            fn = os.path.join(d, "test.db")
            try:
                assert not jsonenv.export_env(fn, env, jsonenv.ABORT)
                check_empty_db(fn)
            finally:
                unlink_failsafe(fn)

            # check SKIP:
            env = {"VAR1":"VAL1", "VAR2":"VAL2", "BAD":object()}
            fn = os.path.join(d, "test.db")
            try:
                assert not jsonenv.export_env(fn, env, jsonenv.SKIP)
                env2 = {}
                assert jsonenv.update_env(fn, env2, jsonenv.RAISE)
                env3 = dict(env)
                del env3["BAD"]
                assert env2 == env3
            finally:
                unlink_failsafe(fn)

        finally:
            shutil.rmtree(d)

