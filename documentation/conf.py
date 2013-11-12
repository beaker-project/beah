
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx', 'sphinx.ext.todo', 'sphinx.ext.viewcode']


source_suffix = '.rst'
master_doc = 'index'
project = u'Beah'
copyright = u'2013, Red Hat Inc'

try:
    import beah
    release = beah.__version__
    version = '.'.join(release.split('.')[:2])
except ImportError:
    release = 'dev'
    version = 'dev'

exclude_patterns = ['_build']
html_theme = 'default'
html_title = 'Beah %s' % version
html_short_title = 'Beah'

intersphinx_mapping = {'python': ('http://docs.python.org/', None),
                       'beakerdev': ('http://beaker-project.org/dev/', None),
                       'beakerdocs': ('http://beaker-project.org/docs/', None)}
