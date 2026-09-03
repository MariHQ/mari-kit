SPHINXBUILD ?= sphinx-build
SOURCEDIR = docs
BUILDDIR = _build

.PHONY: clean html

html:
	$(SPHINXBUILD) -W --keep-going -b html $(SOURCEDIR) $(BUILDDIR)/html

clean:
	$(SPHINXBUILD) -M clean $(SOURCEDIR) $(BUILDDIR)

