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

.. todo:: Beah release tarballs
