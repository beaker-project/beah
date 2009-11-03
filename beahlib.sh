#!/bin/bash

# Beah - Test harness. Part of Beaker project.
#
# Copyright (C) 2009 Marian Csontos <mcsontos@redhat.com>
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

# FIXME: use python script instead - this is very limited.

function event()
{
        echo "[\"Event\",\"$1\",\"$(uuid)\",$2,$3,$4]"
}

function log()
{
	event log {} null "{\"log_handle\":\"\",\"message\":\"$2\",\"log_level\":$1}"
        echo "[\"Event\",\"log\",\"$(uuid)\",{},null,]"
}

function linfo()
{
        log 40 "$*"
}

function lerror()
{
        log 60 "$*"
}

export -f event log linfo lerror

