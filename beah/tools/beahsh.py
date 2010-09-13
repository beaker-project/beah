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



"""
This module will be used as script from shell to create events.

Usage:

beahsh [OPTIONS] COMMAND [COMMAND-OPTS] [COMMAND-ARGS]
  beahsh echo message
  beahsh pass everything is fine

beahsh -c "COMMAND [COMMAND-OPTS] [COMMAND-ARGS]"
Use argument following -c as command. This can be repeated.
  beahsh -c "log message" -c "pass everything's fine"

beahsh [OPTIONS]
Use stdin: (NOTE: NOT IMPLEMENTED!)
  beahsh <<END
  WARN warn log message
  warn have a suspicion...
  END
"""


import os
import sys
import shlex
import simplejson as json
from optparse import OptionParser
from beah.core import event
from beah.core.constants import RC, LOG_LEVEL
import beah.misc



def evt_send_stdout(evt):
    if evt:
        print(json.dumps(evt))
        return True


no_opts = OptionParser()
no_opts.disable_interspersed_args()


def proc_evt_extend_watchdog(cmd, args):
    """Extend watchdog."""
    no_opts.prog = cmd
    no_opts.usage = "%prog SECONDS"
    no_opts.description = "Extend watchdog."
    opts, args = no_opts.parse_args(args)
    if args:
        timeout = beah.misc.canonical_time(args[0])
    else:
        print >> sys.stderr, "WARNING: SECONDS not specified. Extending for 1 more day."
        timeout = 24*3600
    return [event.extend_watchdog(timeout)]


def proc_evt_nop(cmd, args):
    """Do nothing."""
    no_opts.prog = cmd
    no_opts.usage = "%prog"
    no_opts.description = "Do nothing."
    opts, args = no_opts.parse_args(args)


def proc_evt_echo(cmd, args):
    """Echo args to stdout."""
    no_opts.prog = cmd
    no_opts.usage = "%prog MESSAGE..."
    no_opts.description = "Echo args to stdout"
    opts, args = no_opts.parse_args(args)
    return [event.stdout(" ".join(args))]


def proc_evt_echo_err(cmd, args):
    """Echo args to stderr."""
    no_opts.prog = cmd
    no_opts.usage = "%prog MESSAGE..."
    no_opts.description = "Echo args to stderr"
    opts, args = no_opts.parse_args(args)
    return [event.stderr(" ".join(args))]


__TEXT_RESULT_TO_BEAH = {
        "pass": RC.PASS,
        "warn": RC.WARNING,
        "fail": RC.FAIL,
        "crit": RC.CRITICAL,
        "fata": RC.FATAL,
        "pani": RC.FATAL,
        }


result_opts = None


def _proc_evt_result(cmd, args):
    """Return a result."""
    global result_opts
    cmd = cmd.lower()
    text_result = {'warning':'warn', 'error':'fail'}.get(cmd, cmd)
    evt_result = __TEXT_RESULT_TO_BEAH.get(text_result[:4])
    if not result_opts:
        result_opts = OptionParser(usage="%prog [OPTIONS] MESSAGE",
                description="Return a %prog result.")
        result_opts.disable_interspersed_args()
        result_opts.add_option("-H", "--handle", action="store",
                dest="handle", help="result handle", type="string",
                default="")
        result_opts.add_option("-s", "--score", action="store",
                dest="score", help="result score", default="0.0", type="float")
    result_opts.prog = text_result
    opts, args = result_opts.parse_args(args)
    statistics = {}
    if opts.score:
        statistics["score"] = opts.score
    return [event.result_ex(evt_result, handle=opts.handle,
        message=" ".join(args), statistics=statistics)]


proc_evt_pass = _proc_evt_result
proc_evt_warn = _proc_evt_result
proc_evt_warning = _proc_evt_result
proc_evt_fail = _proc_evt_result
proc_evt_error = _proc_evt_result


abort_opts = None


def _proc_evt_abort(cmd, args):
    """Abort TARGETS of given type.

    If TARGETS are not given, aborts current task/recipe/recipeset as specified
    by environment."""
    global abort_opts
    cmd = cmd.lower()
    abort_type = cmd[len('abort'):]
    if abort_type.startswith('_'):
        abort_type = abort_type[1:]
    abort_type = {'r':'recipe', 'rs':'recipeset', 't':'task'}.get(abort_type, abort_type)
    if not abort_opts:
        abort_opts = OptionParser(usage="%prog [OPTIONS] [TARGETS]",
                description="Return a %prog result.")
        abort_opts.disable_interspersed_args()
        abort_opts.add_option("-m", "--message", action="store",
                dest="message", help="message to log", type="string",
                default="")
    abort_opts.prog = cmd
    opts, args = abort_opts.parse_args(args)
    if args:
        targets = args
    else:
        abort_env = {'task':'TASKID', 'recipe':'RECIPEID', 'recipeset':'RECIPESET'}[abort_type]
        target = os.getenv(abort_env)
        if target:
            targets = [target]
        else:
            targets = []
    evts = []
    for target in targets:
        evts.append(event.abort(abort_type, target=target, message=opts.message))
    return evts


proc_evt_abort_task = _proc_evt_abort
proc_evt_abort_recipe = _proc_evt_abort
proc_evt_abort_recipeset = _proc_evt_abort
proc_evt_abort_t = _proc_evt_abort
proc_evt_abort_r = _proc_evt_abort
proc_evt_abort_rs = _proc_evt_abort


__TEXT_LOG_LEVEL_TO_BEAH = {
        'lfatal':LOG_LEVEL.FATAL, 'lcritical':LOG_LEVEL.CRITICAL,
        'lerror':LOG_LEVEL.ERROR, 'lwarning':LOG_LEVEL.WARNING,
        'linfo':LOG_LEVEL.INFO, 'ldebug1':LOG_LEVEL.DEBUG1,
        'ldebug2':LOG_LEVEL.DEBUG2, 'ldebug3':LOG_LEVEL.DEBUG3, }


log_opts = None


def _proc_evt_log(cmd, args):
    """Return a log event."""
    global log_opts
    cmd = cmd.lower()
    text_level = {'log':'linfo', 'ldebug':'ldebug1', 'lwarn':'lwarning',
            'INFO':'linfo', 'ERR':'lerror', 'WARN':'lwarning',
            'DEBUG':'ldebug1'}.get(cmd, cmd)
    log_level = __TEXT_LOG_LEVEL_TO_BEAH.get(text_level)
    if not log_opts:
        log_opts = OptionParser(usage="%prog [OPTIONS] MESSAGE",
                description="Return a %prog log event.")
        log_opts.disable_interspersed_args()
        log_opts.add_option("-H", "--handle", action="store",
                dest="handle", help="log handle", type="string",
                default="")
    log_opts.prog = text_level
    opts, args = log_opts.parse_args(args)
    return [event.log(message=" ".join(args), log_level=log_level,
            log_handle=opts.handle)]


proc_evt_log = _proc_evt_log
proc_evt_lfatal = _proc_evt_log
proc_evt_lcritical = _proc_evt_log
proc_evt_lerror = _proc_evt_log
proc_evt_lwarning = _proc_evt_log
proc_evt_lwarn = _proc_evt_log
proc_evt_linfo = _proc_evt_log
proc_evt_ldebug1 = _proc_evt_log
proc_evt_ldebug2 = _proc_evt_log
proc_evt_ldebug3 = _proc_evt_log
proc_evt_ldebug = _proc_evt_log
proc_evt_ERR = _proc_evt_log
proc_evt_WARN = _proc_evt_log
proc_evt_INFO = _proc_evt_log
proc_evt_DEBUG = _proc_evt_log


def echoerr(message):
    print >> sys.stderr, message


def _run(cmd_args, evt_send, print_id):
    if not cmd_args:
        return False
    cmd = cmd_args[0]
    f = globals().get("proc_evt_"+cmd, None)
    if not f:
        echoerr("Command %s is not implemented. Command: %r" % (cmd, cmd_args))
        return False
    evts = f(cmd, cmd_args[1:])
    if evts:
        for evt in evts:
            if print_id:
                print >> sys.stderr, "id=%s" % (evt.id(),)
            evt_send(evt)
    return True


def help_commands(self, opt, value, parser, *args, **kwargs):
    doc = None
    for k in globals().keys():
        if k[:9] == "proc_evt_":
            if kwargs.get('help'):
                #doc = globals()[k].__doc__
                doc = getattr(globals()[k], "__doc__")
            if doc:
                print "%s -- %s" % (k[9:], doc)
            else:
                print k[9:]
    sys.exit(0)


def _main(args, evt_send=evt_send_stdout):
    errs = 0
    main_opts = OptionParser(
            usage="%prog [OPTIONS] COMMAND [COMMAND-OPTIONS] [COMMAND-ARGS]",
            description="""Create events to be consumed by the harness.""")
    main_opts.disable_interspersed_args()
#If there is no COMMAND specified, stdin is processed line by line.
    main_opts.add_option("-c", "--command", action="append", dest="commands",
            help="Run COMMAND. This option could be specified multiple times.",
            metavar="COMMAND", nargs=1, type="string")
    main_opts.add_option("-x", "--nostdin", action="store_true", dest="nostdin",
            help="Do not process stdin if there is no COMMAND", default=False)
    main_opts.add_option("--help-commands", action="callback", nargs=0,
            callback=help_commands, callback_kwargs={'help':True},
            help="Print short help on available commands.")
    main_opts.add_option("--list-commands", action="callback", nargs=0,
            callback=help_commands,
            help="Print list of available commands.")
    main_opts.add_option("-i", "--print-id", action="store_true",
            dest="print_id", help="Print event id on stderr.")
    main_opts.add_option("-I", "--print-all-ids", action="store_true",
            dest="print_all_ids", help="Print all event ids on stderr.")
    opts, args = main_opts.parse_args(args)
    if opts.commands:
        for line in opts.commands:
            if not _run(shlex.split(line, True), evt_send, opts.print_all_ids):
                errs += 1
    if not args:
        if not opts.nostdin:
            # FIXME: process stdin
            pass
    else:
        if not _run(args, evt_send, opts.print_id or opts.print_all_ids):
            errs += 1
    return errs


def main():
    errs = _main(sys.argv[1:])
    if errs > 0:
        print >> sys.stderr, "SUMMARY: Encounterred %s errors..." % errs
        sys.exit(1)


if __name__ == '__main__':
    main()

