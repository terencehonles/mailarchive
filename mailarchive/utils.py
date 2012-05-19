# vim: set fileencoding=utf-8 :

from __future__ import unicode_literals

import argparse
import json

from collections import deque
from contextlib import closing
from gzip import GzipFile
from io import BytesIO, open

from mailarchive.parse import parse_mbox
from mailarchive.shared import NS
from mailarchive.thread import build_threads, flatten_threads, \
                               normalize_threads, tie_threads

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit


def convert(url, gzip=False):
    'converts a mbox url to a JSON encodable structure'

    parser = parse_gz_mbox if gzip else parse_mbox

    # local file
    if not urlsplit(url).scheme:
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




convert_parser = argparse.ArgumentParser(
    description='Parses local or remote mbox files and saves parsed '
                'representation in JSON')

convert_parser.add_argument('--gzip', default=False, action='store_true',
                            help='Use gzip to decompress the target file')

convert_parser.add_argument('--output', '-o', default=None,
                            help='Filename to save the output to '
                                 '(default: stdout)')

convert_parser.add_argument('url', help='URL or filename to parse')


def run_convert():
    'executes the convert script'

    args = convert_parser.parse_args()

    from sys import stdout
    output = stdout

    try:
        if args.output:
            output = open(args.output, 'wb')


        encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True)
        for chunk in encoder.iterencode(convert(args.url, gzip=args.gzip)):
            output.write(chunk.encode('utf-8'))

    finally:
        if output is not stdout: output.close()
