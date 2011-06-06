#!/bin/bash

################################################################################
# Preface:
################################################################################

usage() {
  echo "Usage: $1 ENV"
}

help_msg() {
  usage $0
  cat <<END

Description: This script runs the RHTS task outside of beah-tree.

Arguments:
ENV	-- shell environment file. This will be sourced.

END
}

if [[ -z $1 ]]; then
  echo "ERROR: Missing required argument 'ENV'" >&2
  usage $0 >&2
  exit 1
fi

if [[ $1 == --help || $1 == -h ]]; then
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

main() {
  # check and read env.
  local shenv="$1" launcher="$2"
  if [[ -x $launcher ]]; then
    # removing the launcher here, so it won't get recycled
    rm -f $launcher
  else
    echo "INFO: $0: No launcher. Executed manually?"
  fi
  if [[ -z $RUNNER_PID ]]; then
    echo "WARNING: $0: No runner. Executed manually?"
  fi
  [[ -f "$shenv" ]] || die 1 "No such env.file: '$shenv'"
  source $shenv || die 1 "Errors while sourcing '$shenv'"

  # TODO "set traps"
  # this shall
  # - kill rhts-test-runner.sh (will it be killed anyway?)
  # - kill rhts-compat-placeholder.sh

  # "launch"
  LAUNCHER_PID=$$ LAUNCHER_FILE=rhts-compat-runner.sh \
    bash -l -c "cd $TESTPATH; exec beah-initgroups.py beah-unconfined.sh rhts-test-runner.sh"
  local answ=$?

  if [[ $answ -ne 0 && $answ -ne 143 ]]; then
    echo -n "" | rhts-report-result "rhts-runner/exit" FAIL - $answ
  fi

  if ps -wwo command --no-headers -p $RUNNER_PID | grep -F "$RUNNER_FILE" >/dev/null; then
    kill $RUNNER_PID
  else
    echo "WARNING: $0: Runner $RUNNER_FILE($RUNNER_PID) has finished."
  fi

  return $answ
}

if [[ -f /etc/profile.d/task-overrides-rhts.sh ]]; then
  source /etc/profile.d/task-overrides-rhts.sh
fi
main "$@"

