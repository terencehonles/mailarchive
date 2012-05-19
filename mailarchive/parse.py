# vim: set fileencoding=utf-8 :

from __future__ import unicode_literals

import base64
import mailbox
import quopri
import re
import time

from dateutil import tz
from dateutil.parser import parse as dateparser
from hashlib import md5, sha1
from io import DEFAULT_BUFFER_SIZE as BUFFER_SIZE
from tempfile import NamedTemporaryFile

from mailarchive.shared import NS

UTC = tz.tzutc()


# encoded URL match from email.header is too strict
# (allow non-hex characters after an '=' sign)
ENCODED_PATTERN = re.compile(r'=\?([^?]*)\?([qb])\?(.*?)\?=([^0-9a-f]|$)',
                             re.I)

def _decode(match):
    'transforms a encoded match to its decoded substitution'

    encoding, transfer_encoding, encoded, trailing = match.groups()

    if transfer_encoding.lower() == 'b':
        # add extra padding just in case there was not enough padding
        return base64.b64decode((encoded + '====').encode('ascii')) \
                     .decode(encoding) + trailing

    else:
        return quopri.decodestring(encoded.encode('ascii')) \
                     .decode(encoding) + trailing


def decode(string):
    'returns a properly decoded email header'

    return ENCODED_PATTERN.sub(_decode, string)


def parse_mbox(filename=None, fileobj=None):
    'parse a mbox file'

    if not filename and not fileobj:
        raise ValueError('one of "filename" or "fileobj" is required')

    if filename:
        mbox = mailbox.mbox(filename)
        for message in mbox:
            yield simplify_message(message)

    else:
        # create a tempfile because mbox needs a path
        with NamedTemporaryFile() as tempfile:
            for chunk in iter(lambda: fileobj.read(BUFFER_SIZE), bytes()):
                tempfile.write(chunk)

            # make sure there is something to read
            tempfile.flush()

            mbox = mailbox.mbox(tempfile.name)
            for message in mbox:
                yield simplify_message(message)


def simplify_message(message):
    'transforms a message instance into built-in types (json encodable)'

    assert not message.is_multipart()
    headers = NS((k.replace('-', '_').lower(), decode(v))
                  for k, v in message.items())

    # if the @ is not found or after the first space
    sender = headers.get('from', '')
    at = sender.find('@')
    if sender and (at == -1 or sender.find(' ') < at):
        sender = sender.replace(' at ', '@')
        # do not make it any easier to spam?
        # headers['from'] = sender

    headers['from_hash'] = md5(sender.encode('utf-8')).hexdigest()

    date = headers.get('date')
    if date:
        utc = dateparser(date).astimezone(UTC)
        headers['date_utc'] = int(time.mktime(utc.timetuple()))

    message_id = headers.get('message_id')
    if message_id:
        message_id_hash = sha1(message_id.encode('utf-8')).hexdigest()
        headers['message_id_hash'] = message_id_hash

    return NS(headers=headers, payload = message.get_payload())
