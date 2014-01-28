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
  before it starts executing it and starts local network servers per
  task. This introduces issues when a recipe disables IPv4, and still
  have tasks to execute:

  * :file:`/etc/resolv.conf` on the test system must have the IPv6
    addresses of the nameservers so that it can successfully
    communicate over IPv6 with the task library. Of course, the Beaker
    server has to be reachable over IPv6 (IPv6 enabled, DNS records
    updated and firewall rules appropriately configured).

  * Assuming that you have got your task installed somehow, Beah
    currently assumes that the IPv4 support has not been
    disabled. Hence the local servers fails to start in an IPv6 only
    environment (See :issue:`1059479`).

Hence, unless both these issues are solved, the recipe will finish without
being able to execute the remaining tasks. Thus, it is recommended
that a task which disables IPv4 be the last task in a recipe.
