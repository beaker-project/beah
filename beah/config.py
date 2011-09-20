# -*- test-case-name: beah.test.test_config -*-

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


"""
Read configuration for beah.

Functions:
    beah_conf
        - create controller configuration
    backend_conf
        - create backend configuration
    get_conf
        - find ConfigParser instance with given id

Auxiliary:
    _Config
        - common configuration behavior
    _BeahConfig
        - beah specific behavior
    _ConfigParserFix
        - fixed ConfigParser
    _get_config
        - find _Config instance with given id

Basic Usage:
    # Import:
    from beah import config

    # Read and set:
    beah_conf = config.beah_conf(beah_overrides)
    beaker_backend_conf = config.backend_conf('beaker-backend',
        'BEAKER_BACKEND_CONF', 'beaker_backend.conf', beaker_defaults,
        beaker_overrides)
    beaker_backend_conf.conf.set('CONTROLLER', 'LOG', 'True')

    # Use:
    beaker_backend_conf = config.get_config('beaker-backend')
    if beaker_backend_conf.conf.get('CONTROLLER', 'LOG'):
        pass

"""


import sys
import os
import os.path
import re
import exceptions
import random
from ConfigParser import ConfigParser
from optparse import OptionParser
from beah.misc import dict_update


class _ConfigParserFix(ConfigParser):
    """
    Class overriding ConfigParser to workaround a bug in Python 2.3.

    The problem is that optionxform is not applied consistently to keys.

    Using str.upper for optionxform, as uppercase keys are used in beah.

    """
    def __init__(self, defaults=None, optionxformf=str.upper):
        self.optionxform = optionxformf
        defs = {}
        if defaults:
            for key, value in defaults.items():
                defs[self.optionxform(key)] = value
        ConfigParser.__init__(self, defs)


class NoConfFile(Exception):
    """Exception raised when none of listed config files can be found."""
    pass


class ConfigurationExists(Exception):
    """Exception raised when configuration with given id already exists."""
    pass


class _Config(object):

    _VERBOSE = ('_get_conf_file', '_conf_files', '_conf_runtime', 'read_conf',
            ('parse_conf_name', staticmethod), ('get_config', staticmethod),
            ('has_config', staticmethod))

    _CONF_ID = '[a-zA-Z_][a-zA-Z_0-9]*'
    _CONF_NAME_RE = re.compile('^(?:('+_CONF_ID+')\.)?('+_CONF_ID+')$')

    _configs = {}

    def __init__(self, id, conf_env_var, conf_filename, defaults, opts):
        """
        Configuration builder.

        This object takes multiple sources of configuration options and builds a
        single configuration dictionary - the conf instance variable.

        This also keeps track of active configurations and prevents two
        configurations with same id.

        Arguments:
        id -- configuration id used to obtain active configuration.
        conf_env_var -- name of environment variable containing configuration file name
        conf_filename -- configuration file's basename
        defaults -- dictionary with default values.
        opts -- dictionary containing parsed command line options (and
                environment variables)

        defaults' and opts' keys are in the form NAME or SECTION.NAME

        """
        if self._configs.has_key(id):
            raise ConfigurationExists('Configuration %r already defined.' % id)
        self.id = id
        self.conf_env_var = conf_env_var
        self.conf_filename = conf_filename
        self.defaults = defaults
        self.opts = opts
        self.conf = None
        self.read_conf()
        if id:
            self._configs[id] = self

    def _remove(id):
        """Remove configuration instance with given id."""
        del _Config._configs[id]
    _remove = staticmethod(_remove)

    def print_conf(conf, raw=False, defaults=None, show_defaults=False):
        """
        Print a configuration.

        This does not show values which are same as default ones.

        Arguments:
        conf -- ConfigParser object
        raw -- print raw values when True. Otherwise print interpolated values
               with %(NAME)s values expanded.
        defaults -- default values
        show_defaults -- when true show defaults.

        """
        if defaults is None:
            defaults = {}
        if show_defaults and defaults:
            print "defaults=dict("
            for key, value in defaults.items():
                print "%s=%r" % (key, value)
            print ")\n"
        defs = conf.items('DEFAULT', raw=raw)
        print "[DEFAULT]"
        for key, value in defs:
            if defaults.has_key(key) and defaults[key] == value:
                continue
            tmpkey = "DEFAULT.%s" % key
            if defaults.has_key(tmpkey) and defaults[tmpkey] == value:
                continue
            print "%s=%r" % (key, value)
        print ""
        defs = dict(defs)
        for section in conf.sections():
            if section == 'DEFAULT':
                continue
            print "[%s]" % section
            for key, value in conf.items(section, raw=raw):
                if defs.has_key(key) and defs[key] == value:
                    continue
                tmpkey = "%s.%s" % (section, key)
                if defaults.has_key(tmpkey) and defaults[tmpkey] == value:
                    continue
                print "%s=%r" % (key, value)
            print ""
    print_conf = staticmethod(print_conf)

    def print_(self, raw=False, defaults_display='include'):
        """
        Print.

        Arguments:
        - raw -- see print_conf
        - defaults_display -- whether to display defaults and how to display
                              them. Permitted values:
          - include -- display defaults like any other values inline in
                       appropriate section
          - exclude -- do not show values same as their default
          - show, extra -- display default values separately

        """
        print "\n=== %s ===" % self.id
        if defaults_display:
            defaults_display = defaults_display.lower()
        if not defaults_display or defaults_display == 'include':
            defs = {}
            show_defaults = False
        elif defaults_display == 'exclude':
            defs = self.defaults
            show_defaults = False
        elif defaults_display in ('show', 'extra'):
            defs = self.defaults
            show_defaults = True
        else:
            raise exceptions.NotImplementedError('print_ does not know how to handle %s' % (defaults_display,))
        self.print_conf(self.conf, raw=raw, defaults=defs,
                show_defaults=show_defaults)

    def _conf_opt(self):
        """Access value of command line option for passing config.file."""
        return self.opts.get(self.conf_env_var, '')

    def upd_conf(conf, dict_, warn_section=False):
        """Update conf with [SECTION.]NAME pairs found in dict_."""
        for (sec_name, value) in dict_.items():
            sec_name_pair = _Config.parse_conf_name(sec_name)
            if not sec_name_pair:
                print >> sys.stderr, "--- WARNING: Can not parse %r." % sec_name
                continue
            section, name = sec_name_pair
            if not isinstance(value, basestring):
                print >> sys.stderr, "--- WARNING: Value for %s.%s (%r) is not an string." % (section, name, value)
                continue
            if section and section != 'DEFAULT' and not conf.has_section(section):
                if warn_section:
                    print >> sys.stderr, "--- WARNING: Section %r does not exist." % section
                conf.add_section(section)
            conf.set(section, name, value)
    upd_conf = staticmethod(upd_conf)

    def read_conf(self):
        """
        Update configuration from available sources.

        This includes rereading configuration files.

        """
        conf = _ConfigParserFix()
        self.upd_conf(conf, self.defaults, warn_section=False)
        fn = self._get_conf_file(self._conf_opt())
        if not fn:
            if self.conf_filename:
                print >> sys.stderr, "--- WARNING: Could not find conf.file."
        else:
            try:
                conf.read(fn)
            except:
                print >> sys.stderr, "--- ERROR: Could not read %r." % fn
                raise
        self.upd_conf(conf, self.opts, warn_section=True)
        self.conf = conf

    def parse_conf_name(name):
        """Parse configuration name in form [SECTION.]NAME."""
        if isinstance(name, (tuple, list)):
            if len(name) == 1:
                return ('DEFAULT', name[0])
            if len(name) == 2:
                return (name[0], name[1])
            raise exceptions.RuntimeError('tuple %r should have one or two items.' % name)
        if isinstance(name, basestring):
            match = _Config._CONF_NAME_RE.match(name)
            if not match:
                return None
            return (match.group(1) or 'DEFAULT', match.group(2))
    parse_conf_name = staticmethod(parse_conf_name)

    def _check_conf_file(self, filename):
        """Check the existence of configuration file."""
        if filename and os.path.isfile(filename):
            return filename
        return None

    def _conf_runtime(self, opt=None):
        """Make a list of conf.files coming from options and environment."""
        return [opt, os.environ.get(self.conf_env_var, None)]

    def _conf_files(self):
        """Make a list of conf.files."""
        conf_list = []
        if self.conf_filename:
            if os.environ.has_key('HOME'):
                conf_list.append(os.environ.get('HOME')+'/.'+self.conf_filename)
            if sys.prefix not in ['', '/', '/usr']:
                conf_list.append(sys.prefix + '/etc/'+self.conf_filename)
            conf_list.append('/etc/'+self.conf_filename)
        return conf_list

    def _get_conf_file(self, opt=None):
        """Find a configuration file or raise an exception."""
        conf_list = self._conf_runtime(opt) + self._conf_files()
        no_file = True
        for conf_file in conf_list:
            if conf_file:
                no_file = False
                if self._check_conf_file(conf_file):
                    return conf_file
        if no_file:
            return ''
        raise NoConfFile("Could not find configuration file.")

    def has_config(id):
        """Check whether an instance with given id exists."""
        return _Config._configs.get(id, None)
    has_config = staticmethod(has_config)

    def get_config(id):
        """Find an instance with given id."""
        return _Config._configs[id]
    get_config = staticmethod(get_config)


class _BeahConfig(_Config):

    """
    beah specific extension of _Config class.

    This overrides lookup paths for configuration files and provides methods
    for building _Config instances (beah_conf and backend_conf).

    """

    _VERBOSE = ('_conf_files', '_get_conf_file', ('beah_conf', staticmethod),
            ('backend_conf', staticmethod))

    def _conf_files(self):
        conf_list = []
        if self.conf_filename and os.environ.has_key('BEAH_ROOT'):
            # used in devel.environment only:
            conf_list = [os.environ.get('BEAH_ROOT')+'/'+self.conf_filename,
                    os.environ.get('BEAH_ROOT')+'/etc/'+self.conf_filename]
        return conf_list + _Config._conf_files(self)

    def _get_conf_file(self, opt=None):
        try:
            return _Config._get_conf_file(self, opt=opt)
        except NoConfFile:
            return ''

    def beah_conf(opts, id='beah'):
        """
        Build a _BeahConfig object for beah-server.

        Arguments:
        opts -- parsed command line options
        """
        return _BeahConfig(id, 'BEAH_CONF', 'beah.conf', beah_defaults(), opts)
    beah_conf = staticmethod(beah_conf)

    def backend_conf(id, conf_env_var, conf_filename, defaults, opts):
        """
        Build a _BeahConfig object for backends.

        This will look-up BACKEND section in beah-server configuration file to
        override defaults.

        """
        conf2 = {'BEAH_CONF': opts.get('BEAH_CONF', '')}
        conf = _BeahConfig.beah_conf(conf2, id=None).conf
        defs = dict(conf.items('BACKEND', raw=True))
        dict_update(defs, defaults)
        return _BeahConfig(id, conf_env_var, conf_filename, defs, opts)
    backend_conf = staticmethod(backend_conf)


def get_conf(id):
    """Get ConfigParser object by id."""
    return _Config.get_config(id).conf


def defaults():
    """Default common configuration options."""
    return dict(
            LOG='Warning',
            ROOT='',
            VAR_ROOT='%(ROOT)s/var/beah',
            LOG_PATH='%(ROOT)s/var/log',
            DEVEL='False',
            CONSOLE_LOG='False',
            NAME='beah-default-%2.2d' % random.randint(0,99),
            RUNTIME_FILE_NAME='%(VAR_ROOT)s/%(NAME)s.runtime',
            )


def beah_defaults():
    """Default configuration options specific for controller."""
    d = defaults()
    d.update({
            'CONTROLLER.NAME':'beah',
            'CONTROLLER.LOG_FILE_NAME':'%(LOG_PATH)s/%(NAME)s.log',
            'BACKEND.INTERFACE':'',
            'BACKEND.PORT':'12432',
            'BACKEND.PORT_OPT':'False',
            'TASK.INTERFACE':'127.0.0.1',
            'TASK.PORT':'12434'})
    if os.name == 'posix':
        # using PORT as ID, not NAME. NAME could (and should) be different for
        # each backend as well as for the controller.
        d['BACKEND.SOCKET'] = '%(VAR_ROOT)s/backend%(PORT)s.socket'
        d['BACKEND.SOCKET_OPT'] = 'False'
        d['TASK.SOCKET'] = '%(VAR_ROOT)s/task%(PORT)s.socket'
    return d


def backend_defaults():
    """Default configuration options specific for backend."""
    return {}


def beah_conf(overrides=None, args=None):
    """
    Main beah-server configuration routine.

    This parses command line options, environment, configuration file and
    default options with decreasing priority in that order and returns a single
    _BeahConfig object.

    Configuration file's location may be affected by command line options or
    environment.

    Arguments:
    overrides - parsed configuration dictionary. This overrides args.
    args - list of command line arguments. sys.argv will be used when None.

    """
    if overrides is None:
        overrides = beah_opts(args)
    return _BeahConfig.beah_conf(overrides)


def backend_conf(env_var=None, filename=None, defaults=None, overrides=None):
    """
    Main backend configuration routine.

    This requires command line options to be already parsed and passed in in
    overrides dictionary.

    This parses overrides, environment, configuration file and default options
    with decreasing priority in that order and returns a single _BeahConfig
    object.

    Configuration file's location may be affected by overrides or environment.

    Arguments:
    env_var -- name of environment variable containing configuration file name
    filename -- configuration file's basename
    defaults -- defaults
    overrides - parsed configuration dictionary

    """
    return _BeahConfig.backend_conf('beah-backend', env_var, filename,
            defaults or {}, overrides or {})


def _get_config(id):
    return _Config.get_config(id)


def proc_verbosity(opts, conf):
    """Process verbose/quiet options and set appropriate log level."""
    if opts.verbose is not None or opts.quiet is not None:
        verbosity = int(opts.verbose or 0) - int(opts.quiet or 0)
    else:
        return
    if verbosity >= 3:
        conf['DEVEL'] = 'True'
    if not conf.has_key('LOG'):
        level = 'error'
        if verbosity > 2:
            level = 'debug'
        else:
            level = ('warning', 'info', 'debug')[verbosity]
        conf['LOG'] = level


def beah_opts_aux(opt, conf, args=None):
    """
    Parse positional arguments using option parser opt into conf.

    This handles additional options (verbosity) and BEAH_DEVEL env.variable.

    Arguments:
    opt -- OptionParser
    conf -- dictionary holding parsed data
    args -- list holding positional arguments. Use sys.argv when None.

    """
    if args is None:
        args = sys.argv[1:]
    # Process environment:
    if os.environ.has_key('BEAH_DEVEL'):
        conf['DEVEL'] = os.environ.get('BEAH_DEVEL', 'False')
    # Process command line options:
    opts, rest = opt.parse_args(args)
    proc_verbosity(opts, conf)
    return conf, rest


def beah_opts(args=None):
    """Create a parser and parse options for beah-server."""
    conf = {}
    opt = beah_opt(OptionParser(), conf)
    conf, rest = beah_opts_aux(opt, conf, args=args)
    if rest:
        opt.print_help()
        raise exceptions.RuntimeError('Program accepts no positional arguments.')
    return conf


def backend_opt_ex(conf=None, option_adder=None):
    """
    Build option parser for backend.

    Arguments:
    conf -- dictionary holding parsed data
    option_adder -- additional OptionParser extender

    """
    if conf is None:
        conf = {}
    opt = backend_opt(OptionParser(), conf)
    if option_adder is not None:
        opt = option_adder(opt, conf)
    return conf, opt

def backend_opts_ex(args=None, option_adder=None):
    """
    Parse options and positional arguments for backend.

    Arguments:
    option_adder -- additional OptionParser extender

    """
    conf, opt = backend_opt_ex(option_adder=option_adder)
    conf, rest = beah_opts_aux(opt, conf, args=args)
    return conf, rest


def backend_opts(args=None, option_adder=None):
    """
    Parse options for backend.

    Use backend_opts_ex for backends accepting positional arguments.

    Arguments:
    option_adder -- additional OptionParser extender

    """
    conf, opt = backend_opt_ex(option_adder=option_adder)
    conf, rest = beah_opts_aux(opt, conf, args=args)
    if rest:
        opt.print_help()
        raise exceptions.RuntimeError('Program accepts no positional arguments.')
    return conf


def default_opt(opt, conf, kwargs):
    """
    Extend option parser opt to handle common options.

    Arguments:
    opt -- OptionParser
    conf -- dictionary holding parsed data

    Keyword Arguments:
    type -- type of configuration to update (one of 'beah', 'backend' or 'task').
            This affects which keys get set by the parser.

    """
    opt.disable_interspersed_args()
    def config_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['BEAH_CONF'] = value
    opt.add_option("-c", "--config",
            action="callback", callback=config_cb, type='string',
            help="Use FILE for configuration.", metavar="FILE")
    def name_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        if kwargs['type'] == 'beah':
            conf['CONTROLLER.NAME'] = value
        else:
            conf['NAME'] = value
    opt.add_option("-n", "--name",
            action="callback", callback=name_cb, type='string',
            help="Use NAME as identification.")
    opt.add_option("-v", "--verbose", action="count",
            help="Increase verbosity.")
    opt.add_option("-q", "--quiet", action="count",
            help="Decrease verbosity.")
    def log_stderr_cb(option, opt_str, value, parser, arg):
        conf['CONSOLE_LOG'] = arg
    opt.add_option("--log-console", action="callback",
            callback=log_stderr_cb, callback_args=("console",),
            help="Write all logging to /dev/console.")
    opt.add_option("-O", "--log-stderr", action="callback",
            callback=log_stderr_cb, callback_args=("True",),
            help="Write all logging to stderr.")
    opt.add_option("--no-log-stderr", action="callback",
            callback=log_stderr_cb, callback_args=("False",),
            help="Do not write logging info to stderr.")
    def log_level_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['LOG'] = value
    opt.add_option("-L", "--log-level",
            action="callback", callback=log_level_cb, type='string',
            help="Specify log level explicitly.")
    return opt


def beah_be_opt(opt, conf, kwargs):
    """
    Extend option parser opt to handle common backend-related options.

    Arguments:
    opt -- OptionParser
    conf -- dictionary holding parsed data

    Keyword Arguments:
    type -- type of configuration to update (one of 'beah' or 'backend').
            This affects which keys get set by the parser.

    """
    def interface_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        if kwargs['type'] == 'beah':
            conf['BACKEND.INTERFACE'] = value
        else:
            conf['INTERFACE'] = value
    opt.add_option("-i", "--interface", action="callback",
            callback=interface_cb, type='string',
            help="interface backends are connecting to.")
    def port_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        if kwargs['type'] == 'beah':
            conf['BACKEND.PORT'] = value
            conf['BACKEND.PORT_OPT'] = 'True'
        else:
            conf['PORT'] = value
            conf['PORT_OPT'] = 'True'
    opt.add_option("-p", "--port", action="callback", callback=port_cb,
            type='string',
            help="port number backends are using.")
    if os.name == 'posix':
        def socket_cb(option, opt_str, value, parser):
            # FIXME!!! check value
            if kwargs['type'] == 'beah':
                conf['BACKEND.SOCKET'] = value
                conf['BACKEND.SOCKET_OPT'] = 'True'
            else:
                conf['SOCKET'] = value
                conf['SOCKET_OPT'] = 'True'
        opt.add_option("-s", "--socket", action="callback", callback=socket_cb,
                type='string',
                help="socket for backends.")
    return opt


def beah_t_opt(opt, conf, kwargs):
    """
    Extend option parser opt to handle common task-related options

    Arguments:
    opt -- OptionParser
    conf -- dictionary holding parsed data

    Keyword Arguments:
    type -- type of configuration to update (one of 'beah' or 'task').
            This affects which keys get set by the parser.

    """
    def interface_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        if kwargs['type'] == 'beah':
            conf['TASK.INTERFACE'] = value
        else:
            conf['INTERFACE'] = value
    opt.add_option("-I", "--task-interface", action="callback",
            callback=interface_cb, type='string',
            help="interface tasks are connecting to.")
    def port_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        if kwargs['type'] == 'beah':
            conf['TASK.PORT'] = value
        else:
            conf['PORT'] = value
    opt.add_option("-P", "--task-port", action="callback", callback=port_cb,
            type='string',
            help="port number tasks are using.")
    if os.name == 'posix':
        def socket_cb(option, opt_str, value, parser):
            # FIXME!!! check value
            if kwargs['type'] == 'beah':
                conf['TASK.SOCKET'] = value
            else:
                conf['SOCKET'] = value
        opt.add_option("-S", "--task-socket", action="callback", callback=socket_cb,
                type='string',
                help="socket for tasks.")
    return opt


def beah_opt(opt, conf, kwargs=None):
    """
    Extend option parser opt to handle beah-server options.

    Arguments:
    opt -- OptionParser
    conf -- dictionary holding parsed data

    """
    kwargs = dict(kwargs or {})
    kwargs['type'] = 'beah'
    default_opt(opt, conf, kwargs)
    beah_be_opt(opt, conf, kwargs)
    beah_t_opt(opt, conf, kwargs)
    return opt


def backend_opt(opt, conf, kwargs=None):
    """
    Extend option parser opt to handle backend options.

    Arguments:
    opt -- OptionParser
    conf -- dictionary holding parsed data

    """
    kwargs = dict(kwargs or {})
    kwargs['type'] = 'backend'
    default_opt(opt, conf, kwargs)
    beah_be_opt(opt, conf, kwargs)
    def backend_conf_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['BACKEND_CONF'] = value
    opt.add_option("-C", "--backend-config", action="callback",
            callback=backend_conf_cb, type='string',
            help="Use BACKEND_CONFIG for configuration.")
    return opt

