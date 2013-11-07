# Makefile for Sphinx documentation

SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
PAPER         =
BUILDDIR      = _build
STATICDIR     = _static

# Internal variables.
PAPEROPT_a4     = -D latex_paper_size=a4
PAPEROPT_letter = -D latex_paper_size=letter
ALLSPHINXOPTS   = -d $(BUILDDIR)/doctrees $(PAPEROPT_$(PAPER)) $(SPHINXOPTS) .
# the i18n builder cannot share the environment and doctrees with the others
I18NSPHINXOPTS  = $(PAPEROPT_$(PAPER)) $(SPHINXOPTS) .

.PHONY: clean html man download_static

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  html       to make standalone HTML files"
	@echo "  man        to make manual pages"

clean:
	rm -rf $(BUILDDIR)/* $(STATICDIR)

# pull style.css and images from beaker's repo
download_static:

	mkdir -p $(STATICDIR)/images
	curl -o $(STATICDIR)/style.css http://git.beaker-project.org/cgit/beaker-project.org/plain/style.css
	curl -o $(STATICDIR)/images/fabric_plaid.png http://git.beaker-project.org/cgit/beaker-project.org/plain/images/fabric_plaid.png
	curl -o $(STATICDIR)/images/rubber_grip.png http://git.beaker-project.org/cgit/beaker-project.org/plain/images/rubber_grip.png
	curl -o $(STATICDIR)/images/logo.png http://git.beaker-project.org/cgit/beaker-project.org/plain/images/logo.png

html:	download_static

	$(SPHINXBUILD) -b html $(ALLSPHINXOPTS) $(BUILDDIR)/html
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)/html."

# currently unused
man:
	$(SPHINXBUILD) -b man $(ALLSPHINXOPTS) $(BUILDDIR)/man
	@echo
	@echo "Build finished. The manual pages are in $(BUILDDIR)/man."
