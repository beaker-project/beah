#!/bin/bash

################################################################################
# Preface:
################################################################################

help_msg() {
  usage $0
  cat <<END

Description: This script will run instead of rhts-test-runner.sh

It's a placeholder which will run untill launcher is finished.

END
}

usage() {
  echo "Usage: $1 [OPTIONS]"
}

if [[ "$1" == "--help" || "$1" == "-h" ]]; then
  help_msg $0
  exit 0
fi

################################################################################
# Auxiliary:
################################################################################

TODO() {
  die 1 "NotImplementedError: $*"
}

backtrace() {
  # TODO "Write a callstack."
  true
}

die() {
  local rc=$1
  shift
  local msg="$*"
  if [[ -z "$msg" ]]; then
    msg="Sorry, something went wrong. Bailing out..."
  fi
  echo "$msg" >&2
  backtrace
  if [[ "$rc" != "0" ]]; then
    exit $rc
  fi
}

################################################################################
# Main:
################################################################################

# This is to be personalized...
heartbeat() {
  true
}

main() {
  if [[ -f /etc/profile.d/task-overrides-rhts.sh ]]; then
    source /etc/profile.d/task-overrides-rhts.sh
  fi
  if [[ -z $RHTS_OPTION_COMPATIBLE ]]; then
    exec /usr/bin/rhts-test-runner.sh </dev/null || \
        die 1 "Can not run rhts-test-runner.sh"
  else
    local compat_root=$BEAH_ROOT/var/beah/rhts-compat
    local launcher=$compat_root/launchers/launcher-$TASKID.sh
    local pidfile=$compat_root/runner-$TASKID.pid
    local pidfile2=$compat_root/launcher-$TASKID.pid
    local shenv=$compat_root/env-$TASKID.sh

    mkdir -p $compat_root &>/dev/null
    [[ -d $compat_root ]] || die 1 "Directory '$compat_root' does not exist."

    if [[ ! -f $shenv ]]; then
      json-env - =$RHTS_ENV RUNNER_PIDFILE=$pidfile LAUNCHER_PIDFILE=$pidfile2 /bin/bash -c 'export' > $shenv || die 1 "Can not create the environment."
    fi

    # "write launcher if it does not exist"
    if [[ ! -x $launcher ]]; then
      mkdir -p $(dirname $launcher)
      echo "#!/bin/sh" > $launcher || die 1 "Error writing launcher"
      echo "rhts-compat-runner.sh $shenv" >> $launcher || die 1 "Error writing launcher"
      chmod a+x $launcher || die 1 "Error chmodding launcher"
    fi

    # "check rhts-compat is runing. setup and reboot if not"
    if service rhts-compat status; then
      echo "rhts-compat service is running. Waiting for launcher being picked up."
    else
      chkconfig --add rhts-compat && \
      chkconfig rhts-compat on || die "Can not set the rhts-compat service."
      echo "The rhts-compat service is set up. Rebooting..."
      echo "Optionally run 'service rhts-compat start' and kill rhts-reboot process."
      echo "Do not press C-c as adviced, please."
      beah-reboot.sh
    fi

    # "write pid file if does not exist"
    if [[ -f $pidfile ]]; then
      true
      # 1. TODO: check the process is running. If not simply remove pid file and create it.
      # 2. TODO: what now?
    fi
    echo "$$" > $pidfile

    # TODO "set traps"
    # - on kill: kill launcher, remove pid file. Shall we remove launcher here?

    # "run until killed"
    while true; do
      heartbeat
      sleep 300
    done
  fi
}

main "$@"

