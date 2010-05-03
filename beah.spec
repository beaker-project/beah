%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_pytho
n_lib; print get_python_lib()")}
%{!?pyver: %global pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Summary: Beah - Beaker Test Harness. Part of Beaker project - http://fedorahosted.org/beaker/wiki.
Name: beah
Version: 0.2.a1
Release: 0%{?dist}
URL: http://fedorahosted.org/beah
Source0: http://fedorahosted.org/releases/b/e/%{name}-%{version}.tar.gz
License: GPLv2+
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Marian Csontos <mcsontos@redhat.com>
Packager: Marian Csontos <mcsontos@redhat.com>
Requires: python python-hashlib python-setuptools python-simplejson 
Requires: python-twisted-core python-twisted-web python-uuid python-zope-interface
BuildRequires: python-devel python-setuptools
Url: http://fedorahosted.org/beaker/wiki

%description
Beah - Beaker Test Harness.

Ultimate Test Harness, with goal to serve any tests and any test scheduler
tools. Harness consist of a server and two kinds of clients - backends and
tasks.

Backends issue commands to Server and process events from tasks.
Tasks are mostly events producers.

Powered by Twisted.


%prep
%setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}

%build
%{__python} setup.py build

%install
%{__python} setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)

%changelog
* Mon May 03 2010 Bill Peck <bpeck@redhat.com> 0.2.a1-0
 - Initial spec file and use of tito for tagging and building.
