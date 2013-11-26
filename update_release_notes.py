#!/usr/bin/python

"""
Script to update release notes in documentation/releases.rst

*Before* tagging the release, run this script as:

$ ./update_release_notes.py <next-release-version-string>

Example:

$ ./update_release_notes.py 0.6.47-2

The script will create a new release note entry and open the editor
for you. You will see that the git commit summary messages since the last
release tag has been filled in. You may want to keep it as it is or
add any extra information if desired. Save the file and exit.

Commit your changes and proceed with the release process.

"""
import os
import sys
import subprocess
import textwrap

def create_release_note(version_string):

    release_notes = 'documentation/releases.rst'
        # basic sanity check
    with open(release_notes) as f:
        if version_string in f.read():
            sys.exit('Release notes for %s already added.' % version_string)

    # idea stolen from tito
    with open('rel-eng/packages/beah') as f:
        last_tag = 'beah-{0}'.format(f.read().split()[0])

    default_changelog = "git log --pretty=%s  --relative {0}..{1}".format(last_tag, "HEAD")
    template = subprocess.check_output(default_changelog.split())
    template = ['- {0}\n'.format(line) for line in template.split('\n')[:-1]]
    # existing release notes
    with open(release_notes) as f:
        lines = f.readlines()
        # skip the first two lines
        # Releases:
        # ---------
        existing = lines[3:]

    # new release note
    current_note = textwrap.dedent('''\
                                   Releases
                                   --------

                                   {0}
                                   {1}

                                   Changelog

                                   {2}
                                   ''').format(version_string, ('='*len(version_string)), ''.join(template))

    # write the new release note file
    with open(release_notes, 'w') as f:
        f.write(current_note)
        f.write(''.join(existing))

    # open the editor to make changes (Add more detail?)
    # idea stolen from tito
    editor = 'vi'
    if "EDITOR" in os.environ:
        editor = os.environ["EDITOR"]
    subprocess.call(editor.split() + [release_notes])
    print 'Release note created for %s' % version_string

if __name__ == '__main__':

    if len(sys.argv) == 2:
        version_string = 'Beah-%s' % sys.argv[1]
        create_release_note(version_string)
    else:
        sys.exit('Must supply version as the first argument')
