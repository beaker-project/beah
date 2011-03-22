import pkg_resources


def load_plugins(the_entrypoint, load_to=None):
    '''setuptools based plugin loader'''
    if load_to is None:
        load_to = {}
    for entrypoint in pkg_resources.iter_entry_points(the_entrypoint):
        load_to[entrypoint.name] = entrypoint.load()
    return load_to


