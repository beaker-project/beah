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
    BEAKERLIB_COMMAND_REPORT_RESULT=/usr/bin/rhts-report-result \
    BEAKERLIB_COMMAND_SUBMIT_LOG=/usr/bin/rhts-submit-log \
    exec beah-initgroups.py beah-unconfined.sh /usr/bin/rhts-test-runner.sh </dev/null || \
        die 1 "Can not run rhts-test-runner.sh"
  else
    local compat_root=$BEAH_ROOT/var/run/beah/rhts-compat
    local launcher=$compat_root/launchers/launcher-$TASKID.sh
    local shenv=$compat_root/env-$TASKID.sh

    mkdir -p $compat_root/launchers &>/dev/null
    [[ -d $compat_root/launchers ]] || die 1 "Directory '$compat_root/launchers' does not exist."

    cd $compat_root
    local temp_root=$(mktemp -d rhts-compat-temp.XXXXXX)
    [[ -d $temp_root ]] || die 1 "Directory '$temp_root' does not exist."

    json-env - \
      BEAKERLIB_COMMAND_REPORT_RESULT=/usr/bin/rhts-report-result \
      BEAKERLIB_COMMAND_SUBMIT_LOG=/usr/bin/rhts-submit-log \
      =$RHTS_ENV RUNNER_PID=$$ RUNNER_FILE="beah-rhts-runner.sh" \
      /bin/bash -c 'export' > $temp_root/$(basename $shenv) || die 1 "Can not create the environment."

    local temp_file=$temp_root/$(basename $launcher)
    echo "#!/bin/sh" > $temp_file || die 1 "Error writing launcher"
    echo "exec rhts-compat-runner.sh $shenv \$0" >> $temp_file || die 1 "Error writing launcher"
    chmod a+x $temp_file || die 1 "Error chmodding launcher"

    if [[ -x $launcher ]]; then
      echo "INFO: Launcher '$launcher' exists. The file will be replaced."
      rm -f $launcher
    fi
    if [[ -f $shenv ]]; then
      echo "INFO: Env.file '$shenv' exists. The file will be replaced."
      rm -f $shenv
    fi

    mv $temp_root/$(basename $shenv) $shenv || die 1 "Error saving env.file"
    mv $temp_file $launcher || die 1 "Error saving launcher"

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

