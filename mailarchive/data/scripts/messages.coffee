$ = this.jQuery
document = this.document
history = this.History
_cache = {}
_parsed = {}
_templates = null


fetch_message_info = (id, callback) ->
    # fetches message info and "returns" it via the given callback
    info = _cache[id]
    if info
        callback(info)
        return

    $.ajax('messages.json', {
        error: () ->
            console.log('messages could not be fetched at this time!')
            callback()

        success: (data) ->
            get = (index) ->
                if index < 0 or index >= data.length
                    return

                headers = data[index][1][0].headers
                return {
                    from: simple_from(headers['from']),
                    message_id: headers['message_id'],
                    message_id_hash: headers['message_id_hash'],
                    subject: headers['subject'],
                }


            for [top, messages], index in data
                for message in messages
                    _cache[message.headers.message_id_hash] = {
                        previous: get(index - 1)
                        next: get(index + 1)
                        message: message
                    }

            callback(_cache[id])
    })

    return


fetch_templates = (callback) ->
    # fetch the templates and "returns" it via the given callback

    if _templates
        callback(_templates)
        return

    $.ajax('[[web_root|string-data]]templates.json', {
        error: () ->
            console.log('templates could not be fetched at this time!')
            callback()

        success: (data) ->
            _templates = data
            callback(_templates)
    })

    return


init_paging = () ->
    # sets up the paging controls to use ajax

    $('#paging a').click((e) ->
        e.preventDefault()
        parts = this.pathname.split(/\//)
        id = parts[parts.length - 1].split('.')[0]

        # TODO: display "loading" state
        await fetch_message_info(id, defer info)

        if info
            history.pushState(
                info,
                document.title,
                # TODO: this should be using the template
                info.message.headers.message_id_hash + '.html'
            )

        # TODO: display network issue state (message not fetched)

        return false
    )


_parse_template = (name) ->
    # parse a template assuming the templates have already been loaded

    template = _parsed[name]
    if template
        return template

    body = _templates[name]
    if body
        template = _parsed[name] = jsontemplate.Template(body, {
            meta: '{{}}',
            more_formatters: jsontemplate.CallableRegistry((name) ->
                tmpl = _parse_template(name)
                if tmpl
                    return (data) -> tmpl.expand(data)
            )
        })

    return template


parse_template = (name, callback) ->
    await fetch_templates(defer templates)
    callback(_parse_template(name))


render_message = (info) ->
    # renders a message which has been fetched with ajax

    await
        parse_template('controls.html.jst', defer controls_tmpl)
        parse_template('message.html.jst', defer message_tmpl)

    $('#controls').replaceWith(controls_tmpl.expand({
        list_address: '[[list_address|string-data]]',

        previous_thread: info.previous,
        next_thread: info.next,

        message: info.message,
        author_index: '[[author_index|string-data]]',
        date_index: '[[date_index|string-data]]',
        subject_index: '[[subject_index|string-data]]',
        thread_index: '[[thread_index|string-data]]',
    }))
    $('#message').replaceWith(message_tmpl.expand(info.message))
    init_paging()
    return


simple_from = (name) ->
    match = /\(([^)]+)\)/.exec(name)

    return match[1] if match
    return name



history.Adapter.bind(this, 'statechange', () ->
    state = history.getState()
    render_message(state.data) if state
)

$(() -> init_paging())
