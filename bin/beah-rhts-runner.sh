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

check_compat() {
  # "check rhts-compat is runing. setup and reboot if not"
  if service rhts-compat status; then
    return
  else
    # if the service is not running and is scheduled to run: wait first...
    if chkconfig rhts-compat; then
      local i=0
      for i in $(seq 1 10); do
        sleep 4
        if service rhts-compat status; then
          return
        fi
      done
    fi
    chkconfig --add rhts-compat && \
    chkconfig --level 345 rhts-compat on || die 1 "Can not set the rhts-compat service."
    echo "The rhts-compat service is set up. Rebooting..."
    echo "Optionally run 'service rhts-compat start' and kill rhts-reboot process."
    echo "Do not press C-c as adviced, please."
    beah-reboot.sh

    # in case we got here:
    local answ=$?
    echo "Wow, it escaped from infinite loop! Try 'ps -ef | grep -i copperfield'..."
    echo -n "" | rhts-report-result rhts-compat/reboot-failed WARN - $answ
    echo "Starting rhts-compat service manually: I do not want the job to fail beacause of this..."
    service rhts-compat start
  fi
}

main() {
  if [[ -f /etc/profile.d/task-overrides-rhts.sh ]]; then
    source /etc/profile.d/task-overrides-rhts.sh
  fi
  if [[ -z $RHTS_OPTION_COMPATIBLE ]]; then
    if [[ -z $RHTS_OPTION_COMPAT_SERVICE ]]; then
      chkconfig rhts-compat
      local compat_scheduled=$?
      chkconfig rhts-compat off
      # turn compat service off:
      if [[ $compat_scheduled == 0 ]]; then
        # if service was scheduled to start wait - it may be starting right
        # now...
        sleep 5
      fi
      if service rhts-compat status; then
        echo "Stopping rhts-compat service."
        service rhts-compat stop
      fi
    fi
    exec beah-initgroups.py beah-unconfined.sh /usr/bin/rhts-test-runner.sh </dev/null || \
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
      json-env - =$RHTS_ENV RUNNER_PIDFILE=$pidfile LAUNCHER_PIDFILE=$pidfile2 BEAKERLIB_COMMAND_REPORT_RESULT=/usr/bin/rhts-report-result BEAKERLIB_COMMAND_SUBMIT_LOG=/usr/bin/rhts-submit-log /bin/bash -c 'export' > $shenv || die 1 "Can not create the environment."
    fi

    # "write pid file if does not exist"
    if [[ -f $pidfile ]]; then
      true
      # 1. TODO: check the process is running. If not simply remove pid file and create it.
      # 2. TODO: what now?
    fi
    echo "$$" > $pidfile

    # "write launcher if it does not exist"
    if [[ ! -x $launcher ]]; then
      local temp_file=$(mktemp rhts-launcher.XXXXXX)
      mkdir -p $(dirname $launcher)
      echo "#!/bin/sh" > $temp_file || die 1 "Error writing launcher"
      echo "rhts-compat-runner.sh $shenv" >> $temp_file || die 1 "Error writing launcher"
      chmod a+x $temp_file || die 1 "Error chmodding launcher"
      mv $temp_file $launcher
    fi

    check_compat
    echo "rhts-compat service is running. Waiting for launcher being picked up."

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

