#!/usr/bin/python

import os
import sys

default_groups = [ os.getegid() ]
groups = os.getgroups()
print __file__, 'groups: ', groups
if len(groups) == 0:
    print __file__, 'no groups found, defaulting to', default_groups
    os.setgroups(default_groups)

sys.stdout.flush()

if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])
else:
    print __file__, 'unexpectedly at the end of chain'

