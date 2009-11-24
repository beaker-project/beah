#!/bin/sh

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

# FIXME:
# - change "/usr/bin/env python" to "$PYBIN" (full path)
#   - "/usr/bin/env python2.5" does not work in a_task :-(
#   - This should be done by setup.py!

(

## BEAH_ROOT - directory used to store downloaded files and for building
## components.
BEAH_ROOT=/root/beah

## PYTHON:
## PY_VER - version of python to build. Uncomment to include python in
## installation.
#PY_VER=2.5 # This is known to work on RHEL4.8
PY_VER=2.6.2

## PYBIN_NAME - python interpreter binary to install harness to.
PYBIN_NAME=python2.6

## ZOPE INTERFACE:
## ZI_VER - version of zope-interface to download and build. Uncomment to
## include zope-interface in installation.
ZI_VER=3.3.0

## TWISTED:
## TW_VER - version of Twisted framework to download and build. Uncomment to
## include Twisted in installation.
TW_VER=8.2.0

## SIMPLEJSON:
## TW_VER - version of simplejson module to download and build. Uncomment to
## include simplejson in installation.
SJ_VER=2.0.9

## GIT:
## GIT_VER - version of git to download and build. Uncomment to include git in
## installation.
## this did not work on 4.8
#GIT_VER=1.6.4.1

## BEAKER:
#BKR=

################################################################################

mkdir -p $BEAH_ROOT
pushd $BEAH_ROOT

################################################################################
# BUILD AND INSTALL NEWER PYTHON (E.G. 2.5):
################################################################################
if [[ -n "$PY_VER" ]]; then
mkdir python
pushd python

(
wget http://www.python.org/ftp/python/${PY_VER}/Python-${PY_VER}.tar.bz2 && \
tar xvjf Python-${PY_VER}.tar.bz2 && \
cd Python-${PY_VER} && \
./configure && \
make && \
{ make test || true; } && \
make altinstall
) | tee ${BEAH_ROOT}/python.out 2> ${BEAH_ROOT}/python.err

PY_OK=$?

popd
else
PY_OK=0
fi

## PYBIN - full name of python binary. See PYBIN_NAME.
PYBIN=`which $PYBIN_NAME`

################################################################################
# BUILD AND INSTALL ZOPE.INTERFACE:
################################################################################
if [[ "$PY_OK" && -n "$ZI_VER" ]]; then
mkdir zope
pushd zope

(
wget http://www.zope.org/Products/ZopeInterface/${ZI_VER}/zope.interface-${ZI_VER}.tar.gz && \
tar xvzf zope.interface-${ZI_VER}.tar.gz && \
cd zope.interface-${ZI_VER} && \
$PYBIN setup.py build && \
$PYBIN setup.py install
) | tee ${BEAH_ROOT}/zope-interface.out 2> ${BEAH_ROOT}/zope-interface.err

ZI_OK=$?

popd
else
ZI_OK=0
fi

################################################################################
# BUILD AND INSTALL TWISTED:
################################################################################
if [[ "$ZI_OK" && -n "$TW_VER" ]]; then
mkdir twisted
pushd twisted

(
wget http://tmrc.mit.edu/mirror/twisted/Twisted/8.2/Twisted-${TW_VER}.tar.bz2 && \
tar xvjf Twisted-${TW_VER}.tar.bz2 && \
cd Twisted-${TW_VER} && \
$PYBIN setup.py install
) | tee ${BEAH_ROOT}/twisted.out 2> ${BEAH_ROOT}/twisted.err

TW_OK=$?

popd
else
TW_OK=0
fi

################################################################################
# BUILD AND INSTALL GIT:
################################################################################
if [[ -n "$GIT_VER" ]]; then
mkdir git
pushd git

(
wget http://kernel.org/pub/software/scm/git/git-${GIT_VER}.tar.bz2 && \
tar xvjf git-${GIT_VER}.tar.bz2 && \
cd git-${GIT_VER} && \
make configure && \
./configure --prefix=/usr/local && \
make all doc && \
make check && \
make install
) | tee ${BEAH_ROOT}/git.out 2> ${BEAH_ROOT}/git.err

GIT_OK=$?

popd
else
GIT_OK=0
fi

################################################################################
# BUILD AND INSTALL SIMPLEJSON:
################################################################################
if [[ -n "$SJ_VER" ]]; then
mkdir simplejson
pushd simplejson

(
wget http://pypi.python.org/packages/2.6/s/setuptools/setuptools-0.6c9-py2.6.egg && \
chmod 700 setuptools-0.6c9-py2.6.egg && \
./setuptools-0.6c9-py2.6.egg && \
\
wget http://pypi.python.org/packages/source/s/simplejson/simplejson-2.0.9.tar.gz && \
tar xvzf simplejson-${SJ_VER}.tar.gz && \
cd simplejson-${SJ_VER} && \
$PYBIN setup.py build && \
$PYBIN setup.py install
) | tee ${BEAH_ROOT}/simplejson.out 2> ${BEAH_ROOT}/simplejson.err

SJ_OK=$?

popd
else
SJ_OK=0
fi

if [[ -n "$BKR" ]]; then
git clone --depth 1 http://git.fedorahosted.org/git/beaker.git
fi


################################################################################
# SUMMARY:
################################################################################
if [[ "$PY_OK" -eq 0 ]]; then
	echo "Python installed OK"
else
	echo "Python not installed"
fi

if [[ "$ZI_OK" -eq 0 ]]; then
	echo "zope.interface installed OK"
else
	echo "zope.interface not installed"
fi

if [[ "$TW_OK" -eq 0 ]]; then
	echo "Twisted installed OK"
else
	echo "Twisted not installed"
fi

if [[ "$SJ_OK" -eq 0 ]]; then
	echo "simplejson installed OK"
else
	echo "simplejson not installed"
fi

if [[ "$GIT_OK" -eq 0 ]]; then
	echo "Git installed OK"
else
	echo "Git not installed"
fi

################################################################################
popd

)

