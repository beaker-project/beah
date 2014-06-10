# -*- test-case-name: beah.backends.test.test_beakerlc -*-

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
Backend translating beah events to XML-RPCs understood by beaker's Lab
Controller.

Classes:
    BeakerLCBackend -- the main class
    RecipeParser, TaskParser -- parsers classes
    BeakerRecipe, BeakerTask, BeakerResult, BeakerFile
        -- classes used to process events
Auxiliary classes:
    Container -- class used for caching objects
    PersistentBeakerContainer -- container with memory
    Item, PersistentItem -- building blocks
    BeakerObject -- baseclass for Beaker* classes
    PersistentBeakerObject -- baseclass with memory

See BeakerLCBackend.proc_evt and BeakerLCBackend.proc_evt_* methods.
Dispatching according to event type is performed by superclass
(BasicBackend.proc_evt)
"""

# Beaker Backend should invoke these XML-RPC:
#  1. recipes.to_xml(recipe_id)
#     recipes.system_xml(fqdn)
#  2. parse XML
#  3. recipes.tasks.Start(task_id, kill_time)
#  *. recipes.tasks.Result(task_id, result_type, path, score, summary)
#     - result_type: pass_|warn|fail|panic
#  4. recipes.tasks.Stop(task_id, stop_type, msg)
#     - stop_type: stop|abort|cancel

import sys
import os
import os.path
import re
import traceback
import exceptions
import base64
from beah.misc.jsonenv import json
import logging
from xml.dom import minidom
import socket
import time
try:
    set
except NameError: # Python 2.3
    from sets import Set as set

from twisted.internet import reactor, defer
from twisted.internet.task import LoopingCall
from twisted.python import failure
from twisted.web import xmlrpc
from beah import config
from beah.core import command, event, addict, new_id
from beah.core.backends import SerializingBackend
from beah.core.constants import ECHO, RC, LOG_LEVEL
from beah.misc import format_exc, dict_update, log_flush, writers, runtimes, \
        make_class_verbose, is_class_verbose, pre_open, digests, parse_bool
from beah.misc.log_this import log_this
import beah.system
# FIXME: using rpm's, yum - too much Fedora centric(?)
from beah.system.dist_fedora import RPMInstaller
from beah.system.os_linux import ShExecutable
from beah.wires.internals import repeatingproxy
from beah.wires.internals.twbackend import start_backend, log_handler
from beah.wires.internals.twmisc import make_logging_proxy

import twisted
twisted_version = (twisted.version.major, twisted.version.minor)

log = logging.getLogger('backend')

################################################################################
# Scheduling:
################################################################################


class RHTSTask(ShExecutable):

    def __init__(self, env_, repos, repof):
        self.__env = env_
        self.__repos = repos
        self.__repof = repof
        ShExecutable.__init__(self)

    def content(self): # pylint: disable=E0202
        self.write_line("""
# read environment:
if [[ -f /etc/profile.d/task-defaults-rhts.sh ]]; then
    __TEMP_ENV=$(mktemp)
    # save the current environment:
    export > $__TEMP_ENV
    # load defaults:
    source /etc/profile.d/task-defaults-rhts.sh
    # restore saved env:
    source $__TEMP_ENV
    rm -f $__TEMP_ENV
fi
# This wrapper should prevent rhts-test-runner.sh to install rpm from default
# rhts repository and use repositories defined in recipe
#mkdir -p $TESTPATH
if [[ -n "$BEAH_MAKE_REPOS" ]]; then
cat >/etc/yum.repos.d/beaker-tests.repo <<REPO_END
%s
REPO_END
fi
check_test() {
    rpm -q "$TESTRPMNAME" || [[ -f "$TESTPATH/Makefile" ]]
}
_install_test() {
    beahsh extend_watchdog 20m
    yum -y --enablerepo=beaker-* install "$TESTRPMNAME"
}
if check_test; then
    beahsh INFO -H wrapper "$TESTRPMNAME is already installed."
else
    # This will happen only on first run so it is safe to override
    # watchdog as it will be reset by task...
    beahsh INFO -H wrapper "Installing the task $TESTRPMNAME"
    _install_test
    # If task repo is broken the retry is mostly likely a waste of time, but
    # let's try it at least once anyway.
    for iteration in 1; do
        if ! check_test; then
            beahsh INFO -H wrapper "$TESTRPMNAME not installed. Will retry in 60s..."
            sleep 60
            beahsh INFO -H wrapper "Cleaning metadata and trying to get the task again..."
            yum -y clean metadata
            _install_test
        else
            break
        fi
    done
    if ! check_test; then
        #beahsh fail -H wrapper "$TESTRPMNAME was not installed."
        beahsh abort_task -m "$TESTRPMNAME was not installed."
        exit
    fi
fi
# This is a workaround for /distribution/reservesys test:
touch /mnt/tests/runtests.sh
chmod a+x /mnt/tests/runtests.sh
beahsh INFO -H wrapper "Running the task..."
exec env PATH="$PATH:/sbin" beah-rhts-task
""" % (self.__repof,))


def mk_rhts_task(env_, repos, repof):
    # FIXME: proper RHTS launcher shold go here.
    # create a script to: check, install and run a test
    # should task have an "envelope" - e.g. binary to run...
    e = RHTSTask(env_, repos, repof)
    e.make()
    return e.executable

def normalize_rpm_name(rpm_name):
    if rpm_name[-4:] != '.rpm':
        return rpm_name
    return rpm_name[:-4]

def xml_attr(node, key, default=None):
    try:
        return str(node.attributes[key].value)
    except:
        return default

def xml_get_nodes(node, tag):
    if not node:
        return []
    return [n for n in node.childNodes if n.nodeName == tag]

def xml_first_node(node, tag):
    for n in node.childNodes:
        if n.nodeName == tag:
            return n
    return None


def find_recipe(node, recipe_id):
    for er in node.getElementsByTagName('recipe'):
        if xml_attr(er, 'id') == str(recipe_id):
            return er
    for er in node.getElementsByTagName('guestrecipe'):
        if xml_attr(er, 'id') == str(recipe_id):
            return er
    return None


class RecipeException(Exception):
    pass


class RecipeParser(object):

    def make(input_xml, recipe_id):
        """
        Takes an input XML string and creates recipe for given recipe ID.
        """
        root = minidom.parseString(input_xml)
        submitter = None
        for job in root.getElementsByTagName('job'):
            submitter = xml_attr(job, 'owner')
            break
        recipe = find_recipe(root, recipe_id)
        if not recipe:
            return None
        return RecipeParser(recipe, submitter=submitter)
    make = staticmethod(make)

    GUEST_ATTRS = ('system', 'mac_address', 'location', 'guestargs', 'guestname')
    RECIPE_TYPE = {'recipe': 'machine', 'guestrecipe': 'guest'}
    REPOF_TEMPLATE = """
[%s]
name=beaker provided '%s' repo
baseurl=%s
enabled=1
gpgcheck=0

"""

    def __init__(self, recipe_node, submitter=None):

        recipe_type = self.RECIPE_TYPE.get(recipe_node.tagName, None)
        if not recipe_type:
            raise RecipeException("Unknown Tag %s" % recipe_node.tagName)
        self.recipe_node = recipe_node
        variant = xml_attr(recipe_node, 'variant', '')
        if not variant or variant == 'None':
            variant = ''
        if not submitter:
            submitter = ''
        self.beaker_id = xml_attr(recipe_node, 'id')
        self._env = {
                'ARCH': xml_attr(recipe_node, 'arch'),
                'RECIPEID': self.beaker_id,
                'JOBID': xml_attr(recipe_node, 'job_id'),
                'RECIPESETID': xml_attr(recipe_node, 'recipe_set_id'),
                'DISTRO': xml_attr(recipe_node, 'distro', ''),
                'FAMILY': xml_attr(recipe_node, 'family', ''),
                'VARIANT': variant,
                # XXX 'HOSTNAME': hostname,
                'RECIPETYPE': recipe_type,
                'SUBMITTER': submitter,
                }

        if recipe_type == 'guest':
            machine_recipe_node = recipe_node.parentNode
            self._env['HYPERVISOR_HOSTNAME'] = xml_attr(machine_recipe_node, 'system')

        # The following is necessary for Virtual Workflows:
        self._env['GUESTS'] = '|'.join([
            ';'.join([xml_attr(gr, a, '') for a in self.GUEST_ATTRS])
                for gr in xml_get_nodes(recipe_node, 'guestrecipe')])

        # FIXME: This will eventually need to be replaced by sth RPM independent...
        self.repos = []
        self.repof = ''
        for r in xml_get_nodes(xml_first_node(recipe_node, 'repos'), 'repo'):
            name = xml_attr(r, 'name')
            self.repos.append(name)
            self.repof += self.REPOF_TEMPLATE % (name, name, xml_attr(r, 'url'))
        self._env['BEAKER_REPOS']=':'.join(self.repos)

        self._env['RECIPE_ROLE'] = xml_attr(recipe_node, 'role', '')

    def tasks(self, collect_env=False):
        test_order = 1 # internal counter - if prev_task does not have one
        collected = {}
        for task_node in xml_get_nodes(self.recipe_node, 'task'):
            task = TaskParser(task_node, self, test_order)
            task.collected = dict(collected)
            yield task
            collected.update(task.get_params())
            test_order = task.test_order + 1

    def next_task(self, prev_task=None, collect_env=False):
        found = not prev_task # if no prev.task - first will match
        matcher = TaskParser.matcher(prev_task)
        for task in self.tasks(collect_env=collect_env):
            if found:
                yield task
            else:
                found = matcher(task.task_node)
        if not found:
            raise LookupError('Could not find original task %s' % prev_task)

    def find_task(self, task_spec, collect_env=False):
        matcher = TaskParser.matcher(task_spec)
        for task in self.tasks(collect_env=collect_env):
            if matcher(task.task_node):
                yield task


class RpmTaskParser(object):

    def __init__(self, rpm_node, task, task_name):
        rpm_name = xml_attr(rpm_node, 'name')
        test_path = xml_attr(rpm_node, "path") or "/mnt/tests"+task_name
        self.task = task
        dict_update(task._env,
                TEST=task_name,
                TESTRPMNAME=normalize_rpm_name(rpm_name),
                TESTPATH=test_path)
        task.executable = mk_rhts_task(task._env, task.recipe.repos, task.recipe.repof)
        task.args = [rpm_name]
        log.info("RPMTest %s - %s %s", rpm_name, task.executable, task.args)


def normalize_executable(executable, args):
    proto_len = executable.find(':')
    if proto_len >= 0:
        proto = executable[:proto_len]
        if proto == "file" and executable[proto_len+1:proto_len+3] == '//':
            executable = executable[proto_len+3:]
        else:
            # FIXME: retrieve a file and set an executable bit.
            log.warning("Feature not implemented yet. proto=%s",
                    proto)
            return ""
    else:
        executable = os.path.abspath(executable)
    return (executable, args)


class ExecutableTaskParser(object):

    def __init__(self, executable_node, task):
        self.task = task
        if task.recipe.repof:
            f = open('/etc/yum.repos.d/beaker-tests.repo', 'w+')
            f.write(task.recipe.repof)
            f.close()
        args = []
        for arg in executable_node.getElementsByTagName('arg'):
            args.append(xml_attr(arg, 'value'))
        task.executable, task.args = normalize_executable(xml_attr(executable_node, 'url'), args)
        log.info("ExecutableTest %s %s", task.executable, task.args)


class TaskParser(object):

    def __init__(self, task_node, recipe, test_order):
        self.recipe = recipe
        self.task_node = task_node
        self.beaker_id = xml_attr(task_node, 'id')
        to = xml_attr(task_node, 'testorder')
        if to is not None:
            self.test_order = int(to)
        else:
            self.test_order = test_order
        self._env = None
        self.env = None

    def get_env(self):
        if not self.env:
            if not self.parse():
                raise Exception('Parse Error.')
            self.env = dict(self.recipe._env)
            self.env.update(self._env)
        return self.env

    def matcher(task_spec):
        if not task_spec:
            return lambda t: True
        if isinstance(task_spec, basestring):
            return lambda t: xml_attr(t, 'id') == task_spec
        if isinstance(task_spec, TaskParser):
            task_node = task_spec.task_node
            return lambda t: t == task_node
        if isinstance(task_spec, minidom.Element):
            return lambda t: task_spec == t
        raise TypeError('task_spec is of wrong type...')
    matcher = staticmethod(matcher)

    def get_params(self):
        answ = {}
        for p in self.task_node.getElementsByTagName('param'):
            answ[xml_attr(p, 'name')]=xml_attr(p, 'value')
        return answ

    def parse(self):

        if not self._env:

            task_id = self.beaker_id
            task_name = xml_attr(self.task_node, 'name')
            self.ewd = xml_attr(self.task_node, 'avg_time')

            self._env = {
                    'TASKID': str(task_id),
                    'RECIPETESTID': str(task_id),
                    'TESTID': str(task_id),
                    'TASKNAME': task_name,
                    'ROLE': xml_attr(self.task_node, 'role', ''),
                    'KILLTIME': self.ewd,
                    }

            self._env.update(self.get_params())

            if self._env.has_key('TESTORDER'):
                self._env['TESTORDER'] = str(8*int(self._env['TESTORDER']) + 4)
            else:
                self._env['TESTORDER'] = str(8*self.test_order)

            self.executable = ''
            self.args = []
            while True:
                rpm_tags = self.task_node.getElementsByTagName('rpm')
                log.debug("rpm tag: %s", rpm_tags)
                if rpm_tags:
                    self.parsed = RpmTaskParser(rpm_tags[0], self, task_name)
                    break
                exec_tags = self.task_node.getElementsByTagName('executable')
                log.debug("executable tag: %s", exec_tags)
                if exec_tags:
                    self.parsed = ExecutableTaskParser(exec_tags[0], self)
                    break
                break

        if not self.executable:
            log.warning("Task %s(%s) does not have an executable associated!",
                    task_name, task_id)
            return None

        return self

    def task_data(self):
        if self.parse():
            return dict(task_env=self.get_env(), executable=self.executable,
                    args=self.args, ewd=self.ewd)
        else:
            return None


class NothingToDoException(Exception):
    """
    Exception raised when:
    - scheduler does not have a recipe for the machine
    - or recipe contains no more jobs.
    """
    pass


def get_recipe_lc(recipe_id, proxy):
    """Get a recipe from LC."""
    args = {'recipe_id': recipe_id}
    return proxy.callRemote('get_my_recipe', args)


def get_recipe_cache_or_lc(recipe_id, runtime, proxy):
    """Get a recipe from cache or from LC."""
    recipe_xml = runtime.type_get('variables', 'RECIPE', None)
    if not recipe_xml:
        thingy = defer.waitForDeferred(get_recipe_lc(recipe_id, proxy))
        yield thingy
        recipe_xml = thingy.getResult()
        if recipe_xml:
            runtime.type_set('variables', 'RECIPE', recipe_xml)
    yield recipe_xml.encode('utf8')
get_recipe_cache_or_lc = defer.deferredGenerator(get_recipe_cache_or_lc)


def check_task_online(proxy):
    """Return function checking task_info against proxy."""
    def _check_task_online(parsed_task):
        """Query task status from proxy."""
        return proxy.callRemote("task_info", "T:%s" % parsed_task.beaker_id) \
                .addCallback(lambda task_info: not task_info or not task_info.get('is_finished', False))
    return _check_task_online


def get_roles(proxy):
    def _get_roles(task_id):
        return proxy.callRemote('get_peer_roles', task_id)
    return _get_roles


def simple_recipe(recipe_xml, run_task, recipe_id, backend):
    """Parse the XML and run tasks sequentially using task runner run_task."""
    # this is likely a common task:
    if not recipe_xml:
        raise NothingToDoException("Got empty recipe.")
    recipe_parser = RecipeParser.make(recipe_xml, recipe_id)
    if not recipe_parser:
        raise NothingToDoException("No recipe for id %s." % recipe_id)
    rs = xml_attr(recipe_parser.recipe_node, 'status')
    if rs not in ['Running', 'Waiting']:
        raise NothingToDoException("The recipe has finished.")
    beaker_id = recipe_parser.beaker_id
    recipe = BeakerRecipe(backend, beaker_id)
    backend.start(recipe)
    recipe_tasks = recipe_parser.tasks()
    for parsed_task in recipe_tasks:
        try:
            task = defer.waitForDeferred(run_task(backend, recipe, parsed_task))
            yield task
            result = task.getResult()
        except NothingToDoException:
            log.info("Task %r has exitted from recipe.", parsed_task.beaker_id)
            raise
        except:
            log.exception("Encoutnered problem while running task %r.",
                    parsed_task.beaker_id)
    raise NothingToDoException("No more tasks in recipe.")
simple_recipe = defer.deferredGenerator(simple_recipe)

def run_task(runtime, check_task=None, get_roles=None, env_overrides=None):
    """Function generator creating a task runner."""
    def _run_task(backend, recipe, parsed_task):
        """Check task status and execute it."""
        task_beaker_id = parsed_task.beaker_id
        # check status in xml data:
        task_status = xml_attr(parsed_task.task_node, 'status')
        if task_status not in ['Waiting', 'Running']:
            log.debug("task id: %r status: %r", task_beaker_id, task_status)
            return
        # check task data:
        task_data = parsed_task.task_data()
        if not task_data:
            log.error("task id: %r having no task data.", task_beaker_id)
            return
        task_name = task_data['task_env']['TASKNAME']
        task_args = {'name': task_name, 'beaker_id': task_beaker_id}
        # find task by beaker_id...
        run_cmd, task_uuid = runtime.type_get('tasks_by_id', task_beaker_id, (None, None))
        if task_uuid:
            task = recipe.tasks._get(task_uuid, (), task_args)
        else:
            task = None
        # ...and check the local status:
        if task and task.has_finished():
            log.debug("task id: %r finished.", task_beaker_id)
            return
        try:
            # try custom check:
            if check_task is not None:
                thingy = defer.waitForDeferred(check_task(parsed_task))
                yield thingy
                if not thingy.getResult():
                    log.debug("task id: %r finished.", task_beaker_id)
                    return
            # get live roles:
            if get_roles is not None:
                thingy = defer.waitForDeferred(get_roles(task_beaker_id))
                yield thingy
                roles = thingy.getResult()
                log.debug('got peer roles: %r' % roles)
                all_members = set()
                for role, hostnames in roles.items():
                    if role and role != 'None':
                        task_data['task_env'][role] = ' '.join(hostnames)
                    all_members.update(hostnames)
                task_data['task_env']['RECIPE_MEMBERS'] = ' '.join(all_members)
            log.debug("about to run task(task=%s, task_data=%s)", parsed_task, task_data)
            if env_overrides:
                task_data['task_env'].update(env_overrides)
            # get run cmd:
            if not run_cmd:
                run_cmd = command.run(task_data['executable'],
                        name=task_name,
                        env=task_data['task_env'],
                        args=task_data['args'])
                task_uuid = run_cmd.id()
                runtime.type_set('tasks_by_id', task_beaker_id, (run_cmd, task_uuid))
                runtime.sync()
            # get task
            if task is None:
                task = recipe.tasks.make(task_uuid, **task_args)
                if task is None:
                    log.error("task id: %r failed.", task_beaker_id)
                    return
            runtime.sync()
            thingy = defer.waitForDeferred(backend.send_cmd(run_cmd))
            yield thingy
            thingy.getResult()
            thingy = defer.waitForDeferred(task.deferred)
            yield thingy
            thingy.getResult()
            if task:
                task.set_finished()
        # this is a workaround for yield not working in try:finally: in python
        # up to 2.4 :-(
        except:
            if task:
                task.set_finished()
            raise
    return defer.deferredGenerator(_run_task)

#https://bugzilla.redhat.com/show_bug.cgi?id=1004381
def handle_recipe_exception(failure):
    # trap all exceptions
    failure.trap(Exception)

    # If it is NothingToDoException
    if failure.check(NothingToDoException):
        log.info(failure.getErrorMessage())
    else:
        log.error(failure.printTraceback())
    return

def simple_schedule(conf, runtime, proxy, backend):
    """Get a recipe and run tasks."""
    recipe_id = int(conf.get('DEFAULT', 'RECIPEID'))
    env_overrides = {'LAB_CONTROLLER': conf.get('DEFAULT', 'COBBLER_SERVER')}
    task_runner = run_task(runtime, check_task=check_task_online(proxy),
            get_roles=get_roles(proxy),
            env_overrides=env_overrides)
    d = get_recipe_cache_or_lc(recipe_id, runtime, proxy)
    d.addCallback(simple_recipe, task_runner, recipe_id, backend)
    d.addErrback(handle_recipe_exception)
    return


################################################################################
# Reporting:
################################################################################


def handle_error(result, *args, **kwargs):
    log.warning("Deferred Failed(%r, *%r, **%r)", result, args, kwargs)
    return result


def jsonln(obj):
    return "%s\n" % json.dumps(obj)


def open_(name, mode):
    pre_open(name)
    return open(name, mode)


class repeatWithLog(repeatingproxy.repeatWithHandle):

    logf = log.error

    def first_time(self, fail):
        self.logf("Remote call failed unexpectedly. Going into retry loop...\nFailure: %s", fail)


class Container(object):

    def __init__(self, parent, cls):
        self.parent = parent
        self.cls = cls
        self.cached = {}

    def set(self, id, obj):
        if obj is None:
            raise KeyError("%s instance with id '%s' does not exist." % (self.cls.__name__, id))
        self.cached[id] = obj
        return obj

    def _get(self, id, args, kwargs):
        o = self.cached.get(id, None)
        if o is not None:
            return o
        try:
            o = self.cls.get_object(id, self.parent, *args, **kwargs)
        except KeyError:
            o = None
        if o is None:
            o = self.default(id, args, kwargs)
            if o is not None:
                o._default_made = True
        return self.set(id, o)

    def get(self, id, default=None):
        try:
            return self._get(id, (), {})
        except KeyError:
            return default

    def default(self, id, args, kwargs):
        return self.cls.make_default(id, self.parent, *args, **kwargs)

    def get_cached(self):
        '''Return all in memory objects.'''
        return self.cached.values()

    def __getitem__(self, id):
        return self._get(id, (), {})

    def __setitem__(self, id, value):
        return self.set(id, value)

    def make(self, id, *args, **kwargs):
        if self.cached.get(id, None) is not None:
            raise KeyError("%s with id '%s' already exists." % (self.cls.__name__, id))
        return self.set(id, self.cls.make_object(id, self.parent, *args, **kwargs))


class Item(object):

    def get_object(cls, id, parent, *args, **kwargs):
        raise KeyError("%s instance with id '%s' does not exist." %
                (cls.__name__, id))
    get_object = classmethod(get_object)

    def make_default(cls, id, parent, *args, **kwargs):
        raise KeyError("%s instance with id '%s' does not exist. Default is not implememted." %
                (cls.__name__, id))
    make_default = classmethod(make_default)

    def make_object(cls, id, parent, *args, **kwargs):
        raise NotImplementedError
    make_object = classmethod(make_object)


class PersistentItem(Item):

    def get_object(cls, id, parent, *args, **kwargs):
        return cls.read_object(id, parent, *args, **kwargs)
    get_object = classmethod(get_object)

    def read_object(cls, id, parent, *args, **kwargs):
        raise NotImplementedError
    read_object = classmethod(read_object)

    def write_object(self):
        raise NotImplementedError


class BeakerContainer(Container):

    def __init__(self, parent, cls, id=None):
        Container.__init__(self, parent, cls)

    def close(self):
        while self.cached:
            id, obj = self.cached.popitem()
            try:
                obj.close()
            except:
                self.parent.backend().on_exception("can not close object %s" % (obj,))

class PersistentBeakerContainer(BeakerContainer):

    METADATA = ''

    def __init__(self, parent, cls, id=None):
        BeakerContainer.__init__(self, parent, cls)
        list_id = "%s/children/%s" % (id or parent.id, self.METADATA or cls.__name__)
        self.id_list = runtimes.TypeList(parent.runtime(), list_id)

    def set(self, id, obj):
        BeakerContainer.set(self, id, obj)
        self.id_list.append(id)
        return obj

    def get_all_ids(self):
        return list(self.id_list)

    def get_all(self):
        '''Return all objects including ones written to permanent storage.'''
        ids = self.get_all_ids()
        return [self.get(id) for id in ids]


class BeakerObject(object):

    def __init__(self, id, parent):
        self.id = id
        self._set_parent(parent)
        self.__backend = parent.backend()
        self.__proxy = self.__backend.proxy

    def _set_parent(self, parent):
        '''Use this to modify object hierarchy. Use with care!'''
        self.parent = parent

    def close(self): # pylint: disable=E0202
        self.parent = None
        self.close = lambda: None

    def parent_task(self):
        return self.parent.parent_task()

    def backend(self):
        return self.__backend

    def runtime(self):
        return self.backend().runtime

    def proxy(self):
        return self.__proxy

    def log_error(self, message):
        self.backend().on_error(message)


class PersistentBeakerObject(BeakerObject, PersistentItem):

    METADATA = 'beaker_info'

    def __init__(self, id, parent):
        '''
        Instance variables:

        stored_data -- dictionary like structure. Items are written on
        assignment. Use this for more frequently changed items.

        NOTE: This is not an ordinary dictionary - it does not overwrite
        existing data with None`s. Use delete instead.

        meta_data -- dictionary which requires explicit write - write_metadata.
        Use this for data written once, or just couple of times.
        '''
        BeakerObject.__init__(self, id, parent)
        self.stored_data = runtimes.TypeAddict(self.runtime(), '%s/%s' % (self.METADATA, id))
        self.meta_data = addict(self.stored_data.get('meta', {}))

    def make_object(cls, id, parent, *args, **kwargs):
        o = cls(id, parent, *args, **kwargs)
        o.write_object()
        return o
    make_object = classmethod(make_object)

    def read_object(cls, id, parent, *args, **kwargs):
        if parent.runtime().type_has_key('%s/%s' % (cls.METADATA, id), 'meta'):
            return cls(id, parent, *args, **kwargs)
        raise KeyError
    read_object = classmethod(read_object)

    def write_metadata(self):
        self.stored_data['meta'] = dict(self.meta_data)

    def write_object(self):
        self.write_metadata()


class BeakerWriter(writers.JournallingWriter, BeakerObject, Item):

    _VERBOSE = ('write', 'send')

    def __init__(self, name, parent):
        BeakerObject.__init__(self, name, parent)
        # Use private functions to avoid many self.parent... evaluations
        id = parent.beaker_id
        offs_ = 'offsets/%s' % parent.id
        offs = parent.runtime().type_get(offs_, name, 0)
        rpc = parent.proxy().callRemote
        method = parent.UPLOAD_METHOD
        digest_method = parent.digest_method()
        filename=os.path.basename(name)
        path=os.path.dirname(name) or '/'
        digest_constructor = digests.DigestConstructor(digest_method or 'md5')
        runtime_set = self.runtime().type_set
        self.send = (lambda cdata:
                rpc(method, id, path, filename, len(cdata),
                    digest_constructor(cdata).hexdigest(),
                    self.get_offset(),
                    event.encode("base64", cdata)))
        self.set_offset = (lambda offset: (
            runtime_set(offs_, name, offset),
            writers.JournallingWriter.set_offset(self, offset)))
        jname = os.path.join(parent.backend().conf.get('DEFAULT', 'VAR_ROOT'), "journals", id, name)
        journal = open_(jname, "ab+")
        writers.JournallingWriter.__init__(self, journal, offs, capacity=4096, no_split=True)

    def close(self): # pylint: disable=E0202
        self.journal.close()
        writers.JournallingWriter.close(self)

    def make_default(cls, id, parent):
        return BeakerWriter(id, parent)
    make_default = classmethod(make_default)


class BeakerLinkCounter(object):

    def __init__(self, owner):
        """
        Class to check number of files uploaded to server.

        check_link is the main entry point.

        """
        if owner.link_limits[0] <= 0 and owner.link_limits[1] <= 0:
            self.check_link = owner.parent.check_link
        else:
            self.owner = owner
            self.limits = owner.link_limits
            self.link_warn = owner.stored_data.get('link_limit', 0)
            self.alive = self.link_warn < 2

    def _check_link(self):
        sd = self.owner.stored_data
        amt = sd.get('link_total', 0) + 1
        sd['link_total'] = amt
        limit = self.limits[1]
        if limit > 0 and amt > limit:
            if self.link_warn < 2:
                self.owner.parent_task().send_result('warn', 'link_limit', amt,
                        "%s has reached link limit! (%s > %s)" % (self.owner.name(), amt, limit))
                self.link_warn = 2
                sd['link_limit'] = 2
            return False
        limit = self.limits[0]
        if limit > 0 and amt > limit and self.link_warn < 1:
            self.owner.parent_task().send_result('warn', 'link_limit/soft', amt,
                    "%s has reached soft link limit! (%s > %s)" % (self.owner.name(), amt, limit))
            self.link_warn = 1
            sd['link_limit'] = 1
        return True

    def check_link(self): # pylint: disable=E0202
        if not self.alive:
            return False
        self.alive = self._check_link() and self.owner.parent.check_link()
        return self.alive


class BeakerUploadCounter(object):

    def __init__(self, owner):
        """
        Class to check amount of data uploaded to server.

        check_upload is the main entry point.

        """
        alive = True
        check = False
        if owner.upload_limits[0] <= 0 and owner.upload_limits[1] <= 0:
            self.check_upload_amount = lambda size: True
        else:
            check = True
            self.upload_limits = owner.upload_limits
            self.upload_warn = owner.stored_data.get('upload_warn', 0)
            alive = alive and self.upload_warn < 2

        if owner.size_limits[0] <= 0 and owner.size_limits[1] <= 0:
            self.check_file_size = lambda delta: True
        else:
            check = True
            self.size_limits = owner.size_limits
            self.size_warn = owner.stored_data.get('size_warn', 0)
            alive = alive and self.size_warn < 2

        if not check:
            self.check_upload = owner.parent.check_upload
        else:
            self.owner = owner
            self.upload_alive = alive

    def check_upload_amount(self, size): # pylint: disable=E0202
        sd = self.owner.stored_data
        amt = sd.get('upload_total', 0) + size
        sd['upload_total'] = amt
        limit = self.upload_limits[1]
        if limit > 0 and amt > limit:
            if self.upload_warn < 2:
                self.owner.parent_task().send_result('warn', 'upload_limit', amt, "%s has reached upload limit! (%s > %s)" % (self.owner.name(), amt, limit))
                self.upload_warn = 2
                sd['upload_warn'] = 2
            return False
        limit = self.upload_limits[0]
        if limit > 0 and amt > limit and self.upload_warn < 1:
            self.owner.parent_task().send_result('warn', 'upload_limit/soft', amt, "%s has reached soft upload limit! (%s > %s)" % (self.owner.name(), amt, limit))
            self.upload_warn = 1
            sd['upload_warn'] = 1
        return True

    def _check_file_size(self, size_total):
        limit = self.size_limits[1]
        if limit > 0 and size_total > limit:
            if self.size_warn < 2:
                self.owner.parent_task().send_result('warn', 'size_limit', size_total, "%s has reached size limit! (%s > %s)" % (self.owner.name(), size_total, limit))
                self.size_warn = 2
                self.owner.stored_data['size_warn'] = 2
            return False
        limit = self.size_limits[0]
        if limit > 0 and size_total > limit and self.size_warn < 1:
            self.owner.parent_task().send_result('warn', 'size_limit/soft', size_total, "%s has reached soft size limit! (%s > %s)" % (self.owner.name(), size_total, limit))
            self.size_warn = 1
            self.owner.stored_data['size_warn'] = 1
        return True

    def check_file_size(self, delta): # pylint: disable=E0202
        sd = self.owner.stored_data
        amt = sd.get('size_total', 0) + delta
        sd['size_total'] = amt
        return self._check_file_size(amt)

    def _check_upload(self, delta, size):
        """Check this instance."""
        return self.check_upload_amount(size) and self.check_file_size(delta)

    def check_upload(self, delta, size): # pylint: disable=E0202
        if not self.upload_alive:
            return False
        self.upload_alive = (self._check_upload(delta, size) and
                self.owner.parent.check_upload(delta, size))
        return self.upload_alive


class NullFile(object):

    def _set_parent(self, parent):
        pass

    def meta(self, metadata):
        pass

    def write(self, args):
        pass

    def close(self):
        pass


def truef():
    return True


def falsef():
    return False


def boolf(cond):
    if cond:
        return truef
    else:
        return falsef


class BeakerTask(PersistentBeakerObject):

    _VERBOSE = ['__init__', 'start', 'end', 'abort', 'new_result', 'new_file', 'output', 'stop', 'writer']
    METADATA = 'task_info'
    UPLOAD_METHOD = 'task_upload_file'
    UPLOAD_LIMIT = 'TASK_UPLOAD_LIMIT'
    UPLOAD_LIMIT_SOFT = 'TASK_UPLOAD_LIMIT_SOFT'
    SIZE_LIMIT = 'TASK_SIZE_LIMIT'
    SIZE_LIMIT_SOFT = 'TASK_SIZE_LIMIT_SOFT'
    LINK_LIMIT = 'TASK_LINK_LIMIT'
    LINK_LIMIT_SOFT = 'TASK_LINK_LIMIT_SOFT'

    null_file = NullFile()

    def get_meta(self, attr, default):
        """
        Get attr from meta_data or store and return default if not set.

        Check Consistency: If both default and value in meta_data are set, log
        an error if values do not match.

        Return tuple (found, value) where:

        - found is True if found in meta_data, False if default was stored and
          returned
        - value is the return value

        NOTE: When field is not found in meta_data, default is written to
        runtime and caller is responsible for calling self.write_metadata() to
        flush meta_data.

        """
        meta = self.meta_data.get(attr, None)
        if meta is None:
            self.meta_data[attr] = default
            return (False, default)
        if default and default != meta:
            log.error("Inconsistent %s: %s in metadata, %s passed.",
                    attr, meta, default)
        return (True, meta)

    def __init__(self, id, parent, name='', beaker_id=None, deferred=None):
        PersistentBeakerObject.__init__(self, id, parent)
        self.deferred = deferred or defer.Deferred()
        found_name, self._name = self.get_meta('_name', name)
        found_id, self.beaker_id = self.get_meta('beaker_id', beaker_id)
        assert self.beaker_id
        if not found_name or not found_id:
            self.write_metadata()
        self.writers = PersistentBeakerContainer(self, BeakerWriter)
        self.results = BeakerContainer(self, BeakerResult)
        self.files = BeakerContainer(self, BeakerFile)
        confget = self.backend().conf.get
        self.upload_limits = [int(confget('DEFAULT', self.UPLOAD_LIMIT_SOFT, '-1')),
                int(confget('DEFAULT', self.UPLOAD_LIMIT, '-1'))]
        self.size_limits = [int(confget('DEFAULT', self.SIZE_LIMIT_SOFT, '-1')),
                int(confget('DEFAULT', self.SIZE_LIMIT, '-1'))]
        self.check_upload = BeakerUploadCounter(self).check_upload
        self.link_limits = [int(confget('DEFAULT', self.LINK_LIMIT_SOFT, '-1')),
                int(confget('DEFAULT', self.LINK_LIMIT, '-1'))]
        self.check_link = BeakerLinkCounter(self).check_link
        self.on_set_state()

    def close(self): # pylint: disable=E0202
        self.writers.close()
        self.writers = None
        self.results.close()
        self.results = None
        self.files.close()
        self.files = None
        self.check_link = None
        self.set_completed()
        PersistentBeakerObject.close(self)

    def name(self):
        if not getattr(self, '_name', ''):
            self._name = 'task_%s' % (self.beaker_id,)
        return self._name

    def digest_method(self):
        return self.backend().digest_method

    def start(self):
        if not self.has_started():
            self.set_started()
            # FIXME: start local watchdog
            self.proxy().repeatedRemote(repeatWithLog(repeatingproxy.repeatAlways), 'task_start', self.beaker_id, 0)

    def abort(self, message):
        self.set_finished()
        self.send_result('fail', 'harness/run', 1, message)
        return self.stop('abort', message)

    def flush(self):
        self.flush_writers()

    def send_result(self, result, handle, score=0, message=''):
        return self.proxy().callRemote('task_result', self.beaker_id, result, handle, score, message)

    def end(self, rc):
        if rc is None:
            score = 999
        else:
            score = int(rc)
        if score != 0:
            message = 'Task adaptor returned non zero exit code. This is likely a harness problem. rc=%s' % rc
            self.send_result('pass', 'task/exit', score, message)
        else:
            message = 'OK'
        return self.stop('stop', message)

    def parent_task(self):
        return self

    STATE_INIT = 0 # uninitialised state
    STATE_STARTED = 10 # the task started
    STATE_FINISHED = 20 # the task finished, but there may be pending data
    STATE_COMPLETED = 30 # all tasks data are uploaded

    def on_set_state(self, new_state=None):
        state = self.stored_data.get('state', self.STATE_INIT)
        if new_state is None:
            new_state = state
        else:
            if new_state <= state:
                return
            self.stored_data['state'] = new_state
            self.write_metadata()
        self.has_started = boolf(new_state >= self.STATE_STARTED)
        self.has_finished = boolf(new_state >= self.STATE_FINISHED)
        self.has_completed = boolf(new_state >= self.STATE_COMPLETED)

    def set_started(self):
        self.on_set_state(self.STATE_STARTED)

    def set_finished(self):
        self.on_set_state(self.STATE_FINISHED)

    def set_completed(self):
        self.on_set_state(self.STATE_COMPLETED)

    def flush_writers(self):
        for writer in self.writers.get_cached():
            writer.flush()

    def writer(self, name):
        return self.writers.get(name)

    def new_result(self, id, args):
        return self.results.make(id, args)

    def result(self, id):
        return self.results.get(id, None)

    def new_file(self, id, args):
        if not self.check_link():
            return self.files.set(id, self.null_file)
        return self.files.make(id, metadata=dict(args))

    def file(self, id):
        return self.files.get(id, self.null_file)

    def output(self, args):
        self.writer('debug/task_output_%s' % args.get('out_handle', '')) \
                        .write(str(args['data']))

    def stop(self, type, msg):
        # type: ('stop'|'abort')
        self.flush()
        return self.proxy().callRemote('task_stop', self.beaker_id, type, msg) \
                .chainDeferred(self.deferred)


class BeakerResult(BeakerObject, PersistentItem):

    PENDING_RESULT = '?'
    METADATA = 'result'
    _VERBOSE = ('set_id', 'attach')
    UPLOAD_METHOD = 'result_upload_file'

    def __init__(self, id, parent, name=''):
        BeakerObject.__init__(self, id, parent)
        self.beaker_id = self.runtime().type_get('results_by_uuid', id, self.PENDING_RESULT)
        # SAVE THE NAME!
        self._name = name

    def name(self):
        return self._name

    def make_message(cls, **kwargs):
        return json.dumps(kwargs)
    make_message = classmethod(make_message)

    def make_object(cls, id, parent, args={}):
        result = cls(id, parent)
        type = result.result_type(args.get('rc', None))
        handle = args.get('handle', '%s/%s' % \
                (parent.name(), id))
        statistics = args.get('statistics') or {}
        score = statistics.get('score', 0)
        message = args.get('message', '') or cls.make_message(args=args)
        log_msg = '%s:%s: %s score=%s\n' % (type[1], handle, message, score)
        parent.writer('debug/task_log').write(log_msg)
        parent.send_result(type[0], handle, score, message).addCallback(result.handle_Result)
        return result
    make_object = classmethod(make_object)

    def read_object(cls, id, parent, args={}):
        result = cls(id, parent)
        if result.beaker_id == cls.PENDING_RESULT:
            raise KeyError("The result '%s' did not get through." % id)
    read_object = classmethod(read_object)

    def write_object(self):
        pass

    def handle_Result(self, result_id):
        '''Attach data to a result. Find result by UUID.'''
        log.debug("%s.RETURN: %s (original event_id %s)",
                'task_result', result_id, self.id)
        self.set_id(result_id)

    def set_id(self, id):
        self.beaker_id = id
        self.runtime().type_set('results_by_uuid', self.id, id)
        if not self._name:
            self._name = "result_%s" % self.beaker_id

    def attach(self, file, attach_as=None):
        # pass
        result_id = self.beaker_id
        if result_id == self.PENDING_RESULT:
            self.log_error("Waiting for result_id from LC for given id (%s)." % self.id)
            return
        if file is None:
            self.log_error("File with given id does not exist.")
            return
        file._set_parent(self)
        if attach_as:
            file.meta({'be:upload_as': attach_as})
        log.debug("relation result_file processed. finfo updated: %r", file)

    RESULT_TYPE = {
            RC.PASS:("pass_", "Pass"),
            RC.WARNING:("warn", "Warning"),
            RC.FAIL:("fail", "Fail"),
            RC.CRITICAL:("panic", "Panic - Critical"),
            RC.FATAL:("panic", "Panic - Fatal"),
            }

    def result_type(rc):
        return BeakerResult.RESULT_TYPE.get(rc,
                ("warn", "Warning: Unknown Code (%s)" % rc))
    result_type = staticmethod(result_type)

    def check_upload(self, delta, size):
        return self.parent.check_upload(delta, size)


class BeakerFile(PersistentBeakerObject):

    METADATA = "file_info"
    _VERBOSE = ('__init__', 'meta', 'write', 'filename')

    UPLOAD_LIMIT = 'FILE_UPLOAD_LIMIT'
    UPLOAD_LIMIT_SOFT = 'FILE_UPLOAD_LIMIT_SOFT'
    SIZE_LIMIT = 'FILE_SIZE_LIMIT'
    SIZE_LIMIT_SOFT = 'FILE_SIZE_LIMIT_SOFT'

    def __init__(self, fid, parent, metadata=None):
        PersistentBeakerObject.__init__(self, fid, parent)
        self.meta(metadata)
        confget = self.backend().conf.get
        self.upload_limits = [int(confget('DEFAULT', self.UPLOAD_LIMIT_SOFT, '-1')),
                int(confget('DEFAULT', self.UPLOAD_LIMIT, '-1'))]
        self.size_limits = [int(confget('DEFAULT', self.SIZE_LIMIT_SOFT, '-1')),
                int(confget('DEFAULT', self.SIZE_LIMIT, '-1'))]
        self.check_upload = BeakerUploadCounter(self).check_upload

    def make_default(cls, fid, parent):
        return BeakerFakeFile(fid, parent)
    make_default = classmethod(make_default)

    def meta(self, metadata):
        if metadata:
            self.meta_data.update(metadata)
            self.write_metadata()

    def get_meta(self, item, default):
        answ = self.meta_data.get(item, None)
        if answ is None:
            answ = default
        return answ

    def read_object(cls, id, parent):
        pass
    read_object = classmethod(read_object)

    def write_object(self):
        pass

    def recode(data, in_codec, out_codec, in_digest, out_digest_method):
        '''
        return: (cdata_len, out_data, out_digest)
        '''
        cdata = event.decode(in_codec, data)
        if cdata is None:
            raise RuntimeError("No data found.")
        dm, digest = digests.make_digest(in_digest) or (None, None)
        # FIXME: Optionally check digest
        if dm != out_digest_method:
            digest = digests.DigestConstructor(out_digest_method)(cdata).hexdigest()
        if in_codec != out_codec:
            data = event.encode(out_codec, cdata)
        return (len(cdata), data, digest)
    recode = staticmethod(recode)

    def filename(self):
        pathname = (self.get_meta('be:upload_as', '')
                or self.get_meta('name', '')
                or "file_%s" % self.id)
        path, filename = os.path.split(pathname)
        return (path or "/", filename)

    def name(self):
        return "file:%s/%s" % self.filename()

    def writer(self):
        if getattr(self, '_be_writer', None) is None:
            if self.stored_data.has_key('be:uploading_as'):
                method, id, path, filename = self.stored_data['be:uploading_as']
            else:
                method = self.parent.UPLOAD_METHOD
                id = self.parent.beaker_id
                path, filename = self.filename()
                self.stored_data['be:uploading_as'] = (method, id, path, filename)
            rpc = self.proxy().callRemote
            log.debug("writer for method=%r, id=%r, path=%r, filename=%r", method, id, path, filename)
            def writer_(size, digest, offset, data):
                return rpc(method, id, path, filename, size, digest, str(offset), data)
            self._be_writer = writer_
        return self._be_writer

    def check_offset(self, offset):
        """
        Check the offset and return pair (offset to use, original offset).

        """
        seqoff = self.stored_data.get('offset', 0)
        if offset is None:
            offset = seqoff
        elif offset != seqoff:
            if offset == 0:
                # task might want to re-upload file from offset 0.
                log.info('Rewriting file %s.' % self.id)
            else:
                log.warning("Given offset (%s) does not match calculated (%s).",
                        offset, seqoff)
        return (offset, seqoff)

    def write(self, args):
        (offset, seqoff) = self.check_offset(args.get('offset', None))
        codec = args.get('codec', None)
        if codec is None:
            codec = self.get_meta('codec', None)
        size, data, digest = self.recode(args.get('data'), codec, "base64", args.get('digest', None), self.backend().digest_method)
        if not self.check_upload(offset+size-seqoff, size):
            return
        self.writer()(size, digest, offset, data).addCallback(self.written, new_offset=offset+size)

    def written(self, response, new_offset=None):
        self.stored_data['offset'] = new_offset


def BeakerFakeFile(fid, parent):
    return BeakerFile(fid, parent, dict(name="FakeFile-%s" % fid))


class BeakerRecipe(BeakerTask):

    _VERBOSE = ['task',] + BeakerTask._VERBOSE

    METADATA = "recipe"
    UPLOAD_METHOD = 'recipe_upload_file'
    UPLOAD_LIMIT = 'RECIPE_UPLOAD_LIMIT'
    UPLOAD_LIMIT_SOFT = 'RECIPE_UPLOAD_LIMIT_SOFT'
    SIZE_LIMIT = 'RECIPE_SIZE_LIMIT'
    SIZE_LIMIT_SOFT = 'RECIPE_SIZE_LIMIT_SOFT'
    LINK_LIMIT = 'RECIPE_LINK_LIMIT'
    LINK_LIMIT_SOFT = 'RECIPE_LINK_LIMIT_SOFT'

    def __init__(self, backend, beaker_id):
        BeakerTask.__init__(self, 'the_recipe', backend,
                name='recipe_%s' % beaker_id, beaker_id=beaker_id)
        self.tasks = BeakerContainer(self, BeakerTask)

    def close(self): # pylint: disable=E0202
        self.tasks.close()
        self.tasks = None
        BeakerTask.close(self)

    def name(self):
        return 'the_recipe'

    def task(self, id):
        return self.tasks[id]

    def send_result(self, result, handle, score=0, message=''):
        result=('recipe_result', self.beaker_id, result, handle, score, message)
        msg = "Can not attach a result to recipe. Result=%s" % (result,)
        log.error(msg)


class JournallingQueue(object):

    def __init__(self, offset_writer=None, read_offset=None, journal_file=None):
        self.queue = []
        self.len_queue = []
        self.journal_file = journal_file
        self.journal_ready = False
        self.read_offset = read_offset
        self.offset_writer = offset_writer

    def ready(self):
        return self.journal_ready


    def _enqueue(self, obj, data_len):
        self.queue.append(obj)
        self.len_queue.append(data_len)

    def push(self, obj):
        data = jsonln(obj)
        self.journal_file.write(data)
        self.journal_file.flush()
        if self.ready():
            self._enqueue(obj, len(data))

    def pop(self):
        self.read_offset += self.len_queue.pop(0)
        self.offset_writer(self.read_offset)
        return self.queue.pop(0)

    def top(self):
        return self.queue[0]

    def empty(self):
        return not self.queue


def journal_reader(queue, journal_in, backend):
    if queue.ready():
        return
    evt_len = 0 # counter to skip any events which can not be enqueued
    while True:
        ln = journal_in.readline()
        evt_len += len(ln)
        if ln == '':
            if evt_len > 0:
                queue._enqueue((event.nop(), {}), evt_len)
            break
        try:
            evt, flags = json.loads(ln)
            evt = event.Event(evt)
            if not backend.async_proc(evt, flags):
                tid = evt.task_id()
                log.error("No task '%s' for the event '%r'.", tid, evt)
                continue
            queue._enqueue((evt, flags), evt_len)
            evt_len = 0
        except:
                log.error("Can not parse a line from journal. line=%r", ln)
    journal_in.close()
    queue.journal_ready = True


class BeakerLCBackend(SerializingBackend):

    _VERBOSE = ['set_controller', '_send_cmd',
            'proc_evt', 'pre_proc', 'proc_evt_output',
            'proc_evt_lose_item', 'proc_evt_log', 'proc_evt_echo',
            'proc_evt_start', 'proc_evt_end', 'proc_evt_result',
            'proc_evt_relation', 'proc_evt_file', 'proc_evt_file_meta',
            'proc_evt_file_write', 'proc_evt_abort',
            ]
    _VERBOSE += ['set_idle', '_next_evt', '_pop_evt', 'idle',
            ]

    WATCHDOG_TOLERANCE = 5 # Account for trip from scheduler to handler

    def __init__(self, conf=None, proxy=None, runtime=None, queue=None,
            build_queue=None):
        self.conf = conf
        self.digest_method = "no-digest" # self.conf.get('DEFAULT', 'DIGEST')
        self.name = self.conf.get('DEFAULT', 'NAME')
        self.runtime = runtime
        self.__commands = {}
        self.recipe = None
        self.__command_callbacks = {}
        self.__cmd_queue = []
        self.proxy = proxy
        self.build_queue = build_queue
        SerializingBackend.__init__(self, queue)

    def start(self, recipe):
        self.recipe = recipe
        self.flush()
        self.build_queue(self)

    def check_link(self):
        return True

    def check_upload(self, size, delta):
        return True

    def backend(self):
        '''Used by recipe to allow using Backend as its parent'''
        return self

    def log_error(self, message):
        '''Used by recipe to allow using Backend as its parent'''
        self.on_error(message)

    def idle(self):
        return self.proxy.is_idle()

    def set_controller(self, controller=None):
        SerializingBackend.set_controller(self, controller)
        if controller:
            log.info("Connected to controller.")
            while self.__cmd_queue:
                self._send_cmd(self.__cmd_queue.pop())
        else:
            log.info("Connection to controller lost.")

    def close(self):
        pass

    def flush(self):
        """Flush any memory-cached data to disk."""
        log.debug("flush")
        self.runtime.sync()

    ############################################################################
    # RECIPE HANDLING
    ############################################################################

    def get_evt_task(self, evt):
        if not self.recipe:
            return None
        task = getattr(evt, 'task', None)
        if task is not None:
            return task
        tid = evt.task_id()
        if tid is None:
            return None
        task = self.recipe.tasks.get(tid, None)
        if task is not None:
            evt.task = task
        return task

    def _send_cmd(self, cmd):
        log.info("Command %s sent.", cmd)
        self.controller.proc_cmd(self, cmd)

    def send_cmd(self, cmd):
        if self.controller:
            self._send_cmd(cmd)
        else:
            log.info("No connection to Controller. %s is queued.", cmd)
            self.__cmd_queue.append(cmd)
        d = defer.Deferred()
        self.__command_callbacks[cmd.id()] = d
        return d

    def __on_error(self, level, msg, tb, *args, **kwargs):
        if args: msg += '; *args=%r' % (args,)
        if kwargs: msg += '; **kwargs=%r' % (kwargs,)
        log.error("--- %s: %s at %s", level, msg, tb)

    def on_exception(self, msg, *args, **kwargs):
        self.__on_error("EXCEPTION", msg, format_exc(),
                *args, **kwargs)

    def on_error(self, msg, *args, **kwargs):
        self.__on_error("ERROR", msg, traceback.format_stack(), *args, **kwargs)

    ############################################################################
    # EVENT PROCESSING:
    ############################################################################

    def pre_proc(self, evt):
        task = self.get_evt_task(evt)
        if not task or task.has_completed():
            # Do not submit to finished tasks!
            return True
        task.writer('debug/.task_beah_raw').write(jsonln(evt.printable()))
        return False

    def proc_evt_output(self, evt):
        evt.task.output(evt.args())

    def proc_evt_lose_item(self, evt):
        evt.task.writer('debug/task_beah_unexpected').write(str(evt.arg('data')) + "\n")

    def proc_evt_log(self, evt):
        message = evt.arg('message', '')
        reason = evt.arg('reason', '')
        join = ''
        if reason:
            reason = 'reason=%s' % reason
            if message:
                message = "%s; %s" % (message, reason)
            else:
                message = reason
        message = "LOG:%s(%s): %s\n" % (evt.arg('log_handle', ''),
                self.log_type(evt.arg('log_level')), message)
        evt.task.writer('debug/task_log').write(message)

    def proc_evt_echo(self, evt):
        # answer to run command if task exists:
        rc = evt.arg('rc')
        if rc not in (ECHO.OK, ECHO.DUPLICATE) and not evt.task.has_finished():
            evt.task.abort("Harness could not run the task: %s rc=%s" %
                (evt.arg('message', 'no info'), rc))

    def proc_evt_start(self, evt):
        evt.task.start()

    def proc_evt_end(self, evt):
        evt.task.end(evt.arg("rc", None)).addBoth(lambda ignored: evt.task.close())

    def handle_status_watchdog(self, watchdog, task):
        self.send_cmd(command.forward(event.extend_watchdog(
            watchdog - self.WATCHDOG_TOLERANCE,
            origin={'id': task.id, 'source': self.name})))

    def async_proc(self, evt, flags):
        if self.get_evt_task(evt) is None:
            return False
        evev = evt.event()
        # some events need asynchronous processing, so they do not wait in
        # queue.
        if evev == 'query_watchdog':
            # query_watchdog is sent immediately. May be used as ping.
            id = evt.task.beaker_id
            d = self.proxy.callRemote('status_watchdog', id)
            d.addCallback(self.handle_status_watchdog, evt.task)
        if evev == 'extend_watchdog':
            # extend_watchdog is send immediately, to prevent EWD killing us in
            # case of network/LC problems.
            tio = evt.arg('timeout')
            id = evt.task.beaker_id
            log.info('Extending Watchdog for task %s by %s..', id, tio)
            d = self.proxy.callRemote('extend_watchdog', id, tio)
            d.addCallback(self.handle_status_watchdog, evt.task)
            #return
        elif evev == 'end':
            # task is done: override EWD to allow for data submission, even in
            # case of network/LC problems:
            evt.task.set_finished()
            id = evt.task.beaker_id
            log.info('Task %s done. Submitting logs...', id)
            d = self.proxy.callRemote('extend_watchdog', id, 4*3600)
            d.addCallback(self.handle_status_watchdog, evt.task)
            # end will be processed synchronously too to mark the task finished
        return True

    def proc_evt(self, evt, **flags):
        if evt.origin().get('source', None) == self.name:
            return
        evev = evt.event()
        if evev == 'echo':
            cid = evt.arg('cmd_id', None)
            cb = self.__command_callbacks.get(cid, None)
            if cb:
                del self.__command_callbacks[cid]
                if evt.arg('rc') == ECHO.OK:
                    cb.callback(evt.args)
                else:
                    cb.errback(evt.args)
        elif evev == 'flush':
            self.flush()
            return
        if self._queue_ready():
            # store the task:
            if not self.async_proc(evt, flags):
                return
            SerializingBackend.proc_evt(self, evt, **flags)
        else:
            self._queue_evt(evt, flags)

    def proc_evt_abort(self, evt):
        type = evt.arg('type', '')
        if not type:
            log.error("No abort type specified.")
            raise exceptions.RuntimeError("No abort type specified.")
        task = evt.task
        task.flush()
        id_ = task.beaker_id
        target = evt.arg('target', None)
        d = None
        msg = evt.arg('msg', '')
        if msg:
            msg = " aborted by task %s: %s" % (id_, msg)
        else:
            msg = " aborted by task %s" % (id_,)
        if type == 'recipeset':
            target = self.find_recipeset_id(target)
            if target is not None:
                d = self.proxy.callRemote('recipeset_stop', target, 'abort', "RecipeSet"+msg)
        elif type == 'job':
            target = self.find_job_id(target)
            if target is not None:
                d = self.proxy.callRemote('job_stop', target, 'abort', "Job"+msg)
        elif type == 'recipe':
            target = self.find_recipe_id(target)
            if target is not None:
                d = self.proxy.callRemote('recipe_stop', target, 'abort', "Recipe"+msg)
        elif type == 'task':
            target = self.find_task_id(target)
            if target is not None:
                if target != id_:
                    log.warning("Can abort only currently running task.")
                    return
                if task.has_completed():
                    return
                task.stop('abort', "Task"+msg).addBoth(lambda ignored: task.close())

    def proc_evt_result(self, evt):
        r = evt.task.new_result(evt.id(), evt.args())

    def proc_evt_relation(self, evt):
        if evt.arg('handle') == 'result_file':
            result = evt.task.result(evt.arg('id1'))
            result.attach(evt.task.file(evt.arg('id2')), attach_as=evt.arg('title2'))

    def proc_evt_file(self, evt):
        evt.task.new_file(evt.id(), evt.args())

    def proc_evt_file_meta(self, evt):
        evt.task.file(evt.arg('file_id')).meta(evt.args())

    def proc_evt_file_write(self, evt):
        evt.task.file(evt.arg('file_id')).write(evt.args())

    # AUXILIARY:

    LOG_TYPE = {
            LOG_LEVEL.DEBUG3: "DEBUG3",
            LOG_LEVEL.DEBUG2: "DEBUG2",
            LOG_LEVEL.DEBUG1: "DEBUG",
            LOG_LEVEL.INFO: "INFO",
            LOG_LEVEL.WARNING: "WARNING",
            LOG_LEVEL.ERROR: "ERROR",
            LOG_LEVEL.CRITICAL: "CRITICAL",
            LOG_LEVEL.FATAL: "FATAL",
            }

    def log_type(log_level):
        return BeakerLCBackend.LOG_TYPE.get(log_level,
                "WARNING(%s)" % (log_level,))
    log_type = staticmethod(log_type)

    def find_job_id(self, id):
        return id

    def find_recipe_id(self, id):
        return id

    def find_recipeset_id(self, id):
        return id

    def find_task_id(self, id):
        return id


################################################################################
# Put it all together:
################################################################################


def make_runtime(conf, verbose=False):
    runtime = runtimes.ShelveRuntime(conf.get('DEFAULT', 'RUNTIME_FILE_NAME'))
    # override runtime sync to prevent performance hit:
    runtime_sync_orig = runtime.sync
    def runtime_sync(type=None):
        """
        Synchronize the runtime to disk.

        Original sync method will be called only when called explicitly
        i.e. with type == None.

        """
        if type is None:
            runtime_sync_orig()
            if verbose:
                log.debug("runtime.dump: %s" % (runtime.dump(sorted=True),))
    if verbose:
        log.debug("runtime.dump: %s" % (runtime.dump(sorted=True),))
    runtime.sync = runtime_sync
    return runtime


def has_ipv6(url):

    """ This function resolves the IPv6 address of the lab controller
    and then attempts to connect to the proxy port.
    If one of these fails, we cannot use IPv6
    """
    # sheer abuse of twisted.web.xmlrpc here to get the hostname/port 
    # reliably, since we can't use  stdlib's urlparse.urlsplit()
    # (Python 2.4 doesn't have what we want)
    url = xmlrpc.Proxy(url)
    lc_ipv6 = None
    try:
        #XXX: getaddrinfo() is blocking
        lc_ipv6 = socket.getaddrinfo(url.host, 0,
                                     socket.AF_INET6, 0, socket.SOL_TCP)[0][4][0]
    except socket.gaierror:
        log.info('Failed to look up IPv6 address for LC')
    else:
        log.info('Resolved IPv6 address of the LC')

    if not lc_ipv6:
        return None

    # can we connect?
    try:
        s = socket.socket(socket.AF_INET6)
        s.connect((lc_ipv6, url.port))
    except (socket.gaierror, socket.error):
        log.exception('Failed to connect to LC over IPv6.')
        lc_ipv6 = None

    return lc_ipv6

class ProxyIPv6(xmlrpc.Proxy):

    """
    IPv6 capable Proxy, until this Twisted issue is resolved:
    https://twistedmatrix.com/trac/ticket/6870
    """

    def __init__(self, url, lc_ipv6, **kwargs):
        xmlrpc.Proxy.__init__(self, url, **kwargs)
        self.host = lc_ipv6

def make_proxy(conf, verbose):
    ipv6_disabled = parse_bool(conf.get('DEFAULT', 'IPV6_DISABLED'))
    url = conf.get('DEFAULT', 'LAB_CONTROLLER')

    if not ipv6_disabled and twisted_version >= (12, 1):
        lc_ipv6 = has_ipv6(url)
    else:
        lc_ipv6 = None

    if lc_ipv6:
        log.info('Communicating to LC over IPv6 (%s)' % lc_ipv6)
        proxy = repeatingproxy.RepeatingProxy(ProxyIPv6(url, lc_ipv6, allowNone=True))
    else:
        # else fall back to using IPv4
        log.info('Communicating to LC over IPv4')
        proxy = repeatingproxy.RepeatingProxy(xmlrpc.Proxy(url, allowNone=True))

    if verbose:
        make_logging_proxy(proxy)
        proxy.logging_print = log.debug
    try:
        rpc_timeout = float(conf.get('DEFAULT', 'RPC_TIMEOUT'))
        proxy.set_timeout(repeatingproxy.IncreasingTimeout(rpc_timeout, max=300))
    except:
        proxy.set_timeout(None)
    proxy.serializing = True
    return proxy

def make_verbose():
    print_this = log_this(lambda s: log.debug(s), log_on=True)
    make_class_verbose(BeakerLCBackend, print_this)
    make_class_verbose(BeakerWriter, print_this)
    make_class_verbose(BeakerRecipe, print_this)
    make_class_verbose(BeakerTask, print_this)
    make_class_verbose(BeakerResult, print_this)
    make_class_verbose(BeakerFile, print_this)
    make_class_verbose(repeatingproxy.RepeatingProxy, print_this)


def make_queue(conf, runtime):
    offset = runtime.type_get('', 'journal_offs', 0)
    journal_fname = os.path.join(conf.get('DEFAULT', 'VAR_ROOT'), 'journals' , 'beakerlc.journal')
    queue = JournallingQueue(
            offset_writer=lambda offset: runtime.type_set('', 'journal_offs', offset),
            read_offset=offset,
            journal_file=open_(journal_fname, 'ab+'))
    journal_in = open_(journal_fname, 'rb')
    journal_in.seek(offset, 1)
    return dict(queue=queue, build_queue=lambda backend: journal_reader(queue, journal_in, backend))


def start_beaker_backend(conf):
    verbose = parse_bool(conf.get('DEFAULT', 'DEVEL'))
    if verbose:
        make_verbose()

    # NOTE: use verbose=verbose for runtime debugging. This is disabled by
    # default, as it may be slow and brief.
    runtime = make_runtime(conf, verbose=False)

    proxy = make_proxy(conf, verbose)

    backend = BeakerLCBackend(conf=conf, proxy=proxy, runtime=runtime,
            **make_queue(conf, runtime))

    proxy.on_idle = backend.set_idle

    simple_schedule(conf, runtime, proxy, backend)

    # Ensure memory-cache is flushed regularly.
    #
    # We do not want flush to happen too often as it hits performance and
    # this should help preventing loosing mind e.g. in case of unexpected
    # panic.
    flush_regularly = LoopingCall(backend.flush)
    flush_regularly.start(60, now=False)

    def shutdown():
        backend.close()
        runtime.close()
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)


# TODO: need to start scheduler bit here

    # Start a client:
    start_backend(backend)


def beakerlc_opts(opt, conf):
    def lc_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['LAB_CONTROLLER'] = value
    opt.add_option("-l", "--lab-controller", "--lc",
            action="callback", callback=lc_cb, type='string',
            help="Specify lab controller's URL.")
    def cs_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['COBBLER_SERVER'] = value
    opt.add_option("-S", "--cobbler-server", "--cs",
            action="callback", callback=cs_cb, type='string',
            help="Cobbler server's host name.")
    def hostname_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['HOSTNAME'] = value
    opt.add_option("-H", "--hostname",
            action="callback", callback=hostname_cb, type='string',
            help="Identify as HOSTNAME when talking to Lab Controller.")
    def digest_cb(option, opt_str, value, parser):
        # FIXME!!! check value
        conf['DIGEST'] = "no-digest"
    opt.add_option("--digest", metavar="DIGEST_METHOD",
            action="callback", callback=digest_cb, type='string',
            help="Use DIGEST_METHOD for checksums.")
    def recipeid_cb(option, opt_str, value, parser):
        tmp = int(value) # must be an integer
        conf['RECIPEID'] = value
    opt.add_option("--recipeid", metavar="RECIPEID",
            action="callback", callback=recipeid_cb, type='string',
            help="Use the RECIPEID to get the recipe.")
    return opt


def defaults():
    d = config.backend_defaults()
    cs = os.getenv('COBBLER_SERVER', '')
    lc = os.getenv('LAB_CONTROLLER', '')

    if not lc:
        if cs:
            lc = 'http://%s:8000/server' % cs
        else:
            cs = '127.0.0.1'
            lc = 'http://127.0.0.1:5222/'
    if not cs:
        cs = re.compile('^(https?://)?([^/:]+?)(:[0-9]+)?(/.*)?$').match(lc).group(2)
    d.update({
            'NAME':'beah_beaker_backend',
            'LAB_CONTROLLER':lc,
            'IPV6_DISABLED': 'False',
            'COBBLER_SERVER':cs,
            'HOSTNAME': socket.getfqdn(),
            'RECIPEID':'-1',
            'DIGEST':'no-digest',
            'RPC_TIMEOUT':'60',
            'RECIPE_UPLOAD_LIMIT':'0',
            'RECIPE_UPLOAD_LIMIT_SOFT':'0',
            'RECIPE_SIZE_LIMIT':'0',
            'RECIPE_SIZE_LIMIT_SOFT':'0',
            'RECIPE_LINK_LIMIT':'0',
            'RECIPE_LINK_LIMIT_SOFT':'0',
            'TASK_UPLOAD_LIMIT':'0',
            'TASK_UPLOAD_LIMIT_SOFT':'0',
            'TASK_SIZE_LIMIT':'0',
            'TASK_SIZE_LIMIT_SOFT':'0',
            'TASK_LINK_LIMIT':'0',
            'TASK_LINK_LIMIT_SOFT':'0',
            'FILE_UPLOAD_LIMIT':'0',
            'FILE_UPLOAD_LIMIT_SOFT':'0',
            'FILE_SIZE_LIMIT':'0',
            'FILE_SIZE_LIMIT_SOFT':'0',
            })
    return d


def configure(args=None):
    config.backend_conf(env_var='BEAH_BEAKER_CONF', filename='beah_beaker.conf',
            defaults=defaults(), overrides=config.backend_opts(args=args, option_adder=beakerlc_opts))


def main():
    from beah.core import debug
    configure()
    conf = config.get_conf('beah-backend')
    debug.setup(os.getenv("BEAH_BEAKER_DEBUGGER"), conf.get('DEFAULT', 'NAME'))
    log_handler()
    start_beaker_backend(config.get_conf('beah-backend'))
    debug.runcall(reactor.run)

