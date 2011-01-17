#!/bin/bash

_is_rhfamily() {
  local family=$1
  local op=$2
  local ver=$3
  shift 3
  local the_rpms="$(rpm -qa | grep ${family}-release)"
  if [[ -z $the_rpms ]]; then
    false
  else
    local the_ver="$(rpm -q --qf="%{VERSION}" $the_rpms | sed "s/^\([0-9]\+\)[^0-9]\+.*$/\1/")"
    if [[ "$op" == "show" ]]; then
      echo "Family: $family"
      echo "Version: $the_ver"
      echo "Rpms: $the_rpms"
    elif [[ -n "$op" && -n "$ver" ]]; then
      eval "[[ $the_ver $op $ver ]]"
    else
      true
    fi
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

