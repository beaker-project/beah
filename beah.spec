# The following allows us to build properly on rhel3
%if "0%{?dist}" == "0"
%global __python python2.6
%global _rhel3 26
%global _py_dev 26
%else
%global _py_dev 2
%endif
%global _services "beah-fakelc beah-srv beah-beaker-backend beah-fwd-backend"

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %global pyver %(%{__python} -c "import sys ; print sys.version[:3]")}
Summary: Test Harness. Offspring of Beaker project: http://fedorahosted.org/beaker
Name: beah
Version: 0.6.rpmlint.2
Release: 1%{?dist}
URL: http://fedorahosted.org/beah
Source0: http://fedorahosted.org/releases/b/e/%{name}-%{version}.tar.gz
License: GPLv2+
Group: Development/Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot-%(%{__id_u} -n)
Prefix: %{_prefix}
BuildArch: noarch
Requires: python(abi) >= 2.3
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
Requires(post): chkconfig
Requires(preun): chkconfig
# This is for /sbin/service
Requires(preun): initscripts
Requires(postun): initscripts
BuildRequires: python%{?_py_dev}-devel
BuildRequires: python%{?_rhel3}-setuptools

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
%{__python} setup.py install --optimize=1 --skip-build --root $RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%config(noreplace) %{_sysconfdir}/*.conf
%{_sysconfdir}/init.d/*
%attr(0755, root, root)%{_bindir}/*
%{python_sitelib}/*
%{_datadir}/%{name}/
%doc %{_datadir}/%{name}/README
%doc %{_datadir}/%{name}/COPYING
%doc %{_datadir}/%{name}/LICENSE

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
    for service in %{_services}; do
        /sbin/service $service condrestart >/dev/null 2>&1 || :
    done
fi

%changelog
* Tue May 11 2010 Marian Csontos <mcsontos@redhat.com> 0.6.rpmlint.2-1
- Spec file changed to be more template-alike. (mcsontos@redhat.com)
- Commented configuration files. (mcsontos@redhat.com)
- Cleaned up more rpmlint errors and warnings. (mcsontos@redhat.com)

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
