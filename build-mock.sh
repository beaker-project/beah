#!/bin/bash
set -e
usage() {
    echo "Builds test RPMs and deploys them in a Beaker installation" >&2
    echo "Usage: $0 <destination-hostname>, example: $0 beaker-devel.example.com" >&2
    exit 1
}
[[ -z "$DEST" ]] && DEST=$1
[[ -z "$DEST" ]] && usage
rm -rf tito-output
mkdir tito-output
# no RHEL3 for now, cannot get a working mock config
#tito build --test --rpm -o "$(pwd)/tito-output" --rpmbuild-options "--define 'dist %nil'" --builder mock --builder-arg mock=dist-3.0E-eso-x86_64
#scp tito-output/beah-*.noarch.rpm $DEST:/var/www/beaker/harness/RedHatEnterpriseLinux3/
tito build --test --rpm -o "$(pwd)/tito-output" --dist .el4 --builder mock --builder-arg mock=dist-4E-eso-x86_64
tito build --test --rpm -o "$(pwd)/tito-output" --dist .el5 --builder mock --builder-arg mock=dist-5E-eso-x86_64
tito build --test --rpm -o "$(pwd)/tito-output" --dist .el6eng --builder mock --builder-arg mock=eng-rhel-6-x86_64
tito build --test --rpm -o "$(pwd)/tito-output" --dist .el7eng --builder mock --builder-arg mock=eng-rhel-7-x86_64
tito build --test --rpm -o "$(pwd)/tito-output" --dist .fc19 --builder mock --builder-arg mock=fedora-19-x86_64
tito build --test --rpm -o "$(pwd)/tito-output" --dist .fc21 --builder mock --builder-arg mock=fedora-rawhide-x86_64
scp tito-output/beah-*.el4.noarch.rpm $DEST:/var/www/beaker/harness/RedHatEnterpriseLinux4/
scp tito-output/beah-*.el5.noarch.rpm $DEST:/var/www/beaker/harness/RedHatEnterpriseLinuxServer5/
scp tito-output/beah-*.el5.noarch.rpm $DEST:/var/www/beaker/harness/RedHatEnterpriseLinuxClient5/
scp tito-output/beah-*.el6eng.noarch.rpm $DEST:/var/www/beaker/harness/RedHatEnterpriseLinux6/
scp tito-output/beah-*.el7eng.noarch.rpm $DEST:/var/www/beaker/harness/RedHatEnterpriseLinux7/
scp tito-output/beah-*.fc19.noarch.rpm $DEST:/var/www/beaker/harness/Fedora19/
scp tito-output/beah-*.fc19.noarch.rpm $DEST:/var/www/beaker/harness/Fedora20/
scp tito-output/beah-*.fc21.noarch.rpm $DEST:/var/www/beaker/harness/Fedorarawhide/
ssh -t $DEST sudo bash -c '"for family in RedHatEnterpriseLinux{3,4,Server5,Client5,6,7} Fedora{19,20,rawhide} ; do createrepo --checksum sha --update --no-database /var/www/beaker/harness/\$family/ ; done"'
