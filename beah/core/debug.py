import os


def breakpoint():
    """Function to create a breakpoint."""
    pass


def runcall(a_callable, *args, **kwargs):
    """Function used to call a_callable under debugger."""
    a_callable(*args, **kwargs)


def setup(debugger, name):
    global runcall, breakpoint
    if debugger == "pdb":
        try:
            import pdb
            runcall = pdb.runcall
            breakpoint = pdb.set_trace
        except ImportError:
            pass
    elif debugger == "profile":
        try:
            import cProfile as profile
        except ImportError:
            try:
                import profile
            except ImportError:
                profile = None
        if profile is not None:
            def profile_runcall(a_callable, *args, **kwargs):
                profiler = profile.Profile()
                try:
                    profiler.runcall(a_callable, *args, **kwargs)
                finally:
                    profiler.dump_stats('/mnt/testarea/%s.profile' % name)
                    profiler.print_stats()
                    #profiler.sort_stats( 'calls', 'cumulative' )
                    #profiler.print_stats()
            runcall = profile_runcall
    #elif debugger in ("rpdb2", "winpdb"):
    #    try:
    #        import rpdb2
    #        rpdb2.start_embedded_debugger('w7F!stH!55H|7')
    #    except ImportError:
    #        pass

