# -*- test-case-name: beah.misc.test.test_runtimes -*-

# Beah - Test harness. Part of Beaker project.
#
# Copyright (C) 2010 Marian Csontos <mcsontos@redhat.com>
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

import exceptions
import shelve
from beah.misc import pre_open
from beah.core import make_addict


UNDEFINED=[]


class BaseRuntime(object):

    """
    Baseclass for persistent objects with better granularity than shelve.

    Subclass should implement these methods:
        type_set_primitive(rt, type, key, value)
        type_del_primitive(rt, type, key)
        type_get(rt, type, key)
        type_keys(rt, type)
    And depending on the implementation these:
        close(rt)
        sync(rt, type=None)
    This one might be redefined for performance reasons:
        type_has_key(rt, type, key)

    Its instance can define dict members this way:
        rt = ShelveRuntime(fname)
        rt.vars = TypeDict(rt, 'var')
        rt.files = TypeDict(rt, 'file')
    or in subclass' contructor.
    These can be accessed as normal dictionary
        rt.vars['a'] = 11
    """

    def __init__(self):
        pass

    def close(self):
        self.sync()

    def sync(self, type=None):
        pass

    def type_set(self, type, key, value):
        self.type_set_primitive(type, key, value)
        self.sync(type)
        return None

    def type_del(self, type, key):
        self.type_del_primitive(type, key)
        self.sync(type)

    def type_has_key(self, type, key):
        return key in self.type_keys(type)

    def type_set_primitive(self, type, key, value):
        raise exceptions.NotImplementedError

    def type_del_primitive(self, type, key):
        raise exceptions.NotImplementedError

    def type_get(self, type, key, defval=UNDEFINED):
        raise exceptions.NotImplementedError

    def type_keys(self, type):
        raise exceptions.NotImplementedError



class TypeDict(object):

    """
    Class implementing dictionary functionality using runtime object for
    storage.
    """

    def __init__(self, runtime, type):
        self.runtime = runtime
        self.type = type

    def __setitem__(self, key, value):
        return self.runtime.type_set(self.type, key, value)

    def __getitem__(self, key):
        return self.runtime.type_get(self.type, key)

    def __delitem__(self, key):
        return self.runtime.type_del(self.type, key)

    def keys(self):
        return self.runtime.type_keys(self.type)

    def has_key(self, key):
        return self.runtime.type_has_key(self.type, key)

    def get(self, key, defval=UNDEFINED):
        if self.has_key(key):
            return self[key]
        if defval is UNDEFINED:
            raise exceptions.KeyError("Key %r is not present." % key)
        return defval

    def setdefault(self, key, defval=None):
        if self.has_key(key):
            return self[key]
        self[key] = defval
        return defval

    def update(self, *dicts, **kwargs):
        cache = {}
        for dict_ in dicts:
            cache.update(dict_)
        cache.update(kwargs)
        for key, value in cache.items():
            self.runtime.type_set_primitive(self.type, key, value)
        self.runtime.sync(self.type)


def TypeAddict_init(self, runtime, type):
    TypeDict.__init__(self, runtime, type)
TypeAddict = make_addict(TypeDict)
TypeAddict.__init__ = TypeAddict_init


class TypeList(object):

    """
    Class implementing list functionality using runtime object for storage.
    """

    def __init__(self, runtime, type):
        self.runtime = runtime
        self.type = type
        f = self.__first = int(self.runtime.type_get(self.type, 'first', 0))
        l = self.__last = int(self.runtime.type_get(self.type, 'last', -1))
        index = []
        while f <= l:
            key = str(f)
            if self.runtime.type_has_key(self.type, key):
                index.append(key)
            f += 1
        self.__index = index

    def __len__(self):
        return len(self.__index)

    def __contains__(self, value):
        for v in self:
            if v == value:
                return True
        return False

    def __eq__(self, iterable):
        it = self.__iter__()
        it2 = iterable.__iter__()
        while True:
            try:
                v = it.next() # pylint: disable=E1101
            except exceptions.StopIteration:
                break
            try:
                v2 = it2.next()
            except exceptions.StopIteration:
                return False
            if v != v2:
                return False
        try:
            it2.next()
            return False
        except exceptions.StopIteration:
            return True

    def __ne__(self, iterable):
        return not (self == iterable)

    def __iter__(self):
        for ix in self.__index:
            yield self.runtime.type_get(self.type, ix)
        raise exceptions.StopIteration

    def __normalize_ix(self, ix):
        if ix < 0:
            ix = len(self) + ix
            if ix < 0:
                raise exceptions.KeyError('Not enough items in list')
        return ix

    def __getitem__(self, ix):
        ix = self.__normalize_ix(ix)
        return self.runtime.type_get(self.type, self.__index[ix])

    def __setitem__(self, ix, value):
        ix = self.__normalize_ix(ix)
        return self.runtime.type_set(self.type, self.__index[ix], value)

    def __delitem__(self, ix):
        ix = self.__normalize_ix(ix)
        self.runtime.type_del(self.type, str(self.__index[ix]))
        del self.__index[ix]
        n = len(self)
        upd = False
        if n == 0:
            self.__first = 0
            self.__last = -1
            upd = True
        elif ix == 0:
            self.__first = int(self.__index[0])
            upd = True
        elif ix == n:
            self.__last = int(self.__index[-1])
            upd = True
        if upd:
            self.runtime.type_set_primitive(self.type, 'first', self.__first)
            self.runtime.type_set_primitive(self.type, 'last', self.__last)
            self.runtime.sync(self.type)

    def __add(self, value):
        l = self.__last = self.__last + 1
        self.runtime.type_set_primitive(self.type, 'last', l)
        key = str(l)
        self.__index.append(key)
        self.runtime.type_set_primitive(self.type, key, value)

    def __iadd__(self, value):
        self.__add(value)
        self.runtime.sync(self.type)
        return self

    def append(self, value):
        self.__add(value)
        self.runtime.sync(self.type)

    def extend(self, iterable):
        for value in iterable:
            self.__add(value)
        self.runtime.sync(self.type)

    def pop(self, ix=-1):
        answ = self[ix]
        del self[ix]
        return answ

    def dump(self):
        return (self.__first, self.__last, list([(ix, self[i]) for i, ix in enumerate(self.__index)]))

    def check(self):
        f = int(self.runtime.type_get(self.type, 'first', 0))
        l = int(self.runtime.type_get(self.type, 'last', -1))
        v = list([(str(i), self.runtime.type_get(self.type, str(i)))
            for i in xrange(f, l+1) if self.runtime.type_has_key(self.type,
                str(i))])
        d = self.dump()
        r = (f, l, v)
        assert d == r


class DictRuntime(BaseRuntime):
    """
    Runtime using dict to store data.
    """

    def __init__(self, dict_):
        self.dict_ = dict_
        BaseRuntime.__init__(self)

    def close(self):
        pass

    def sync(self, type=None):
        pass

    def mk_type_key(self, type, key):
        # NOTE: In python 2.3 this might return unicode, which is not handled
        # by shelve.
        return str("%s/%s" % (type, key))

    def unmk_type_key(self, id):
        l = id.find("/")
        # Note: ``id[l:][1:]'' is not the same as ``id[l+1:]'' if l is -1
        return (id[:l], id[l:][1:])

    def type_set_primitive(self, type, key, value):
        self.dict_[self.mk_type_key(type, key)] = value

    def type_del_primitive(self, type, key):
        del self.dict_[self.mk_type_key(type, key)]

    def type_get(self, type, key, defval=UNDEFINED):
        if defval is UNDEFINED:
            return self.dict_[self.mk_type_key(type, key)]
        return self.dict_.get(self.mk_type_key(type, key), defval)

    def type_has_key(self, type, key):
        return self.dict_.has_key(self.mk_type_key(type, key))

    def type_keys(self, type):
        tl = len(type)+1
        type = type + '/'
        return [key[tl:] for key in self.dict_.keys() if key[:tl] == type]

    def dump(self):
        return list([(k, v) for k, v in enumerate(self.dict_)])


class ShelveRuntime(DictRuntime):
    """
    Runtime using shelve to store data.
    """

    def __init__(self, fname):
        self.fname = fname
        pre_open(fname)
        DictRuntime.__init__(self, shelve.open(fname, 'c'))

    def close(self):
        if self.dict_ is not None:
            self.dict_.close()
            self.dict_ = None

    def sync(self, type=None): # pylint: disable=E0202
        self.dict_.sync()

