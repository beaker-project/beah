Releases
--------

Beah-0.7.6
==========

Changelog

- Add before and conflicts on shutdown.target for beah systemd services. This
  will allow the Beah services to be shutdown cleanly.
- Currently Beah considers a Task runner exit as task completion. Starting
  this release, Beah will ignore a task exit when a system reboots via
  ``rhts-reboot`` and hence not mark it as "done". This fixes :issue:`908354`.

Beah-0.7.5
==========

Changelog

- Pass a valid Exception to errback()
- fix systemd dependencies for beah-srv.service
- don't rely on HOSTNAME env var
- SELinux policy module to allow beah to transition to unconfined
- Discard python-hashlib to enable FIPS mode on RHEL5

Beah-0.7.4
==========

Changelog

- A new config option ``IPV6_DISABLED`` will cause Beah to avoid using IPv6
  even when it is available.
- Beah now starts after systemd readahead collection is finished.

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
