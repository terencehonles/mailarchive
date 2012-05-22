ICED_OPTS=--print --runtime window
CLOSURE_OPTS=--compilation_level SIMPLE_OPTIMIZATIONS

# Valid coffee scripts, but need to be expanded using jsontemplate
%.js.jst : %.jst.coffee
	iced $(ICED_OPTS) $< | closure $(CLOSURE_OPTS) > $@

%.js : %.coffee
	iced $(ICED_OPTS) $< | closure $(CLOSURE_OPTS) > $@

default: $(wildcard *.js.jst) $(wildcard *.js)

.PHONY: default
.DEFAULT: default
