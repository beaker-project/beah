Administrator Guide
-------------------

Installing and Upgrading Beah
=============================

New Beah releases are made available as RPM packages for Red Hat
Enterprise Linux and Fedora via a yum repository `here
<http://beaker-project.org/yum/harness/>`__.

If you are upgrading an existing Beah installation, you can simply run
``beaker-repo-update`` on the Beaker server. To specify an alternative
location, use the ``-b`` switch. For example::

    beaker-repo-update -b http://beaker-project.org/yum/harness-testing/


Using Beah for IPv6 testing
===========================

.. versionadded:: 0.7.0

During a test run, periodic network communication over TCP/IP takes
place from a Beah daemon on the test system to the lab controller and
between Beah services on the test system itself. The
following are necessary prerequisites for Beah to be able to function
successfully when IPv6 functionality is desired (in a dual IPv4/IPv6
environment) or IPv4 is disabled on the test system to test IPv6
specific functionality (See :ref:`limitations` below).

Test system environment
~~~~~~~~~~~~~~~~~~~~~~~

- The operating system must support IPv6.
- The network interfaces are appropriately configured (IPv6 address
  assigned).
- Routing tables are correctly setup for IPv6.
- The version of the Twisted library must be greater than or equal to
  ``12.1``.

.. note::

   In the absence of any of the above, communication within the test
   system falls back to using IPv4.

Lab controller
~~~~~~~~~~~~~~

- The IPv6 DNS records must be configured correctly.
- The firewall configuration must be correctly configured to allow
  connections to the ``beaker-proxy`` service that runs on port
  ``8000`` over IPv6.

.. note::

   In the absence of any of the above, communication with the lab controller
   falls back to using IPv4.

.. _limitations:

Limitations
~~~~~~~~~~~

The following limitations exist with regards to using Beah for IPv6 testing:

- Multihost testing is currently not supported when the test systems
  have IPv4 disabled.
- Beah fetches every task from the Beaker server's task library just
  before it starts executing it. When IPv4 is disabled, this is not
  possible, unless :file:`/etc/resolv.conf` on the test system has the
  IPv6 addresses of the nameservers so that it can successfully
  communicate over IPv6 with the Beaker server. Of course, the
  server has to be reachable over IPv6 (IPv6 enabled, DNS records
  updated and firewall rules appropriately configured).

  One possible workaround is to manually add entries in the
  :file:`/etc/hosts` file on the test system for the Beaker server (to fetch the Task
  RPMs) and any other host with which communication may be
  needed (for example, for downloading packages from a remote yum
  repository). Here is a sample ``<ksappends/>`` snippet which can be added to
  a Beaker :ref:`Job XML <job-xml>` and will setup :file:`/etc/hosts`
  with IPv6 address and hostname mapping for the beaker server
  ``beaker-server.host.com``::

	     <ks_appends>
             <ks_append><![CDATA[
	     %post
	     cat >>/etc/hosts <<EOF
	     2620:52:0:1065:5054:ff:fe22:b7d9 beaker-server.host.com
	     EOF
	     %end
	     ]]></ks_append>
	     </ks_appends>


  In the absence of both the above, the recipe will
  finish without being able to execute the remaining tasks.
