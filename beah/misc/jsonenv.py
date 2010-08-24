# Beah - Test harness. Part of Beaker project.
#
# Copyright (C) 2010 Red Hat, Inc.
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


import os
import simplejson as json
import exceptions
import beah.misc


def _copy_dict_check(src, dst, checkf, errorf):
    answ = True
    for key in src.keys():
        val = src[key]
        if checkf(key, val):
            dst[key] = val
        else:
            answ = None
            if not errorf(key, val):
                return None
    return answ


def _copy_dict_typecheck(src, dst, types, errorf):
    return _copy_dict_check(src, dst,
            lambda key, value: isinstance(value, types),
            errorf)


def SKIP(key, value): return True
def ABORT(key, value): return False
def RAISE(key, value): raise exceptions.TypeError("env[%s] = %r is not a string." % (key, value))


def _read_env(filename, on_error=ABORT):
    """
    Read dictionary from json file.
    """
    env = {}
    if os.path.exists(filename):
        f = open(filename, "r")
        try:
            try:
                db = json.load(f)
            except:
                db = {}
        finally:
            f.close()
    else:
        db = {}
    answ = _copy_dict_typecheck(db, env, (str, unicode), on_error)
    if not answ and on_error == ABORT:
        return None
    return env


def export_env(filename, env=None, on_error=ABORT):
    """
    Write environment env to json file.

    Use current environment if env is None.
    """
    if env is None:
        env_ = dict(os.environ)
        answ = True
    else:
        env_ = {}
        answ = _copy_dict_typecheck(env, env_, (str, unicode), on_error)
        if not answ and on_error == ABORT:
            return False
    beah.misc.pre_open(filename)
    f = open(filename, "w+")
    try:
        try:
            json.dump(env_, f)
            return answ
        except:
            os.unlink(filename)
            raise
    finally:
        f.close()


def update_env(filename, env=None, on_error=ABORT):
    """
    Update environment env from json file.

    Use current environment if env is None.
    """
    if env is None:
        env = os.environ
    env_ = _read_env(filename, on_error)
    if env_ is None:
        return None
    env.update(env_)
    return True


if __name__ == "__main__":
    import shutil
    import tempfile
    import sys

    env = {"S":"str", "O":object(), "T":(), "L":[], "U":u"hello"}

    env2 = {}
    assert not _copy_dict_typecheck(env, env2, str, SKIP)
    assert env2 == {"S":"str"}

    env2 = {}
    assert not _copy_dict_typecheck(env, env2, (str, unicode), SKIP)
    assert env2 == {"S":"str", "U":u"hello"}

    env2 = {}
    assert not _copy_dict_typecheck(env, env2, str, ABORT)
    for key in ("O", "T", "L", "U"):
        assert not env2.has_key(key)

    env2 = {}
    try:
        _copy_dict_typecheck(env, env2, str, RAISE)
        assert False
    except:
        pass


    def unlink_failsafe(filename):
        try:
            os.unlink(fn)
        except:
            pass

    def check_empty_db(filename):
        env = {}
        assert update_env(fn, env, RAISE)
        assert env == {}
        env = {"ITEM":"val"}
        assert update_env(fn, env, RAISE)
        assert env == {"ITEM":"val"}

    def check_db(filename, expected=None):
        env = {}
        assert update_env(fn, env, SKIP)
        if expected is not None:
            if env != expected:
                print "got:", env
                print "file(%s): <<END" % filename
                f = open(fn, "r")
                try:
                    print f.read()
                finally:
                    f.close()
                print "END"
                assert env == expected

    d = tempfile.mkdtemp()
    try:
        print >> sys.stderr, "Tempdir: %s" % d

        fn = os.path.join(d, "empty.db")
        try:
            check_empty_db(fn)
        finally:
            unlink_failsafe(fn)

        # check non-empty DB will add all values to dict:
        env = {"VAR1":"VAL1", "VAR2":"VAL2"}
        fn = os.path.join(d, "test.db")
        assert export_env(fn, env, RAISE)
        try:
            check_db(fn, env)
            env2 = {}
            assert update_env(fn, env2, RAISE)
            assert env == env2
        finally:
            unlink_failsafe(fn)

        # check RAISE:
        env = {"VAR1":"VAL1", "VAR2":"VAL2", "BAD":object()}
        fn = os.path.join(d, "test.db")
        try:
            try:
                export_env(fn, env, RAISE)
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
            assert not export_env(fn, env, ABORT)
            check_empty_db(fn)
        finally:
            unlink_failsafe(fn)

        # check SKIP:
        env = {"VAR1":"VAL1", "VAR2":"VAL2", "BAD":object()}
        fn = os.path.join(d, "test.db")
        try:
            assert not export_env(fn, env, SKIP)
            env2 = {}
            assert update_env(fn, env2, RAISE)
            env3 = dict(env)
            del env3["BAD"]
            assert env2 == env3
        finally:
            unlink_failsafe(fn)

    finally:
        shutil.rmtree(d)

