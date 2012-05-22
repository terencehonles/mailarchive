default: scripts styles

scripts:
	$(MAKE) -C mailarchive/data/scripts/

styles:
	$(MAKE) -C mailarchive/data/styles/

.PHONY: default script styles
.DEFAULT: default
