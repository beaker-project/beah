import docutils.nodes
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

# A poor man's version of sphinxcontrib-issuetracker 
# <https://pypi.python.org/pypi/sphinxcontrib-issuetracker> which unfortunately 
# requires a newer python-requests than is available in Fedora.
# This code inspired by Doug Hellman's article 
# <http://doughellmann.com/2010/05/defining-custom-roles-in-sphinx.html>.
def beaker_bugzilla_issue_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    bz_url = 'https://bugzilla.redhat.com/show_bug.cgi?id=%s' % text
    text = "#" + text
    node = docutils.nodes.reference(rawtext, text, refuri=bz_url, **options)
    return [node], []

def setup(app):
    app.add_role('issue', beaker_bugzilla_issue_role)

