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
NAME
       json-env - run a program in a modified environment

SYNOPSIS
       json-env [OPTIONS] [-] [=FILE | NAME=VALUE]... [COMMAND [ARG]...]

DESCRIPTION
       Set each NAME to VALUE in the environment and run COMMAND.
       This utility attempts to match env.

       -i, --ignore-environment
              start with an empty environment

       -u, --unset=NAME
              remove variable from the environment

       -d, --defaults=FILENAME
              json file with defaults. This is read before environment

       -s, --save=FILENAME
              save the resulting environment in a file

       =FILE
              json file with bindings. Bindings starting with - are negative
              bindings and remove the variable from environment
        
       Env.variables defined earlier on command line are overridden by bindings
       introduced later and override all previously defined bindings.

       A mere - implies -i.  If no COMMAND, print the resulting environment.
"""


import os
import sys
from  beah.misc.jsonenv import json
import pprint
import optparse


def opt_parser():
    parser = optparse.OptionParser()
    parser.disable_interspersed_args()
    parser.usage = "%%prog [OPTIONS] [-] [=FILE | NAME=VALUE]... [COMMAND [ARG]...]"
    parser.add_option(
            "--ignore-environment", "-i",
            action="store_true",
            dest="ignore_env",
            help="start with an empty environment",
            )
    parser.add_option(
            "--unset", "-u",
            action="append",
            metavar="NAME",
            dest="unset",
            help="remove variable from the environment",
            )
    parser.add_option(
            "--save", "-s",
            action="store",
            metavar="FILENAME",
            dest="save",
            help="save the resulting environment in a file",
            )
    parser.add_option(
            "--defaults", "-d",
            action="store",
            metavar="FILENAME",
            dest="defaults",
            help="json file with defaults. This is read before environment",
            )
    return parser


def update_env(env, negative_env, key, value):
    if key[0] == "-":
        key = key[1:].strip()
        negative_env.append(key)
        if env.has_key(key):
            del env[key]
        return
    env[key] = value


def update_env_json(env, negative_env, envfile):
    f = open(envfile, 'r')
    try:
        new_env = json.load(f)
    finally:
        f.close()
    for key in new_env.keys(): # pylint: disable=E1103
        update_env(env, negative_env, key, new_env[key])


def json_env(args):
    parser = opt_parser()
    (opts, args) = parser.parse_args(args)

    i = 0
    if len(args) > i and args[i] == '--':
        i += 1
    if len(args) > i and args[i] == '-':
        opts.ignore_env = True
        i += 1

    env = {}
    negative_env = []

    if opts.defaults:
        update_env_json(env, [], opts.defaults)

    if not opts.ignore_env:
        env.update(dict(os.environ))

    if opts.unset:
        for var in opts.unset:
            if env.has_key(var):
                del env[var]
        negative_env.extend(list(opts.unset))

    while i < len(args):
        arg = args[i]
        kv = arg.split("=", 1)
        if len(kv) < 2:
            break
        i += 1
        key = kv[0].strip()
        value = kv[1].strip()
        if key == "":
            update_env_json(env, negative_env, value)
        else:
            update_env(env, negative_env, key, value)

    if opts.save:
        f = open(opts.save, 'w+')
        try:
            db = dict(env)
            for var in negative_env:
                # save only if the variable was not reintroduced:
                if not env.has_key(var):
                    db["-" + var] = ""
            json.dump(db, f)
        finally:
            f.close()
    return (env, args[i:])


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    (env, cmdargs) = json_env(args)
    if len(cmdargs) > 0:
        cmd = cmdargs[0]
        #if debug:
        #    print >> sys.stderr, "cmd: %s" % cmd
        #    print >> sys.stderr, "cmdargs: %r" % cmdargs
        #    print >> sys.stderr, "env: %s" % env
        os.execvpe(cmd, cmdargs, env)
    else:
        pprint.pprint(env)


if __name__ == '__main__':
    main()

