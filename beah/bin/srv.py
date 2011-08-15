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

import os
from twisted.internet import reactor
from beah import config
from beah.wires.internals.twserver import start_server

def main_srv(conf=None):
    """\
This is a Controller server.

Type <Ctrl-C> to exit. Alternatively issue a kill command from cmd_backend.
"""
    return start_server(conf=conf)

def main():
    from beah.core import debug
    config.beah_conf()
    conf = config.get_conf('beah')
    debug.setup(os.getenv("BEAH_SRV_DEBUGGER"), conf.get('DEFAULT', 'NAME'))
    print main_srv.__doc__
    main_srv(conf=conf)
    debug.runcall(reactor.run)

if __name__ == '__main__':
    main()

