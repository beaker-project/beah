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
  local shenv="$1"
  [[ -f "$shenv" ]] || die 1 "No such env.file: '$shenv'"
  source $shenv || die 1 "Errors while sourcing '$shenv'"

  [[ -n "$LAUNCHER_PIDFILE" ]] || die 1 "Missing LAUNCHER_PIDFILE variable."
  [[ -n "$RUNNER_PIDFILE" ]] || die 1 "Missing RUNNER_PIDFILE variable."

  # "check and write PID file"
  if [[ -f $LAUNCHER_PIDFILE ]]; then
    true
    # 1. TODO: check the process is running. If not simply remove pid file and create it.
    # 2. TODO: what now?
  fi
  echo "$$" > $LAUNCHER_PIDFILE

  # TODO "set traps"
  # this shall
  # - kill rhts-test-runner.sh (will it be killed anyway?)
  # - kill rhts-compat-placeholder.sh

  # "launch"
  bash -l -c "cd $TESTPATH; exec beah-unconfined.sh rhts-test-runner.sh"
  local answ=$?

  if [[ $answ -ne 0 && $answ -ne 143 ]]; then
    echo -n "" | rhts-report-result "rhts-runner/exit" FAIL - $answ
  fi

  kill $(cat $RUNNER_PIDFILE)

  # TODO "clean-up?"
  rm -f $RUNNER_PIDFILE
  rm -f $LAUNCHER_PIDFILE

  return $answ
}

main "$@"

