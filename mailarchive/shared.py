# vim: set fileencoding=utf-8 :

from __future__ import unicode_literals

from jsontemplate import _jsontemplate as jsontemplate # bad __all__
import re
import urllib

from io import open
from os import path

try:
    from urllib.parse import quote as urlescape
except ImportError:
    from urllib import quote as urlescape

try: basestring
except NameError: basestring = str


# these really should not have to be specified at all
DEFAULT_FORMATTERS = {
    'url-param-value': lambda s: urlescape(s.encode('utf-8')),
}


class NS(dict):
    'helper class to treat a ``dict`` as an instance'

    def __getattr__(self, key): return self[key]
    def __setattr__(self, key, value): self[key] = value


class PartialManager(dict):
    '''
    create a formatter ``dict`` to automatically load templates in a specified
    directory
    '''

    def __init__(self, directory):
        super(PartialManager, self).__init__()
        self.__dir = directory

    def get(self, key, value=None):
        try:
            return self[key]
        except KeyError:
            return value

    def __getitem__(self, key):
        try:
            return super(PartialManager, self).__getitem__(key)
        except KeyError:
            pass

        try:
            result = self[key] = load_template(path.join(self.__dir, key),
                                               more_formatters=self).expand

            return result
        except IOError:
            raise KeyError(repr(key))


def Template(*args, **kargs):
    'create a Template with our preferred defaults'

    meta = kargs.pop('meta', '{{}}')
    formatters = kargs.pop('more_formatters', None)
    if formatters is not None:
        chain = jsontemplate.ChainedRegistry
        dict_registry = jsontemplate.DictRegistry

        if isinstance(formatters, dict):
            formatters = dict_registry(formatters)

        kargs['more_formatters'] = chain([formatters,
                                          dict_registry(DEFAULT_FORMATTERS)])
    else:
        kargs['more_formatters'] = DEFAULT_FORMATTERS

    return jsontemplate.Template(*args, meta=meta, **kargs)


def load_template(filename, **kargs):
    'create a template by filename'
    with open(filename, encoding='utf-8') as file:
        return Template(file.read(), **kargs)


NAME_PATTERN = re.compile(r'(?<=\()[^()]+(?=\))')
def simple_from(name):
    'returns the "from" in the parenthesis if possible'

    match = NAME_PATTERN.search(name)
    if match:
        return match.group()

    return name


def paging_info(message):
    'returns the data structure expected by the paging controls'

    headers = message.headers

    return {
        'message_id': headers.message_id,
        'message_id_hash': headers.message_id_hash,
        'from': simple_from(headers['from']),
        'subject': headers.subject,
    }


def wrap_dictionaries(value):
    'recursively tries to replace ``dict`` instances with ``NS`` instances'

    if isinstance(value, basestring):
        return value

    try:
        return NS((k, wrap_dictionaries(v)) for k, v in value.items())
    except (AttributeError, TypeError):
        try:
            if isinstance(value, tuple):
                return tuple(wrap_dictionaries(i) for i in value)
            else:
                return [wrap_dictionaries(i) for i in value]
        except TypeError:
            return value
