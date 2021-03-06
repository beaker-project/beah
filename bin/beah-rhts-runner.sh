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

ensure_chkconfig_on() {
  local level= service=$1
  shift
  local levels="$*"
  for level in $levels; do
    if ! chkconfig --level $level $service; then
      chkconfig --level $level $service on
      chkconfig --level $level $service || return 1
    fi
  done
  true
}

WARN_ISSUED=/var/beah/rhts-compat.warning

warn() {
  # we do not want to have the results spoiled by this, but want it reported
  # anyway!
  if false; then # && [[ ! -f $WARN_ISSUED ]]; then
    touch $WARN_ISSUED
    if [[ -f $WARN_ISSUED ]]; then
      echo -n "" | rhts-report-result $1 WARN - ${2:-0}
      return
    fi
  fi
  echo -n "" | rhts-report-result $1/WARN Pass - ${2:-0}
}

check_compat() {
  # "check rhts-compat is runing. setup and reboot if not"
  local compat_reboot_counter=/var/beah/rhts-compat.reboot
  if service rhts-compat try; then
    # ignore if following fails - it's running now
    ensure_chkconfig_on rhts-compat 3 4 5
    echo 0 > $compat_reboot_counter
    return
  else
    if chkconfig rhts-compat; then
      # if the service is not running and is scheduled to run: wait first...
      if service rhts-compat wait_try 120; then
        # ignore if following fails - it's running now
        ensure_chkconfig_on rhts-compat 3 4 5
        echo 0 > $compat_reboot_counter
        return
      fi
      if ! chkconfig rhts-compat; then
        echo "I do not like this! Someone's changing chairs under my ...!"
      fi
    fi
    local compat_reboot_count=$(cat $compat_reboot_counter)
    if [[ ${compat_reboot_count:-0} -lt 1 ]]; then
      # service is not running. Having one attempt to start on boot!
      if echo 1 > $compat_reboot_counter; then
        if chkconfig --add rhts-compat && \
            ensure_chkconfig_on rhts-compat 3 4 5; then
          echo "The rhts-compat service is set up. Rebooting..."
          echo "Optionally run 'service rhts-compat start' and kill rhts-reboot process."
          echo "Do not press C-c as adviced, please."
          beah-reboot.sh

          # in case we got here:
          local answ=$?
          echo "Wow, it escaped from infinite loop! Try 'ps -ef | grep -i copperfield'..."
          warn rhts-compat/reboot-failed $answ
        else
          echo "WARNING: Can not set the rhts-compat service."
          warn rhts-compat/service 0
        fi
      else
        echo "WARNING: could not write to '$compat_reboot_counter'."
        warn rhts-compat/counter 0
        ls -l $compat_reboot_counter
      fi
    else
      echo 2 > $compat_reboot_counter
      echo "WARNING: The rhts-compat service did not come up after reboot."
      warn rhts-compat/not-running 0
    fi

    echo "What's wrong?"
    chkconfig --list rhts-compat
    local file= opt=
    for file in /etc/init.d/rhts-compat /etc/rc*.d/*rhts-compat; do
      for opt in -l -Z; do
        ls $opt $file
      done
    done
    return 1
  fi
}

run_here() {
  BEAKERLIB_COMMAND_REPORT_RESULT=/usr/bin/rhts-report-result \
  BEAKERLIB_COMMAND_SUBMIT_LOG=/usr/bin/rhts-submit-log \
  exec tortilla run </dev/null || \
      die 1 "Can not run rhts-test-runner.sh"
}

stop_compat() {
  chkconfig rhts-compat
  local compat_scheduled=$?
  chkconfig --level 12345 rhts-compat off
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
}

run_compat() {
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

  if check_compat; then
    echo "rhts-compat service is running. Waiting for launcher being picked up."

    mv $temp_root/$(basename $shenv) $shenv || die 1 "Error saving env.file"
    mv $temp_file $launcher || die 1 "Error saving launcher"
    rm -rf $temp_root

    # TODO "set traps"
    # - on kill: kill launcher, remove pid file. Shall we remove launcher here?

    # Waiting to get killed. Nothing interesting ahead.
    set +x
    while true; do
      heartbeat
      sleep 300
    done
    echo "Whoa, another escaper from infinite loop!"
    exit 1
  else
    rm -rf $temp_root
    false
  fi
}

main() {
  if [[ -f /etc/profile.d/task-overrides-rhts.sh ]]; then
    source /etc/profile.d/task-overrides-rhts.sh
  fi
  [[ -n $BEAH_DEBUG ]] && set -x
  if [[ -z $RHTS_OPTION_COMPATIBLE ]]; then
    if [[ -z $RHTS_OPTION_COMPAT_SERVICE ]]; then
      stop_compat
    fi
    run_here
  elif run_compat; then
    true
  else
    echo "Could not set rhts-compat, running the test here."
    # stop the service so it won't delay us anymore.
    stop_compat
    run_here
  fi
}

main

