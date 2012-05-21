# vim: set fileencoding=utf-8 :

from __future__ import unicode_literals

import codecs
import json
import pkg_resources
import sys
import shutil
import yaml

from argparse import ArgumentParser
from collections import deque
from contextlib import closing
from gzip import GzipFile
from io import BytesIO, open
from itertools import groupby
from jsontemplate import _jsontemplate as jsontemplate # bad __all__
from os import path

from mailarchive.parse import parse_mbox
from mailarchive.shared import NS, paging_info, simple_from, wrap_dictionaries

from mailarchive.thread import build_threads, flatten_threads, \
                               normalize_threads, tie_threads

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

try:
    from urllib.parse import queue as urlescape, urlsplit
except ImportError:
    from urllib import quote as urlescape
    from urlparse import urlsplit


try: basestring
except NameError: basestring = str

try: unicode
except NameError: unicode = str


# these really should not have to be specified at all
DEFAULT_FORMATTERS = {
    'url-param-value': lambda s: urlescape(s.encode('utf-8')),
}


class Path(unicode):
    'a path can either be a package resource or an actual file system path'

    def __new__(cls, value='', pkg_resource=False):
        return super(Path, cls).__new__(cls, value)

    def __init__(self, value='', pkg_resource=False):
        self.pkg_resource = pkg_resource

    def __add__(self, other):
        if self.pkg_resource:
            return Path(str(self) + '/' + other, pkg_resource=True)
        else:
            return Path(path.join(self, other))

    def __radd__(self, other):
        if self.pkg_resource:
            return Path(other + '/' + str(self), pkg_resource=True)
        else:
            return Path(path.join(other, self))

    def isdir(self):
        if not self.pkg_resource:
            return path.isdir(self)
        else:
            return pkg_resources.resource_isdir(__name__, self)

    def open(self, encoding=None, errors='strict'):
        'returns a file stream to the specified resource'

        if not self.pkg_resource:
            return open(self, mode='r' if encoding else 'rb',
                        encoding=encoding, errors=errors)

        else:
            stream = pkg_resources.resource_stream(__name__, self)
            if not encoding: return stream

            return codes.EncodedFile(stream, data_encoding=encoding,
                                     errors=errors)


    def read(self, encoding=None, errors='strict'):
        'returns the contents of the specified resource'

        if not self.pkg_resource:
            if not encoding:
                with open(self, 'rb') as file: return files.read()
            else:
                with open(self, mode='r', encoding=encoding,
                          errors=errors) as file:

                    return file.read()

        else:
            data = pkg_resources.resource_string(__name__, self)
            if not encoding: return data

            return data.decode(encoding=encoding, errors=errors)


DEFAULT_MESSAGE = 'message.html.jst'
DEFAULT_PARTIALS = 'partials'
DEFAULT_TEMPLATES = Path('data/templates', pkg_resource=True)


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
            result = self[key] = load_template(self.__dir + key,
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


def convert(url, gzip=False):
    'converts a mbox url to a JSON encodable structure'

    parser = parse_gz_mbox if gzip else parse_mbox

    # stdin
    if url == '-':
        messages = parser(fileobj=BytesIO(sys.stdin.read()))

    # local file
    elif not urlsplit(url).scheme:
        messages = parser(filename=url)
    else:
        messages = fetch_messages(url, parser=parser)

    threads = list(normalize_threads(build_threads(list(messages))))
    tie_threads(threads)

    return list(flatten_threads(threads))


def fetch_messages(url, parser=parse_mbox):
    'parse messages via a URL'

    with closing(urlopen(url)) as network_file:
        for message in parser(fileobj=BytesIO(network_file.read())):
            yield message


def load_template(filename, **kargs):
    'create a template by filename'

    if isinstance(filename, Path):
        return Template(filename.read(encoding='utf-8'), **kargs)

    with open(filename, encoding='utf-8') as file:
        return Template(file.read(), **kargs)


def make_partitioner(sort_keys, group_keys=None):
    'returns a method to partition a sequence of messages'

    def key(keys):
        def key(message):
            headers = message['headers']
            for key in keys:
                header = headers[key]

                # all string comparisons are case and whitespace insensitive
                if isinstance(header, basestring):
                    yield ' '.join(header.lower().split())
                else:
                    yield header

        return lambda message: tuple(key(message))

    sort_key = key(sort_keys)
    group_key = key(group_keys)

    def partitioner(messages):
        if not group_keys:
            return dict(messages=sorted(messages, key=sort_key))
        else:
            # do not use the groupby key because it has been normalized
            groups = (list(messages) for _, messages in
                      groupby(sorted(messages, key=sort_key), key=group_key))

            return dict(groups=[dict(name=m[0]['headers'][group_keys[0]],
                                     messages=m) for m in groups])

    return partitioner


def map_thread(fn, thread):
    'maps messages in a thread given a mapping function ``fn``'

    children = []
    result = NS(message=fn(thread.message), children=children)

    queue = deque([(thread.children, children)])
    while queue:
        parents, lst = queue.popleft()
        for parent in parents:
            children = []
            lst.append(NS(message=fn(parent.message), children=children))
            queue.append((parent.children, children))

    return result


def parse_gz_mbox(filename=None, fileobj=None):
    'parse a gz compressed mbox file'

    if not filename and not fileobj:
        raise ValueError('one of "filename" or "fileobj" is required')

    gz = GzipFile(filename=filename, fileobj=fileobj)
    for message in parse_mbox(fileobj=gz):
        yield message


def preprocess_messages(args):
    'fetches or loads the threads needed for message related activities'

    url = args.url
    if not args.json:
        # run convert (and all its logic)
        threads = convert(args.url, gzip=args.gzip)
    else:
        # stdin
        if url == '-':
            data = sys.stdin.read()
        # local file
        elif not urlsplit(url).scheme:
            with open(url, 'rb') as file: data = file.read()
        else:
            with closing(urlopen(url)) as file: data = file.read()

        if args.gzip:
            data = GzipFile(fileobj=BytesIO(data)).read()

        threads = wrap_dictionaries(json.loads(data))

    if args.templates is None:
        args.templates = DEFAULT_TEMPLATES

    if args.partials is None:
        args.partials = args.templates + DEFAULT_PARTIALS

    if args.message_template is None:
        args.message_template = args.templates + DEFAULT_MESSAGE

    return dict(threads=threads, args=args)


def run_build(threads, args):
    'builds the message and index files'

    run_static(args)
    run_indices(threads, args)
    run_messages(threads, args)


def run_convert():
    'executes the convert script'

    args = convert_parser.parse_args()
    output = sys.stdout

    try:
        if args.output:
            output = open(args.output, 'wb')


        encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True)
        for chunk in encoder.iterencode(convert(args.url, gzip=args.gzip)):
            output.write(chunk.encode('utf-8'))

    finally:
        if output is not sys.stdout: output.close()


INDICES = [
    NS(name=lambda x: x.date_title, filename=lambda x: x.date_index,
       partitioner=make_partitioner(['date_utc'])),

    NS(name=lambda x: x.subject_title, filename=lambda x: x.subject_index,
       partitioner=make_partitioner(['subject', 'date_utc'], ['subject'])),

    NS(name=lambda x: x.author_title, filename=lambda x: x.author_index,
       partitioner=make_partitioner(['from', 'date_utc'], ['from'])),
]


def run_indices(threads, args):
    'builds the index files'

    single_template = load_template(args.templates + 'index.html.jst')
    grouped_template = load_template(args.templates + 'grouped-index.html.jst')

    messages = [
        NS([('from', simple_from(m['headers']['from']))] + list(m.items()))
        for _, messages in threads
            for m in messages
    ]

    # build simple indices
    for index in INDICES:
        data = dict(title=index.name(args), **index.partitioner(messages))

        if 'groups' in data:
            html = grouped_template.expand(data)
        else:
            html = single_template.expand(data)

        with open(path.join(args.output, index.filename(args)), mode='w',
                  encoding='utf-8') as out:

            out.write(html)


    partials = {}
    if args.partials.isdir():
        partials = PartialManager(args.partials)

    index_template = load_template(args.templates + 'thread-index.html.jst',
                                   more_formatters=partials)

    partial_template = load_template(args.partials + 'thread.html.jst',
                                     more_formatters=partials)

    # flatten the threads
    messages = [message for _, messages in threads for message in messages]

    def preprocess(message):
        from_ = simple_from(message.headers.get('from', '')) or None
        return dict(list(message.items()) + [('from', from_)])

    # recursively render the threads here so the expanding doesn't
    # hit the recursion limit
    def render_thread(thread):
        return partial_template.expand(
            message=preprocess(thread.message),
            children=[render_thread(child) for child in thread.children]
        )

    with open(path.join(args.output, args.thread_index), mode='w',
              encoding='utf-8') as out:

        out.write(index_template.expand(
            title=args.thread_title,
            threads=[dict(message=preprocess(t.message),
                          children=[render_thread(c) for c in t.children])
                     for t in normalize_threads(build_threads(messages))]
        ))


def run_mailarchive():
    '``mailarchive`` entry point'

    args = mailarchive_parser.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as file:
            config = yaml.load(file)

        blacklist = set(['action', 'preprocess'])
        for key, value in config.items():
            if key not in blacklist:
                setattr(args, key, value)


    missing = [v for k, v in (('list_address', '--list-address'),
                              ('page_link', '--page-link'),
                              ('page_title', '--page-title'))

               if getattr(args, k, None) is None]

    if missing:
        if len(missing) > 1:
            mailarchive_parser.error('arguments: %s are required'
                    % ' and '.join((', '.join(missing[:-1]), missing[-1])))

        else:
            mailarchive_parser.error('argument %s is required' % missing[0])


    if not args.web_root.endswith('/'):
        args.web_root += '/'

    try:
        preprocessor = args.preprocess
    except AttributeError:
        preprocessed = dict(args=args)
    else:
        preprocessed = preprocessor(args)

    args.action(**preprocessed)


def run_messages(threads, args):
    'builds the message files'

    partials = {}
    if args.partials.isdir():
        partials = PartialManager(args.partials)

    message_template = load_template(args.message_template,
                                     more_formatters=partials)

    back = None
    for index in range(len(threads)):
        if index > 0:
            back = paging_info(threads[index - 1][1][0])

        try:
            forward = paging_info(threads[index + 1][1][0])
        except IndexError:
            forward = None

        for message in threads[index][1]:
            filename = message.headers.message_id_hash + '.html'
            with open(path.join(args.output, filename), mode='w',
                      encoding='utf-8') as out:

                out.write(message_template.expand(
                    list_address=args.list_address,
                    title=args.page_title,
                    top_level=args.page_link,
                    web_root=args.web_root,

                    template=message_template,
                    message=message,
                    next_thread=forward,
                    previous_thread=back,

                    author_index=args.author_index,
                    date_index=args.date_index,
                    subject_index=args.subject_index,
                    thread_index=args.thread_index,
                ))


def run_static(args):
    'writes static files to the specified output directory'

    R = lambda x: Path(x, pkg_resource=True)

    for filename in ['messages.css']:
        with open(path.join(args.output, filename), 'wb') as out:
            out.write(R('data/styles/%s' % filename).read())


convert_parser = ArgumentParser(
    description='Parses local or remote mbox files and saves parsed '
                'representation in JSON')

convert_parser.add_argument('--gzip', default=False, action='store_true',
                            help='Use gzip to decompress the target file')

convert_parser.add_argument('--output', '-o', default=None,
                            help='Filename to save the output to '
                                 '(default: stdout)')

convert_parser.add_argument('url', help='URL or filename to parse')


mailarchive_parser = ArgumentParser()

mailarchive_parser.set_defaults(
    config = None,
    output = '.',
    web_root = '/',

    date_index = 'date.html',
    date_title = 'Archives by Date',

    subject_index = 'subject.html',
    subject_title = 'Archives by Subject',

    author_index = 'author.html',
    author_title = 'Archives by Author',

    thread_index = 'thread.html',
    thread_title = 'Archives by Thread',
)


mailarchive_subparser = mailarchive_parser.add_subparsers()

mailarchive_parser.add_argument('--config',
                                help='Use a config file (yaml) instead of '
                                     'options')

mailarchive_parser.add_argument('--output', '-o', metavar='OUTPUT_DIR',
                                help='Output directory to use')


mailarchive_parser.add_argument('--web-root', '--root',
                                help='Root for the compiled files')

group = mailarchive_parser.add_argument_group('Index Arguments')
for group_type in ('date', 'subject', 'author', 'thread'):
    group.add_argument('--%s-index' % group_type,
                       help='Filename of the %s index' % group_type)

    group.add_argument('--%s-title' % group_type,
                       help='Title of the %s index' % group_type)

group = mailarchive_parser.add_argument_group('Required Arguments')
group.add_argument('--list-address',
                   help='Email address to send to email list')

group.add_argument('--page-title',
                   help='Title for message pages')

group.add_argument('--page-link',
                   help='Page title link destination')


# parent parser for parsers which operate on messages
message_parent_parser = ArgumentParser(add_help=False)
message_parent_parser.set_defaults(
    preprocess=preprocess_messages,

    # does not really "belong" here, but it is easier than making two
    # different preprocessors
    message_template=None
)

message_parent_parser.add_argument('url',
                                   help='URL or filename to use as input')

message_parent_parser.add_argument('--gzip', default=False,
                                   action='store_true',
                                   help='Use gzip to decompress the target '
                                        'file')

message_parent_parser.add_argument('--json', default=False,
                                   action='store_true',
                                   help='Treat the target file as a parsed '
                                        'JSON instance')

message_parent_parser.add_argument('--partials', metavar='PARTIALS_DIR',
                                   default=None,
                                   help='Partials directory to use'
                                        ' (default: TEMPLATES_DIR/%s)'
                                            % DEFAULT_PARTIALS)

message_parent_parser.add_argument('--templates', '-t', metavar='TEMPLATES_DIR',
                                   default=DEFAULT_TEMPLATES,
                                   help='Template directory to use '
                                        '(default: installed templates)')


build_parser = mailarchive_subparser.add_parser(
                    'build', parents=[message_parent_parser])

build_parser.set_defaults(action=run_build)


index_parser = mailarchive_subparser.add_parser(
                    'indices', parents=[message_parent_parser])

index_parser.set_defaults(action=run_indices)


message_parser = mailarchive_subparser.add_parser(
                    'messages', parents=[message_parent_parser])


message_parser.add_argument('--message-template', '--message',
                            dest='message_template',
                            metavar='MESSAGE_TEMPLATE',
                            help='Message template to use '
                                 '(default: TEMPLATES_DIR/%s)'
                                    % DEFAULT_MESSAGE)

message_parser.set_defaults(action=run_messages)

static_parser = mailarchive_subparser.add_parser('static-files')

static_parser.set_defaults(action=run_static)


if __name__ == '__main__':
    run_mailarchive()
