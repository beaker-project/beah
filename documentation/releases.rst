Releases
--------

Beah-0.7.3
==========

Changelog

- Backend needs to listen on all interfaces, not just loopback. This fixes
  a regression in Beah 0.7.2 where multi-host testing did not work because the 
  other Beah processes in the recipe set were not reachable over the network. 
  (Contributed by Dan Callaghan in :issue:`1067745`.)

Beah-0.7.2
==========

Changelog

- Brown paper bag release: fixed a typo in ``start_task``, found by pylint.

Beah-0.7.1
==========

Changelog

- Fixed missing conversion for RHTS_PORT, which was causing TypeError when the
  RHTS_PORT task parameter was set. (Contributed by Marian Csontos in 
  :issue:`1063815`.)
- Handles any combination of IPv6 and IPv4 being enabled, including absent IPv4
  loopback address. (Contributed by Dan Callaghan in :issue:`1059479` and Amit 
  Saha in :issue:`1062896`.)

Beah-0.7.0
==========

Changelog

- IPv6 support
- Remove dependency on 'python-simplejson' on RHEL 6+, 
  Fedora

Beah-0.6.48-1
=============

Changelog

- Add a release note generator
- ControlGroup configuration option no longer valid.
- pass exception instance instead of string to Failure

Beah-0.6.47-1
=============

Changelog

- Changes to Documentation
- Add a version string.
- Add a new README and remove build.sh
- Documentation reorganization
- Add an error handler to simple_recipe
- fix RPM conditional on RHEL3 and RHEL4
