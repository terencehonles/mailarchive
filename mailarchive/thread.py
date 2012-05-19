# vim: set fileencoding=utf-8 :

from __future__ import unicode_literals

from collections import Counter, deque

from mailarchive.shared import NS, paging_info


class CounterList(list):
    '''
    creates a list which returns an empty counter when the index is out of
    bounds
    '''

    def __getitem__(self, index):
        try:
            return super(CounterList, self).__getitem__(index)
        except IndexError:
            return Counter()


def date_and_subject(message):
    'returns the data and subject headers'

    headers = message.headers
    return (headers.date_utc, headers.subject)


def build_chains(messages, key=date_and_subject):
    'returns a map of message_id to chain of replies'

    by_id = dict((m.headers.message_id, m) for m in messages)

    info = dict((h.message_id, h.get('in_reply_to'))
                for h in (m.headers for m in messages))


    chains = dict((id, NS(message=by_id[id], children=[])) for id in info)

    for id, reply_to in info.items():
        if reply_to is None: continue

        try:
            chains[reply_to].children.append(chains[id])

        # reply_to is not a key to info: invalid message specified
        # or not in range (treat as not in range)
        except KeyError:
            chains[reply_to] = NS(message=None, children=[chains[id]])

    # sort the children in place
    for children in (v.children for v in chains.values()):
        children.sort(key=lambda x: key(x.message))

    return chains


def build_threads(messages, key=date_and_subject):
    'returns the messages as a series of threads with their replies'

    chains = build_chains(messages, key=key)
    for thread in top_level_chains(chains, key=key):
        yield thread


def child_references(thread):
    'convert the references string into a more easily merged structure'

    result = []
    for refs in (c.message.headers.get('references')
                 for c in thread.children):

        if not refs: continue
        # email references are appended the end of the header
        for index, ref in enumerate(reversed(refs.split())):
            try:
                result[index][ref] = result[index].get(ref, 0) + 1
            except IndexError:
                result.append({ref:1})

    return [Counter(i) for i in result]


def dummy_node(**kargs):
    '''
    create a message stub (for joining and representing out of range messages)
    '''

    if 'thread' in kargs:
        thread = kargs['thread']
        headers = thread.children[0].message.headers

        children = thread.children
        message_id = headers.in_reply_to
        subject = headers.subject
    else:
        children = kargs['children']
        message_id = kargs['message_id']
        subject = kargs['subject']

    return NS(
        message = NS(headers=NS(message_id=message_id, subject=subject)),
        children = children,
    )


def first_message(thread):
    'return the first real message in a thread (not a message stub)'

    while 'payload' not in thread.message:
        thread = thread.children[0]

    return thread.message


def flatten_threads(threads):
    '''
    flatten a thread into a top level message and its replies as a list
    in a depth first order
    '''

    for thread in threads:
        headers = thread.message.headers
        # all normalized messages will have a message_id and subject
        top = dict(message_id=headers.message_id, subject=headers.subject)

        queue = deque([thread])
        messages = []
        while queue:
            thread = queue.popleft()
            queue.extendleft(reversed(thread.children))

            if 'payload' in thread.message:
                messages.append(thread.message)

        yield top, messages


def normalize_threads(threads):
    '''
    normalize threads by creating dummy nodes (messages) to represent
    out of range messages, and then merges as many threads as possible
    based on the threads replies' references
    '''

    threads = iter(threads)

    # find all the threads which are out of range (possible merges)
    out_of_range = []
    first = None
    try:
        while True:
            thread = next(threads)
            if thread.message is None:
                out_of_range.append((child_references(thread),
                                     dummy_node(thread=thread)))
            else:
                first = thread
                break
    except StopIteration:
        pass

    # make sure all the references start the same length and strip the first
    # reference because we already know valid references would indicate this
    # is their parent because it was in their "in_reply_to" header
    if out_of_range:
        length = max(len(i[0]) for i in out_of_range)
        out_of_range = [(CounterList(r[1:] + [Counter()] * (length - len(r))),
                         t)
                        for r, t in out_of_range]

    # TODO: find merge partners anywhere in the reference list
    # try to merge the threads
    merged = []
    while out_of_range:
        refs, thread = out_of_range.pop(0)

        common = [i for i in ((refs[0] & item[0][0], i, item)
                              for i, item in enumerate(out_of_range)) if i[0]]

        # if there were no common references put the thread aside
        if not common:
            merged.append((refs, thread))
            continue

        # go backwards so the indices to pop do not change
        for _, index, _ in reversed(common):
            out_of_range.pop(index)

        (id, _), = sum((i[0] for i in common), Counter()).most_common(1)

        # merge
        refs = CounterList(
            sum(lst, Counter()) for lst in
            zip(*([refs[1:]] + [i[2][0][1:] for i in common]))
        )

        # a message with only a subject will not be linked to
        # (hopefully all the children have the same subject)
        joined = dummy_node(
            message_id = id,
            subject = thread.message.headers.subject,
            children = sum((i[2][1].children for i in common),
                           thread.children)
        )

        # a merge was performed so retry all threads
        out_of_range = merged + [(refs, joined)] + out_of_range
        merged = []


    # return the merged threads, the first in range thread found, and the rest
    for _, thread in merged: yield thread
    if first is not None: yield first
    for thread in threads: yield thread


def tie_threads(threads):
    'stores a messages "previous" and "next" as part of the message data'

    threads = iter(threads)
    peek = previous = None

    try:
        queue = deque([next(threads)])
    except StopIteration:
        return

    while queue:
        thread = queue.popleft()

        # process the children before siblings, but in their original order
        queue.extendleft(reversed(thread.children))

        if 'payload' not in thread.message: continue

        # make sure we can always peek at a message if there are messages left
        if len(queue) < 1:
            try:
                queue.append(next(threads))
            except StopIteration:
                pass

        try:
            peek = paging_info(first_message(queue[0]))
        except IndexError:
            peek = None


        thread.message.next = peek
        thread.message.previous = previous

        previous = paging_info(first_message(thread))


def top_level_chains(chains, key=date_and_subject):
    'return all the threads given a sequence of chains'

    top_level = dict(chains)
    out_of_range = []

    for id, chain in chains.items():
        message = chain.message
        if message is None:
            out_of_range.append(id)
        elif message.headers.get('in_reply_to'):
            top_level.pop(id)

    # sort based on the first child
    # (we can assume there is at least one child)
    for id in sorted(out_of_range,
                     key=lambda x: key(chains[x].children[0].message)):

        yield top_level[id]

    rest = set(top_level.keys()) - set(out_of_range)
    for id in sorted(rest, key=lambda x: key(chains[x].message)):
        yield top_level[id]
