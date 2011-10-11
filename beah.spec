# The following allows us to build properly on rhel3
%if "0%{?dist}" == "0"
%global __python python2.6
%global _rhel3 26
%global _py_dev 26
%else
%global _py_dev 2
%if "%{?rhel}" != "4"
%if "%{?rhel}" != "6"
%global _pylint pylint --errors-only --output-format=parseable --include-ids=y --reports=n
%endif
%endif
%endif
%global _services_restart "beah-fakelc beah-beaker-backend beah-fwd-backend"
%global _services "beah-srv %{_services_restart}"

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %global pyver %(%{__python} -c "import sys ; print sys.version[:3]")}
Summary: Test Harness. Offspring of Beaker project
Name: beah
Version: 0.6.35
Release: 1%{?dist}
URL: http://fedorahosted.org/beah
Source0: http://fedorahosted.org/releases/b/e/%{name}-%{version}.tar.gz
License: GPLv2+
Group: Development/Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot-%(%{__id_u} -n)
Prefix: %{_prefix}
BuildArch: noarch
# NOTE: lockfile seems to be the only *lock* available on all RHELs.
Requires: procmail
Requires: python%{?_rhel3}
Requires: python%{?_rhel3}-setuptools
Requires: python%{?_rhel3}-simplejson
Requires: python%{?_rhel3}-twisted-web
# We need these for EL4 and EL5.
# RHEL3 python26 includes these, but since its a versioned package doesn't provide them.
%if "0%{?dist}" != "0"
Requires: python-hashlib
Requires: python-uuid
%endif
Requires(post): chkconfig
Requires(preun): chkconfig
# This is for /sbin/service
Requires(preun): initscripts
Requires(postun): initscripts
BuildRequires: python%{?_py_dev}-devel
BuildRequires: python%{?_rhel3}-setuptools
BuildRequires: python%{?_rhel3}-simplejson
BuildRequires: python%{?_rhel3}-twisted-web
%if "0%{?dist}" != "0"
BuildRequires: python-hashlib
BuildRequires: python-uuid
%endif
%if "%{?_pylint}" != ""
BuildRequires: pylint
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

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --optimize=1 --skip-build --root $RPM_BUILD_ROOT

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
%attr(0755, root, root)%{_sysconfdir}/init.d/%{name}*
%attr(0755, root, root)%{_sysconfdir}/init.d/rhts-compat
%attr(0755, root, root)%{_bindir}/%{name}*
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

%post
for service in %{_services}; do
    /sbin/chkconfig --add $service
done

%preun
if [ $1 = 0 ]; then
    for service in %{_services}; do
        /sbin/service $service stop >/dev/null 2>&1
        /sbin/chkconfig --del $service
    done
fi

%postun
if [ "$1" -ge "1" ]; then
    for service in %{_services_restart}; do
        /sbin/service $service condrestart >/dev/null 2>&1 || :
    done
fi

%changelog
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
