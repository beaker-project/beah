#!/bin/bash

_is_rhfamily() {
  local family=$1
  local op=$2
  local ver=$3
  shift 3
  if ! rpm -q ${family}-release &> /dev/null; then
    return 1
  fi
  if [[ -n "$op" && -n "$ver" ]]; then
    eval "[[ $(rpm -q --qf="%{VERSION}" ${family}-release) $op $ver ]]"
  else
    false
  fi
}
is_rhel() { _is_rhfamily redhat "$1" "$2"; }
is_fedora() { _is_rhfamily fedora "$1" "$2"; }
is_centos() { _is_rhfamily centos "$1" "$2"; }

function _runcon_unconfined_cmd() {
  # Determine correct SELinux context for runcon
  local suser='root'
  local srole='system_r'
  local stype='unconfined_t'
  local additional='-l s0'
  if is_rhel -ge 6 || is_fedora -ge 12; then
    suser='unconfined_u'
    srole='unconfined_r'
    additional='-l s0-s0:c0.c1023'
  elif is_rhel -le 4; then
    additional=''
  fi
  echo runcon -u $suser -r $srole -t $stype $additional
}

function runcon_unconfined() {
  local runcon_cmd=$(_runcon_unconfined_cmd)
  if $runcon_cmd -- true; then
    # Run command with SELinux context of the root
    exec $runcon_cmd -- "$@"
  else
    echo "-- WARNING: '$runcon_cmd -- true' failed. Running in default context!"
    exec "$@"
  fi
}

if selinuxenabled; then
  runcon_unconfined "$@"
else
  exec "$@"
fi

