Environment variables
---------------------

The harness sets a number of environment variables in the execution environment 
for tasks. The task can use these to adjust its behaviour as needed.

Task parameters (given in the Beaker job XML using ``<params/>``) are also 
passed to the task as environment variables.

Note that these environment variables *will not* be set when you log in to the 
system as a user over SSH or on the console.

.. envvar:: TEST

   The name of the current task. :envvar:`TASKNAME` is an alias for this 
   variable.

.. envvar:: TESTPATH

   Path to the directory containing this task.

.. envvar:: TESTRPMNAME

   NVRA (Name-Version-Release.Arch) of the current task RPM. Deprecated: do not 
   rely on tasks being packaged as RPMs.

.. envvar:: KILLTIME

   Expected run time of this task in seconds. This is declared in the TestTime 
   field in the task metadata (see :ref:`testinfo-testtime`), and is the length 
   of time by which the harness extends the watchdog at the start of the task.

.. envvar:: FAMILY
            DISTRO
            VARIANT
            ARCH

   Details of the Beaker distro tree which was installed for the current 
   recipe.

.. envvar:: SUBMITTER

   E-mail address of the Beaker user who submitted the current job.

.. envvar:: JOBID
            RECIPESETID
            RECIPEID
            TASKID

   Beaker database IDs for the current job, recipe set, recipe, and recipe-task 
   respectively. :envvar:`TESTID` and :envvar:`RECIPETESTID` are deprecated 
   aliases for :envvar:`TASKID`.

.. envvar:: TESTORDER

   Integer counter for tasks in the recipe. The value increases for every 
   subsequent task, and every peer task in the recipe set will have the same 
   value, but note that it *does not* increase by 1 for each task.

.. envvar:: REBOOTCOUNT

   Number of times this task has rebooted. The counter starts at zero when the 
   task is first run, and increments for every reboot. If a task triggers 
   a reboot, it can test this variable to decide which phase of the test to 
   enter so that it doesn't loop infinitely.

.. envvar:: RECIPETYPE

   The type of the recipe. Possible values are ``guest`` for a guest recipe, or 
   ``machine`` for a host recipe. See :doc:`virtualization-workflow`.

.. envvar:: GUESTS

   Deprecated. The recommended means of looking up details of guest recipes is 
   to fetch the recipe XML from the lab controller and parse it (see 
   :http:get:`/recipes/(recipe_id)/`).

.. envvar:: RECIPE_MEMBERS

   Space-separated list of FQDNs of all systems in the current recipe set.

.. envvar:: RECIPE_ROLE

   The role for the current recipe. See :doc:`multihost`.

.. envvar:: ROLE

   The role for the current task. See :doc:`multihost`.

.. envvar:: HYPERVISOR_HOSTNAME

   The hostname of a guest recipe's host. This is retrieved at recipe run time,
   and is not dynamically updated (i.e if you migrate your guest
   this variable will not be updated).

Additionally, one environment variable will be set for each recipe role defined 
in the recipe set. The name of the environment variable is the role name, and 
its value is a space-separated list of FQDNs of the systems performing that 
role. Similarly, each task role is set as an environment variable, but note 
however that task roles are only shared amongst recipes of the same type. That 
is, task roles for guest recipes are not visible to host recipes, and vice 
versa. See :doc:`multihost` for further details.

The following environment variables are set system-wide by Beaker at the start 
of the recipe.

.. envvar:: LAB_CONTROLLER

   FQDN of the lab controller which the current system is attached to.

.. envvar:: BEAKER

   FQDN of the Beaker server.

.. envvar:: BEAKER_JOB_WHITEBOARD

   Whiteboard of the current job.

.. envvar:: BEAKER_RECIPE_WHITEBOARD

   Recipe whiteboard for the current recipe.
