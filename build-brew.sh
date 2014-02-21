#!/bin/bash
set -e
usage() {
    echo "Builds a release in Brew" >&2
    echo "Usage: $0 <ver-rel>, example: $0 0.7.2-1" >&2
    exit 1
}
[[ -z "$VERREL" ]] && VERREL="$1"
[[ -z "$VERREL" ]] && usage
tito build --rpmbuild-options "--define 'dist %nil'" --srpm
brew build --nowait dist-3.0E-eso-candidate /tmp/tito/beah-$VERREL.src.rpm
tito build --dist .el4 --srpm
brew build --nowait dist-4E-eso-candidate /tmp/tito/beah-$VERREL.el4.src.rpm
tito build --dist .el5 --srpm
brew build --nowait dist-5E-eso-candidate /tmp/tito/beah-$VERREL.el5.src.rpm
tito release -y eng-rhel-6
tito build --dist .el7 --srpm
brew build --nowait eso-rhel-7-candidate /tmp/tito/beah-$VERREL.el7.src.rpm
echo "Don't forget Fedora too!"
