# -*- test-case-name: beah.core.test.test_core -*-

# Beah - Test harness. Part of Beaker project.
#
# Copyright (C) 2009 Red Hat, Inc.
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

import uuid
import exceptions

def new_id():
    """
    Function generating unique id's.

    Return: a string representation of id.
    """
    return str(uuid.uuid4())

def esc_name(name):
    """
    Escape name to be suitable as an identifier.
    """
    if name.isalnum():
        return name
    # using and/or to simulate if/else
    # FIXME: is there a built-in?
    return ''.join([(c.isalnum() and c) or (c=='_' and '__') or '_%x' % ord(c)
            for c in name])


def prettyprint_list(list_, last_join="or"):
    """
    Format list.

    Example:
    >>> prettyprint_list(["An apple", "two pears", "three oranges."], last_join="and")
    'An apple, two pears and three oranges.'

    """
    if not list_:
        return ""
    if len(list_) == 1:
        return str(list_[0])
    l = list([str(item) for item in list_])
    return ", ".join(l[:-1]) + " %s " % last_join + l[-1]


def check_type(name, value, type_, allows_none=False):
    """Check value is of type type_ or None if allows_none is True."""
    if isinstance(value, type_):
        return
    if allows_none and value is None:
        return
    if isinstance(type_, tuple):
        types = list([t.__name__ for t in type_])
    else:
        types = [type_.__name__]
    if allows_none:
        types.append("None")
    raise exceptions.TypeError('%r not permitted as %s. Has to be %s.' \
            % (value, name, prettyprint_list(types)))


def make_addict(d):

    class new_addict(d):

        """
        Dictionary extension, which filters input.
        """

        def __init__(self, *args, **kwargs):
            tmp = self.flatten(args, kwargs)
            d.__init__(self, tmp)

        def filter(self, k, v):
            """
            Filter function.

            This method is to be reimplemented.

            Returning True, if (k,v) pair is to be included in dictionary.
            """
            return k is not None and v is not None

        def flatten(self, args, kwargs):
            # FIXME: a in args could be:
            # - a dictionary
            # - an iterable of key/value pairs (as a tuple or another iterable
            #   of length 2.)
            tmp = dict()
            for a in args:
                #check_type('an argument', a, dict)
                for k, v in a.items():
                    if self.filter(k, v):
                        tmp[k] = v
            for k, v in kwargs.items():
                if self.filter(k, v):
                    tmp[k] = v
            return tmp

        def update(self, *args, **kwargs):
            d.update(self, self.flatten(args, kwargs))

        def __setitem__(self, k, v):
            if self.filter(k, v):
                d.__setitem__(self, k, v)

    return new_addict

addict = make_addict(dict)

