Developer guide
---------------

Beah is using TCP/IP sockets for IPC. In case of failures it is easy to
reconnect. (At least easier than simple capturing stdout.)

Events and Commands are JSON-serialized new-line separated messages sent over
TCP/IP socket. Easy to extend, easy to ignore parts of message which are not
understood. Well supported in many programming languages. Rather effective
enconding/decoding.

Single JSON object on a line, is quite robust: in case of message corruption
only that message (and eventually next one) will be affected. In case of
events, these will not be lost - the lose_item event containing raw data is
generated.

Twisted framework is used for handling non-blocking I/O operations.


Modules
=======

(Beware: things are not in place.)

``beah.config``
  Default configuration. Update this module from outside
``beah.core``
  Independent components - constants, controller, interfaces, basic backends and tasks...
``beah.backends``, ``beah.tasks``
  Additional backend and task adaptors
``beah.wires``
  Wiring to glue things together
``beah.wires.twisted``
  Twisted wiring (mostly metadata - use this protocol, this
  implementation, JSON over TCP/IP socket, default cfg,...
``beah.wires.internals``
  Internal implementation for wirings
``beah.misc``
  Things which do not fit elsewhere
``beah.filters``
  I/O filters. LineReceiver, ObjReceiver,...
``beah.tests``
  Testing harness
``beahlib``
  Library to be used from python tasks/tests.


Setting up a development environment
====================================

To set-up development environment source dev-env.sh. Type ``. dev-env.sh``
in BASH, which will set required environment variables (PATH and PYTHONPATH).
This is not required when package is installed.

After setup, run::

    launcher a

in the same shell, which will start server and backends in separate terminals.
Or launch components yourself.

Development environment provides these shell functions:

* beah-srv - controller server
* beah-cmd-backend - backend to issue commands to controller. Enter ``help``
  when "beah>" prompt is displayed.
* beah-out-backend - backend to display messages from controller
* beah - command line tool. Use ``beah help`` to display help. This uses the
  same command set as beah-cmd-backend
* launcher - wrapper to start these programms in new terminal windows.

beah-out-backend, beah-cmd-backend and beah will wait for controller.

Few auxiliary binaries are provided in bin directory:

* mtail_srv - run srv and beah-out-backend in single window (using multitail
  tool.)
* beat_tap_filter - a filter taking a Perl's Test::Harness::TAP format on
   stdin and producing stream of Events on stdout.

There are few test tasks in examples/tasks directory:

* a_task - a very simple task in python.
* a_task.sh - the same, in bash, with some delays introduced.
* env - a binary displaying environment variables of interest.
* flood - flooding Controller with messges. This task will not finish and has
  to be killed (in a ``pkill flood`` manner.)
* socket - a task using TCP/IP socket to talk to Controller.

Actually a_task and a_task.sh are a simple demonstration of how the test might
look like, though it is not definite and more comfortable API will be
provided.

In default configuration server is listenning on localhost:12432 for backends
and localhost:12434 for tasks. On POSIX compatible systems unix domain sockets
are used for local connections by default.

beah-cmd-backend does not offer history or command line editing features (it
is on TODO list) thus it is more convenient to use beah command line tool.

The commands supported are:

* ping [MESSAGE]: ping a controller, response is sent to issuer only.
* PING [MESSAGE]: ping a controller, response is broadcasted to all backends.
* run TASK (r TASK): run a task. TASK must be an executable file.
* kill:    kill a controller.
* dump: instruct controller to print a diagnostics message on stdout.
* quit (q): close this backend.
* help(h): print this help message.

Controller's log is written to ``[/tmp]/var/log/beah.log``.

Development and Usage in a Lab
==============================

lm-install.sh script can be used to install harness from working copy on a lab
machine. This requires either LABM env.variable to be defined or passing lab
machine's FQDN as an argument

To change settings, change lm-install-env.sh file. As this file is tracked by
VCS, if lm-install-env.sh.tmp exists in current directory it is used with
higher priority.

Usage
~~~~~

On a lab machine::

    $ mkdir -p /mnt/testarea/lm-install
   
This is the default. Change LM_INSTALL_ROOT in lm-install-env.sh.

On the machine where beaker/Harness tree exists::

    edit lm-install-env.sh (or eventually lm-install-env.sh.tmp) file.
    $ export LABM=x.ample.com
    $ ./lm-install.sh
    $ 'LABM=x.ample.com ./lm-install.sh' 

Or, the following can be used instead of the last two steps::

    $ './lm-install.sh x.ample.com'


On a lab machine::

    $ cd /mnt/testarea/lm-install
    $ . lm-package-*.sh
  
Be careful to choose the correct one to be used.

``. /mnt/testarea/lm-install/main.sh`` can be used anytime to read environment and load
functions. Run lm_main_help and lm_help for more help on available functions.

Writing a patch for Beah
========================

Here is a brief overview of how you can submit a patch for Beah.

Clone Beah's repository
~~~~~~~~~~~~~~~~~~~~~~~

Clone beah: ``git clone git://git.beaker-project.org/beah``

Create a local working branch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a branch (say, ``myfeature``): ``git checkout origin/develop -b
myfeature``. Make your changes and once you are happy, commit the
changes. If your patch fixes a bug, please include the Bugzilla number as a
footer line in your commit message.

Submitting your patch
~~~~~~~~~~~~~~~~~~~~~

Beah and all other projects maintained as part of Beaeker (including
 itself) uses the Gerrit code review tool to manage patches. Push your
 local branch to Gerrit for review::

    git push git+ssh://gerrit.beaker-project.org:29418/beah myfeature:refs/for/develop

