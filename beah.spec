%if "%{?rhel}" == "5"
%global _pylint pylint --errors-only --output-format=parseable --include-ids=y --reports=n
%endif
%global _services_restart beah-fakelc beah-beaker-backend beah-fwd-backend
%global _services beah-srv %{_services_restart}

# Got Systemd?
%if 0%{?fedora} >= 18 || 0%{?rhel} >= 7
%global with_systemd 1
%else
%global with_systemd 0
%endif

%if 0%{?fedora} >= 21 || 0%{?rhel} >= 7
%global with_selinux_policy 1
%else
%global with_selinux_policy 0
%endif

# We need python-simplejson on RHEL 3-5
%if 0%{?fedora} >= 18 || 0%{?rhel} >= 6
%global with_simplejson 0
%else
%global with_simplejson 1
%endif

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %global pyver %(%{__python} -c "import sys ; print sys.version[:3]")}
Summary: Test Harness. Offspring of Beaker project
Name: beah
Version: 0.7.12
Release: 1%{?dist}
URL: http://fedorahosted.org/beah
Source0: http://fedorahosted.org/releases/b/e/%{name}-%{version}.tar.gz
License: GPLv2+
Group: Development/Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot-%(%{__id_u} -n)
Prefix: %{_prefix}
BuildArch: noarch

%if 0%{?fedora} >= 29 || 0%{?rhel} >= 8
BuildRequires: python2-devel
BuildRequires: python2-setuptools
BuildRequires: python2-twisted
Requires: python2-setuptools
Requires: python2-twisted
Requires: python2-systemd
%else
BuildRequires: python2-devel
BuildRequires: python-setuptools
BuildRequires: python-twisted-web
Requires: python-setuptools
Requires: python-twisted-web
%if %{with_systemd}
%if 0%{?fedora} >= 24
Requires: python2-systemd
%else
Requires: systemd-python
%endif
%endif
%if %{with_simplejson}
BuildRequires: python-simplejson
Requires: python-simplejson
%endif
%if 0%{?rhel} == 4 || 0%{?rhel} == 5
BuildRequires: python-uuid
%endif
%endif

%if %{with_systemd}
BuildRequires:          systemd
Requires(post):         systemd
Requires(pre):          systemd
Requires(postun):       systemd
%else
Requires(post): chkconfig
Requires(preun): chkconfig
# This is for /sbin/service
Requires(preun): initscripts
Requires(postun): initscripts
# /usr/bin/lockfile from procmail is used in initscripts
# (not required when using systemd)
Requires: procmail
%endif

%if "%{?_pylint}" != ""
BuildRequires: pylint
%endif

%if %{with_selinux_policy}
BuildRequires: selinux-policy-devel
%endif

%description
Beah - Test Harness.

Test Harness with goal to serve any tests and any test schedulers.
Harness consist of a server and two kinds of clients - back ends and tasks.

Back ends issue commands to Server and process events from tasks. Back ends
usually communicate with a Scheduler or interact with an User.

Tasks are events producers. Tasks are wrappers for Tests to produce stream of
events.

Powered by Twisted.

%prep
%setup -q

%build
%{__python} setup.py build
%if %{with_selinux_policy}
if [ -e "selinux/beah%{?dist}.pp" ]; then
# use pre-compiled selinux policy
    cp -p selinux/beah%{?dist}.pp selinux/beah.pp
else
    make -C selinux -f %{_datadir}/selinux/devel/Makefile
fi
%endif

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --optimize=1 --skip-build --root $RPM_BUILD_ROOT
%if %{with_selinux_policy}
install -p -m 644 -D selinux/beah.pp $RPM_BUILD_ROOT%{_datadir}/selinux/packages/%{name}/beah.pp
%endif

%check
trial beah || exit 1
%if "%{?_pylint}" != ""
%_pylint --ignored-classes=twisted.internet.reactor beah; let "$? & 3" && exit 1
%_pylint beahlib; let "$? & 3" && exit 1
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%config(noreplace) %{_sysconfdir}/%{name}*
%if %{with_systemd}
%{_unitdir}/%{name}*
%exclude %{_sysconfdir}/init.d
%if "%{_unitdir}" == "/lib/systemd/system"
%exclude /usr/lib/systemd
%else
%exclude /lib/systemd
%endif
%else
%attr(0755, root, root)%{_sysconfdir}/init.d/%{name}*
%attr(0755, root, root)%{_sysconfdir}/init.d/rhts-compat
%exclude /usr/lib/systemd
%exclude /lib/systemd
%endif
%attr(0755, root, root)%{_bindir}/%{name}*
%attr(0755, root, root)%{_bindir}/tortilla
%attr(0755, root, root)%{_bindir}/rhts-compat-runner.sh
%attr(0755, root, root)%{_bindir}/rhts-flush
%attr(0755, root, root)%{_bindir}/beat_tap_filter
%attr(0755, root, root)%{_bindir}/json-env
%{python_sitelib}/%{name}-*
%{python_sitelib}/%{name}/
%{python_sitelib}/beahlib.py*
%{_datadir}/%{name}
%doc %{_datadir}/%{name}/README
%doc %{_datadir}/%{name}/COPYING
%doc %{_datadir}/%{name}/LICENSE
%{_libexecdir}/%{name}
%attr(0755, root, root)%{_libexecdir}/%{name}/beah-check/*
%{_var}/lib/%{name}
%{_var}/lib/%{name}/tortilla
%attr(0755, root, root)%{_var}/lib/%{name}/tortilla/wrappers.d/*
%{_var}/lib/%{name}/tortilla/order.d/*
%if %{with_selinux_policy}
%{_datadir}/selinux/packages/%{name}
%endif

%post
%if %{with_systemd}
%systemd_post %{_services}
%else
for service in %{_services}; do
    /sbin/chkconfig --add $service
done
%endif
%if %{with_selinux_policy}
if [ "$1" -le 1 ] ; then # First install
    semodule -i %{_datadir}/selinux/packages/%{name}/beah.pp || :
fi
%endif

%preun
%if %{with_systemd}
%systemd_preun %{_services}
%else
if [ $1 = 0 ]; then
    for service in %{_services}; do
        /sbin/service $service stop >/dev/null 2>&1
        /sbin/chkconfig --del $service
    done
fi
%endif
%if %{with_selinux_policy}
if [ "$1" -lt 1 ] ; then # Final removal
    semodule -r beah || :
fi
%endif

%postun
%if %{with_systemd}
%systemd_postun_with_restart %{_services_restart}
%else
if [ "$1" -ge "1" ]; then
    for service in %{_services_restart}; do
        /sbin/service $service condrestart >/dev/null 2>&1 || :
    done
fi
%endif
%if %{with_selinux_policy}
if [ "$1" -ge 1 ] ; then # Upgrade
    semodule -i %{_datadir}/selinux/packages/%{name}/beah.pp || :
fi
%endif

%changelog
* Wed Feb 07 2018 Dan Callaghan <dcallagh@redhat.com> 0.7.12-1
- fix service ordering (dcallagh@redhat.com)
- clarify log messages (dcallagh@redhat.com)

* Fri Jan 13 2017 Dan Callaghan <dcallagh@redhat.com> 0.7.11-1
- support Skip result (dcallagh@redhat.com)
- only require python-uuid on RHEL4 and RHEL5 (dcallagh@redhat.com)

* Fri Aug 12 2016 Dan Callaghan <dcallagh@redhat.com> 0.7.10-1
- Waiting and Running are not the only states for an incomplete recipe
  (dcallagh@redhat.com)

* Mon Sep 14 2015 Dan Callaghan <dcallagh@redhat.com> 0.7.9-2
- use pre-built selinux policy module (mjia@redhat.com)

* Wed Aug 26 2015 Dan Callaghan <dcallagh@redhat.com> 0.7.9-1
- make systemd capture output and send it to the console (dcallagh@redhat.com)
- handle /dev/console errors (dcallagh@redhat.com)
- start services after network-online.target (dcallagh@redhat.com)
- systemd unit files should not be executable (dcallagh@redhat.com)
- need to BuildRequire systemd, not systemd-units (dcallagh@redhat.com)

* Tue Nov 25 2014 Dan Callaghan <dcallagh@redhat.com> 0.7.8-1
- remove readahead ordering hacks (dcallagh@redhat.com)

* Thu Oct 16 2014 Dan Callaghan <dcallagh@redhat.com> 0.7.7-1
- use Wants= instead of Requires= for systemd dependencies
  (dcallagh@redhat.com)
- build selinux policy on RHEL7 also (dcallagh@redhat.com)

* Tue Jul 08 2014 Amit Saha <asaha@redhat.com> 0.7.6-1
- Release note for 0.7.6 (asaha@redhat.com)
- Add before and conflicts on shutdown.target for beah systemd services
  (asaha@redhat.com)
- Handle "rebooting" event generated by rhts-reboot (asaha@redhat.com)

* Mon Jun 16 2014 Amit Saha <asaha@redhat.com> 0.7.5-1
- Pass a valid Exception to errback() (asaha@redhat.com)
- fix systemd dependencies for beah-srv.service (dcallagh@redhat.com)
- don't rely on HOSTNAME env var (dcallagh@redhat.com)
- SELinux policy module to allow beah to transition to unconfined
  (dcallagh@redhat.com)
- Discard python-hashlib to enable FIPS mode on RHEL5 (mcsontos@redhat.com)

* Wed Apr 16 2014 Dan Callaghan <dcallagh@redhat.com> 0.7.4-1
- Implement a new config option to use IPv4 only (asaha@redhat.com)
- Start beah services after readahead collection exits (asaha@redhat.com)

* Mon Feb 24 2014 Dan Callaghan <dcallagh@redhat.com> 0.7.3-1
- RHBZ#1067745 backend needs to listen on all interfaces, not localhost
  (dcallagh@redhat.com)

* Wed Feb 12 2014 Dan Callaghan <dcallagh@redhat.com> 0.7.2-1
- fix typo in start_task (dcallagh@redhat.com)

* Wed Feb 12 2014 Dan Callaghan <dcallagh@redhat.com> 0.7.1-1
- Fix missing conversion for RHTS_PORT env.variable (mcsontos@redhat.com)
- handle any combination of IPv6 and IPv4 being enabled (dcallagh@redhat.com)
- Beah should work when kernel has ipv6.disable=1 (asaha@redhat.com)

* Thu Jan 30 2014 Amit Saha <asaha@redhat.com> 0.7-1
- Release notes for new major release - 0.7.0 (asaha@redhat.com)
- Admin guide: Documentation for IPv6 functionality (asaha@redhat.com)
- IPv6 support (asaha@redhat.com)
- Use 'basestring' instead of str/unicode (asaha@redhat.com)
- Remove dependency on 'python-simplejson' (asaha@redhat.com)

* Mon Dec 02 2013 Dan Callaghan <dcallagh@redhat.com> 0.6.48-1
- Add a release note generator (asaha@redhat.com)
- ControlGroup configuration option no longer valid. (asaha@redhat.com)
- pass exception instance instead of string to Failure (dcallagh@redhat.com)

* Thu Nov 14 2013 Raymond Mancy <rmancy@redhat.com> 0.6.47-1
- Changes to Documentation (asaha@redhat.com)
- Add a version string. (asaha@redhat.com)
- Add a new README and remove build.sh (asaha@redhat.com)
- Documentation reorganization (asaha@redhat.com)
- Add an error handler to simple_recipe (asaha@redhat.com)
- fix RPM conditional on RHEL3 and RHEL4 (dcallagh@redhat.com)

* Tue Oct 01 2013 Dan Callaghan <dcallagh@redhat.com> 0.6.46-2
- beah does not require procmail (lockfile) on RHEL7 or Fedora
  (dcallagh@redhat.com)

* Tue Jul 30 2013 Dan Callaghan <dcallagh@redhat.com> 0.6.46-1
- fix service scriptlets for systemd (dcallagh@redhat.com)
- Keep a guest recipe's hypervisor fqdn in an env variable (rmancy@redhat.com)
- a bit of extra debug logging to help diagnose bug 977586
  (dcallagh@redhat.com)

* Fri Jun 07 2013 Amit Saha <asaha@redhat.com> 0.6.45-1
- Merge "recipe XML is really bytes, even though Beaker returns it in an XML-
  RPC string" (dcallagh@redhat.com)
- depend on time-sync.target (bpeck@redhat.com)
- recipe XML is really bytes, even though Beaker returns it in an XML-RPC
  string (dcallagh@redhat.com)

* Fri Apr 05 2013 Dan Callaghan <dcallagh@redhat.com> 0.6.44-1
- fetch roles at the start of every task (dcallagh@redhat.com)

* Mon Mar 11 2013 Dan Callaghan <dcallagh@redhat.com> 0.6.43-2
- beah-srv: let systemd kill only the main process (jstancek@redhat.com)

* Mon Jan 14 2013 Nick Coghlan <ncoghlan@redhat.com> 0.6.43-1
- Return without abort only when task has completed. (asaha@redhat.com)

* Mon Dec 03 2012 Dan Callaghan <dcallagh@redhat.com> 0.6.42-2
- fix yum argument order for RHEL3/4 (dcallagh@redhat.com)

* Fri Nov 23 2012 Raymond Mancy <rmancy@redhat.com> 0.6.42-1
- Always enable beaker repos when installing tests (ncoghlan@redhat.com)

* Tue Nov 06 2012 Dan Callaghan <dcallagh@redhat.com> 0.6.41-1
- allow task RPMs to be installed from any repo (dcallagh@redhat.com)
- look up recipes by ID, not hostname (dcallagh@redhat.com)
- move harness files from under /tmp to /mnt/testarea (bpeck@redhat.com)
- Change bogus warn result to pass (mcsontos@redhat.com)

* Fri Aug 03 2012 Bill Peck <bpeck@redhat.com> 0.6.40-1
- spec file fix for f16 (bpeck@redhat.com)

* Fri Aug 03 2012 Bill Peck <bpeck@redhat.com> 0.6.39-1
- tests don't run in root cpu cgroup with systemd (bpeck@redhat.com)
- tito config for releasing in dist-git (dcallagh@redhat.com)

* Wed Mar 21 2012 Bill Peck <bpeck@redhat.com> 0.6.38-1
- fix pylint error (bpeck@redhat.com)
- Fix leaking file-descriptors causing EWD (mcsontos@redhat.com)
- Fix incompatibility introduced by Twisted 11.1 (mcsontos@redhat.com)

* Tue Mar 20 2012 Bill Peck <bpeck@redhat.com> 0.6.37-1
- Add tortilla wrappers to beah harness (bpeck@redhat.com)

* Tue Mar 20 2012 Bill Peck <bpeck@redhat.com> 0.6.36-1
- limit pylint to rhel5 (bpeck@redhat.com)
- bz737540 - missing links to beah-srv in rc.d (mcsontos@redhat.com)

* Tue Oct 11 2011 Marian Csontos <mcsontos@redhat.com> 0.6.35-1
- Fix errors reported by pylint
- Mask false positives reported by pylint
- Add pylint to check phase in the spec
- Replace incomprehensible scheduling code

* Sat Oct 01 2011 Marian Csontos <mcsontos@redhat.com> 0.6.34-2
- Fix spec file: %% should be escaped

* Sat Oct 01 2011 Marian Csontos <mcsontos@redhat.com> 0.6.34-1
- Write runtime data on new task
- Bug 737540 - Fix services not added correctly in spec file
- Use trial for testing
- Add %%check to spec file to run tests when building RPM
- Fix some errors found by pylint
- Remove default options from conf.files
- Fix id's reported to beaker by aborts
- Fix beah-check gzip logs.tar.gz not gzipped

* Thu Sep 15 2011 Marian Csontos <mcsontos@redhat.com> 0.6.33-1
- bz737540 - Harness does not restart the task after reboot
  - Revert "bz711270 - use non-standard lockfiles"

* Wed Sep 07 2011 Marian Csontos <mcsontos@redhat.com> 0.6.32-1
- Bug 683184 - [Beaker][Harness] External Watchdog killing "finished" recipes
  - Added set_timeout and kill events.
- Fixed misplaced false positive warning

* Tue Jul 19 2011 Marian Csontos <mcsontos@redhat.com> 0.6.31-1
- bz722288 - report bytes transferred
- bz722387 - soft limits ignored

* Fri Jul 08 2011 Marian Csontos <mcsontos@redhat.com> 0.6.30-2
- bz719623 - missing dependency (lockfile)

* Thu Jul 07 2011 Marian Csontos <mcsontos@redhat.com> 0.6.30-1
- bz718313 - use recipe_id to query the recipe

* Tue Jun 28 2011 Marian Csontos <mcsontos@redhat.com> 0.6.29-1
- 711270 - improvements in rhts-compat

* Tue Jun 07 2011 Marian Csontos <mcsontos@redhat.com> 0.6.28-1
- 680068 - fail fast - do not repeat yum
- 711270 - system will reboot in a infinite loop

* Wed Jun 01 2011 Marian Csontos <mcsontos@redhat.com> 0.6.27-1
- 705026 - Pending launchers causing EWD
- 706026 - runners: initialize supplementary groups (jstancek@redhat.com)
- fix to allow beakerlib to report results via rhts. (bpeck@redhat.com)

* Tue May 03 2011 Marian Csontos <mcsontos@redhat.com> 0.6.26-1
- Improved logging: redirect to /dev/console
- Fixed missing LICENSE and COPYING breaking sdist

* Tue Apr 05 2011 Marian Csontos <mcsontos@redhat.com> 0.6.25-1
- bz688122 - ks-templates: beah services usage
- Improved fedora packaging guidelines compliancy
- Fixed rhts-compat service may not stop on task start
* Tue Mar 22 2011 Marian Csontos <mcsontos@redhat.com> 0.6.24-1
- bz679824 - start backends after NetworkManager
- Watchdog handling
- Waiting for NetworkManager only if active
- Fixed race condition causing External Watchdog

* Tue Mar 01 2011 Bill Peck <bpeck@redhat.com> 0.6.23-1
- bz681005 - Recipes not completing as expected (mcsontos@redhat.com)

* Wed Feb 23 2011 Marian Csontos <mcsontos@redhat.com> 0.6.22-1
- bz677717 - issue when running in rhts compat mode
- bz601126 - $HOME variable not set

* Tue Jan 25 2011 Marian Csontos <mcsontos@redhat.com> 0.6.21-1
- Fixed: rhts-compat uses login shell and correct PWD
- bz669665 - Run rhts tasks in unconfined context
- bz668854 - Update beah to call uuid.uuid4()
- bz666980 - Use rhts-compat service by default

* Tue Jan 04 2011 Marian Csontos <mcsontos@redhat.com> 0.6.20-1
- dev-env: fakelc handling watchdog better
- Make a difference between finished and completed task
- Fixed: skipping invalid entries in journal
- Fixed: process extend_watchog read from journal

* Wed Nov 24 2010 Marian Csontos <mcsontos@redhat.com> 0.6.19-1
- Added option for stronger AVC checks (mcsontos@redhat.com)

* Tue Nov 09 2010 Marian Csontos <mcsontos@redhat.com> 0.6.18-1
- Preserve config files on update
- Fixed corruption on system-crash
- Added flush capability
- Fixed abort not working
- Added /sbin to PATH
- Use RhtsOptions and Environment from metadata

* Wed Oct 27 2010 Marian Csontos <mcsontos@redhat.com> 0.6.17-1
- Added beah-check: harness problem reporting tool
- RHTS compatibility
- Export environment

* Wed Oct 13 2010 Marian Csontos <mcsontos@redhat.com> 0.6.16-1
- Added: caps on file size/count
- beaker-backend broken into smaller pieces
- beahlib: python bindings
- beaker-backend: task_start call must pass.
- RepeatingProxy: per-call on-failure repeating

* Tue Sep 14 2010 Marian Csontos <mcsontos@redhat.com> 0.6.15-1
- Caching recipe and using task_info to get status
- Added Abort-Task
- Added beahsh abort_* sub-commands

* Tue Aug 31 2010 Marian Csontos <mcsontos@redhat.com> 0.6.14-1
- rhts-wrapper: default Fail result if no result is reported by task
- Improved exit-code handling

* Sun Aug 15 2010 Marian Csontos <mcsontos@redhat.com> 0.6.13-1
- beaker: Use no-digest by default (mcsontos@redhat.com)

* Tue Aug 10 2010 Marian Csontos <mcsontos@redhat.com> 0.6.12-1
- Added: timeout and repeat RPCs

* Mon Aug 02 2010 Marian Csontos <mcsontos@redhat.com> 0.6.11-1
- Fixed: beaker-backend handling abort recipe-set

* Tue Jul 27 2010 Marian Csontos <mcsontos@redhat.com> 0.6.10-1
- Added defaults for HOME and LANG

* Mon Jul 26 2010 Marian Csontos <mcsontos@redhat.com> 0.6.9.1-1
- reverted XML-RPC timeout
* Tue Jul 20 2010 Marian Csontos <mcsontos@redhat.com> 0.6.9-1
- Fixed bug in factory method used to create events breaking MH jobs
* Mon Jul 19 2010 Marian Csontos <mcsontos@redhat.com> 0.6.8-1
- Environment: RHTS launcher uses login shell
- handle Null/None in responses from LC
- improved robustness
  - added timeout to XML-RPC calls to LC
  - increased watchdog_time once the test is complete to allow results
    submission
- make harness slightly more verbose

* Fri Jul 02 2010 Marian Csontos <mcsontos@redhat.com> 0.6.7-1
- Configurable digest method (BZ 543061)
- Added list variables, persistent sync states (BZ 601471)
- Changed: use 127.0.0.1 instead of localhost (BZ 608684)

* Mon Jun 21 2010 Marian Csontos <mcsontos@redhat.com> 0.6.6-1
- Fixed: use /dev/null for stdin
- Fixed: harness becoming unresponsive
- Fixed: yum will retry getting the task
- Added: Use no digest by default - fixing FIPS issues
* Mon Jun 14 2010 Marian Csontos <mcsontos@redhat.com> 0.6.5-1
- Fixed: task reports start multiple times to beaker
- Fixed: a bug in logging code

* Sat Jun 05 2010 Marian Csontos <mcsontos@redhat.com> 0.6.3-1
- Fixed: clean-up files for unix sockets on start-up
- Added: reasonable default for TERM
- Fixed: typo in beah-data-root definition
- Fixed: an error in beaker-backend error logging

* Mon May 10 2010 Marian Csontos <mcsontos@redhat.com> 0.6.2-2
- Sorted out rpmlint warnings. (mcsontos@redhat.com)

* Fri May 07 2010 Marian Csontos <mcsontos@redhat.com> 0.6.2-1
- Fix: Sync version in setup.py with tito (mcsontos@redhat.com)
- Added: tito metadata (bpeck@redhat.com)
- Added: proper spec file (bpeck@redhat.com)
- Fix: makedirs in race causing crash (mcsontos@redhat.com)

* Tue May 04 2010 Marian Csontos <mcsontos@redhat.com> 0.6.1-2
- Use ReleaseTagger as default on the branch. (mcsontos@redhat.com)

* Mon May 03 2010 Bill Peck <bpeck@redhat.com> 0.6-1
- Initial spec file and use of tito for tagging and building.
