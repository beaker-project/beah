#!/bin/bash
set -e
usage() {
    echo "Moves all builds from their *-candidate tags to *" >&2
    echo "Usage: $0 <ver-rel>, example: $0 0.7.2-1" >&2
    exit 1
}
[[ -z "$VERREL" ]] && VERREL="$1"
[[ -z "$VERREL" ]] && usage
brew move-pkg dist-3.0E-eso{-candidate,} beah-$VERREL
brew move-pkg dist-4E-eso{-candidate,} beah-$VERREL.el4
brew move-pkg dist-5E-eso{-candidate,} beah-$VERREL.el5
brew move-pkg eng-rhel-6{-candidate,} beah-$VERREL.el6eng
brew move-pkg eso-rhel-7{-candidate,} beah-$VERREL.el7
