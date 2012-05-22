SASS_OPTS=--compass --style compressed

%.css : %.scss
	sass $(SASS_OPTS) $< $@

default: $(wildcard *.css)

.PHONY: default
.DEFAULT: default
