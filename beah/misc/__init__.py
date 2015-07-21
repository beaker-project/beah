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

import exceptions
import socket
import traceback
import os
import os.path
import sys
import logging
import logging.handlers
import inspect
import re

def raiser(exc=exceptions.Exception, *args, **kwargs):
    raise exc(*args, **kwargs)

if sys.version_info[1] >= 4:
    def setfname(f, name):
        f.__name__= name
else:
    def setfname(f, name):
        pass

def Raiser(exc=exceptions.Exception, *args, **kwargs):
    def raiser():
        raise exc(*args, **kwargs)
    setfname(raiser, "raiser_"+exc.__name__)
    return raiser

def mktemppipe():
    from tempfile import mktemp
    from os import mkfifo
    retries = 3
    while True:
        pname=mktemp()
        try:
            mkfifo(pname)
            return pname
        except:
            retries -= 1
            if retries <= 0:
                raise

def localhost_(host):
    return host in ['', '::1', '::', 'localhost', 'localhost.localdomain',
                    '127.0.0.1', 'localhost4', 'localhost4.localdomain4']

def test_loop_port(host):
    """
    Return None if host is not testing loop.
    Otherwise empty string or port number is returned.
    """
    if host[:9] == 'test.loop':
        return host[10:]
    return None

def test_loop(host):
    """
    Returns True if host is testing loop, False otherwise.

    Constrain: this must use lowercase characters only!
    """
    return host[:9] == 'test.loop'

def TEST_LOOP(host):
    """
    Returns True if host is testing loop, False otherwise.

    Constrain: this must use uppercase characters only!
    """
    return host[:9] == 'TEST.LOOP'

def _localhosts_aggressive():
    answ={}
    stack=['localhost', '127.0.0.1', socket.getfqdn(), socket.gethostname()]
    def lh_add(*hs):
        for h in hs:
            if answ.has_key(h):
                continue
            stack.append(h)
    while stack:
        h = stack.pop()
        if answ.has_key(h):
            continue
        answ[h] = True
        lh_add(socket.getfqdn(h))
        try:
            lh_add(socket.gethostbyname(h))
        except:
            pass
        try:
            fqdn, aliases, ip_addresses = socket.gethostbyname_ex(h)
            lh_add(fqdn, *aliases)
            lh_add(*ip_addresses)
        except:
            pass
        try:
            fqdn, aliases, ip_addresses = socket.gethostbyaddr(h)
            lh_add(fqdn, *aliases)
            lh_add(*ip_addresses)
        except:
            pass
    return answ

_LOCALHOSTS = {}
def _localhosts():
    global _LOCALHOSTS
    if not _LOCALHOSTS:
        _LOCALHOSTS.update(_localhosts_aggressive())
    return _LOCALHOSTS

def _set_local(host, local):
    global _LOCALHOSTS
    _localhosts()
    _LOCALHOSTS[host] = local
    return local

def localhost(host):
    """
    Returns True if host is localhost, False otherwise.

    This recognizes constant names as well as attempts to resolve the name.
    """
    if not host or localhost_(host) or TEST_LOOP(host):
        return True
    if test_loop(host):
        return False
    localhosts = _localhosts()
    is_local = localhosts.get(host, None)
    if is_local is not None:
        return is_local
    try:
        hfqdn, haliaslist, hipaddrs = socket.gethostbyname_ex(host)
        for name in [hfqdn] + haliaslist + hipaddrs:
            if name in localhosts:
                return _set_local(host, True)
    except:
        pass
    try:
        hfqdn, haliaslist, hipaddrs = socket.gethostbyaddr(host)
        for name in [hfqdn] + haliaslist + hipaddrs:
            if name in localhosts:
                return _set_local(host, True)
    except:
        pass
    return _set_local(host, False)

if sys.version_info[1] < 4:
    def format_exc():
        """Compatibility wrapper - in python 2.3 can not use traceback.format_exc()."""
        return traceback.format_exception(sys.exc_type, sys.exc_value,
                sys.exc_traceback)
else:
    format_exc = traceback.format_exc

if sys.version_info[1] < 4:
    def dict_update(d, *args, **kwargs):
        """Compatibility wrapper - in python 2.3 dict.update does not accept keyword arguments."""
        return d.update(dict(*args, **kwargs))
else:
    dict_update = dict.update

def log_flush(logger):
    for h in logger.handlers:
        try:
            h.flush()
        except:
            pass


def parse_bool(arg):
    """Permissive string into bool parser."""
    if arg in [True, False, None]:
        return arg
    if str(arg).strip().lower() in ['', '0', 'false']:
        return False
    return arg


class ConsoleHandler(logging.Handler):

    def __init__(self):
        logging.Handler.__init__(self)
        self.console = None

    def reopen(self):
        self.console = open('/dev/console', 'wb')

    def emit(self, record):
        try:
            msg = self.format(record)
            if isinstance(msg, unicode):
                msg.encode('utf8')
            try:
                if self.console is None:
                    self.reopen()
                self.console.write(msg + '\n')
                self.console.flush()
            except (OSError, IOError):
                self.reopen()
                self.console.write(msg + '\n')
                self.console.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

def make_log_handler(log, log_path, log_file_name=None, syslog=None,
        console=None):

    # FIXME: add config.option?
    if sys.version_info[0] == 2 and sys.version_info[1] <= 4:
        fmt = ': %(levelname)s %(message)s'
    else:
        fmt = ' %(funcName)s: %(levelname)s %(message)s'

    if syslog:
        lhandler = logging.handlers.SysLogHandler()
        lhandler.setFormatter(logging.Formatter('%(asctime)s %(name)s'+fmt))
        lhandler.setLevel(logging.WARNING)
        log.addHandler(lhandler)

    console = parse_bool(console)
    if console:
        if str(console).strip().lower() == 'console':
            lhandler = ConsoleHandler()
            lhandler.setLevel(logging.INFO)
        else:
            lhandler = logging.StreamHandler()
        lhandler.setFormatter(logging.Formatter('%(asctime)s %(name)s'+fmt))
        log.addHandler(lhandler)

    if log_file_name:
        if not os.path.isabs(log_file_name):
            log_file_name = os.path.join(log_path, log_file_name)
        # FIXME: should attempt to create a temp file if the following fails:
        pre_open(log_file_name)
        lhandler = logging.FileHandler(log_file_name)
        lhandler.setFormatter(logging.Formatter('%(asctime)s'+fmt))
        log.addHandler(lhandler)

def is_class_verbose(cls):
    if not inspect.isclass(cls):
        cls = cls.__class__
    if 'is_class_verbose' in dir(cls):
        return cls.is_class_verbose()
    return '_class_is_verbose' in dir(cls) and cls._class_is_verbose


def make_methods_verbose(cls, print_on_call, method_list):
    for id in method_list:
        if isinstance(id, (tuple, list)):
            if id[1] == classmethod:
                # FIXME: Have a look at following! It sort-of works, but I
                # am not sure it is correct.
                #setattr(cls, id[0], staticmethod(print_on_call(getattr(cls, id[0]))))
                print >> sys.stderr, "ERROR: at the moment classmethod can not be reliably made verbose."
                continue
            else:
                meth = getattr(cls, id[0])
                new_meth = print_on_call(meth)
                new_meth.original_method = meth
                new_meth = id[1](new_meth)
                setattr(cls, id[0], new_meth)
        else:
            meth = getattr(cls, id)
            new_meth = print_on_call(meth)
            new_meth.original_method = meth
            setattr(cls, id, new_meth)


def make_class_verbose(cls, print_on_call):
    if not inspect.isclass(cls):
        cls = cls.__class__
    if hasattr(cls, 'make_class_verbose'):
        cls.make_class_verbose(print_on_call)
        return
    if hasattr(cls, '_VERBOSE'):
        if getattr(cls, '_class_is_verbose', False):
            return
        cls._class_is_verbose = True
        make_methods_verbose(cls, print_on_call, cls._VERBOSE)
    for c in getattr(cls, '__bases__', ()):
        try:
            make_class_verbose(c, print_on_call)
        except:
            print >> sys.stderr, "ERROR: can not make %s verbose." % (c,)
    if hasattr(cls, '_VERBOSE_CLASSES'):
        for cls_ in cls._VERBOSE_CLASSES:
            make_class_verbose(cls_, print_on_call)


# Auxiliary functions for testing:
def assert_(result, *expecteds, **kwargs):
    compare = kwargs.get('compare', lambda x, y: x == y)
    for expected in expecteds:
        if compare(result, expected):
            return result
    else:
        print >> sys.stderr, "ERROR: got %r\n\texpected: %r" % (result, expecteds)
        assert result == expected

def prints(obj):
    print "%s" % obj
    return obj

def printr(obj):
    print "%r" % obj
    return obj

def assertp(result, *expecteds):
    print "OK: %r" % assert_(result, *expecteds)
    return result

def str2log_level(s, default=logging.WARNING):
    return dict(debug=logging.DEBUG, info=logging.INFO, warning=logging.WARNING,
            warn=logging.WARNING, error=logging.ERROR, fatal=logging.FATAL,
            critical=logging.CRITICAL, false=logging.ERROR, true=logging.INFO) \
                    .get(s.lower(), default)

def pre_open(name):
    if not os.path.isfile(name):
        ensuredir(os.path.dirname(name))

def ensuredir(path):
    if not path:
        # path component empty - using working directory.
        return
    if not os.path.isdir(path):
        try:
            os.makedirs(path)
        except exceptions.OSError:
            # the directory was created in the meantime.
            if not os.path.isdir(path):
                raise
    # check permissions
    if not os.access(path, os.X_OK | os.W_OK):
        raise exceptions.OSError("Directory '%s' not writable." % path)

TIME_RE = re.compile('^([0-9]+)([dhms]?)$')
TIME_UNITS = {'d':24*3600, 'h':3600, 'm':60, 's':1, '':1}
def canonical_time(time):
    amount, units = TIME_RE.match(time.lower()).group(1, 2)
    return int(amount)*TIME_UNITS[units]
