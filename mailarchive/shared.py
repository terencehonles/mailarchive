# vim: set fileencoding=utf-8 :

from __future__ import unicode_literals

import re

try: basestring
except NameError: basestring = str


class NS(dict):
    'helper class to treat a ``dict`` as an instance'

    def __getattr__(self, key): return self[key]
    def __setattr__(self, key, value): self[key] = value


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
