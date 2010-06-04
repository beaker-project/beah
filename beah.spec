# The following allows us to build properly on rhel3
%if "0%{?dist}" == "0"
%global __python python2.6
%global _rhel3 26
%endif

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %global pyver %(%{__python} -c "import sys ; print sys.version[:3]")}
Summary: Beah - Beaker Test Harness. Part of Beaker project - http://fedorahosted.org/beaker/wiki.
Name: beah
Version: 0.6.3
Release: 1%{?dist}
URL: http://fedorahosted.org/beah
Source0: http://fedorahosted.org/releases/b/e/%{name}-%{version}.tar.gz
License: GPLv2+
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Marian Csontos <mcsontos@redhat.com>
Requires: python%{?_rhel3}
Requires: python%{?_rhel3}-setuptools
Requires: python%{?_rhel3}-simplejson 
Requires: python%{?_rhel3}-twisted-core
Requires: python%{?_rhel3}-twisted-web
Requires: python%{?_rhel3}-zope-interface
# RHEL3 python26 includes these, but since its a versioned package doesn't provide them.
%if "0%{?dist}" != "0"
Requires: python-hashlib
Requires: python-uuid
%endif
BuildRequires: python%{?_rhel3}-devel python%{?_rhel3}-setuptools

%description
Beah - Beaker Test Harness.

Ultimate Test Harness, with goal to serve any tests and any test scheduler
tools. Harness consist of a server and two kinds of clients - backends and
tasks.

Backends issue commands to Server and process events from tasks.
Tasks are mostly events producers.

Powered by Twisted.


%prep
%setup -q

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --optimize=1 --root=$RPM_BUILD_ROOT $PREFIX

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{_sysconfdir}/%{name}*
%{_sysconfdir}/init.d/%{name}*
%attr(0755, root, root)%{_bindir}/%{name}*
%attr(0755, root, root)%{_bindir}/beat_tap_filter
%{python_sitelib}/%{name}-*
%{python_sitelib}/%{name}/
%{python_sitelib}/beahlib.py*
%{_datadir}/%{name}

%changelog
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
