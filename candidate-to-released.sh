#!/bin/bash
set -e
usage() {
    echo "Moves all builds from their *-candidate tags to *" >&2
    echo "Usage: $0 <ver-rel>, example: $0 0.7.2-1" >&2
    exit 1
}
[[ -z "$VERREL" ]] && VERREL="$1"
[[ -z "$VERREL" ]] && usage
/usr/bin/python2 /usr/bin/koji -p brew move-pkg beaker-harness-rhel-4{-candidate,} beah-$VERREL.el4bkr
/usr/bin/python2 /usr/bin/koji -p brew move-pkg beaker-harness-rhel-5{-candidate,} beah-$VERREL.el5bkr
/usr/bin/python2 /usr/bin/koji -p brew move-pkg beaker-harness-rhel-6{-candidate,} beah-$VERREL.el6bkr
/usr/bin/python2 /usr/bin/koji -p brew move-pkg beaker-harness-rhel-7{-candidate,} beah-$VERREL.el7bkr
/usr/bin/python2 /usr/bin/koji -p brew move-pkg eng-fedora-27{-candidate,} beah-$VERREL.fc27eng
/usr/bin/python2 /usr/bin/koji -p brew move-pkg eng-fedora-28{-candidate,} beah-$VERREL.fc28eng
