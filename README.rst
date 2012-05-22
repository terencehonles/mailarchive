mailarchive
===========

``mailarchive`` is a script to convert mbox files into a nice and easy to use
web view and can be used as an alternative front end to Mailman_ 2.0's
pipermail.


Installation
------------


To install ``mailarchive`` run ``pip install mailarchive`` or
``easy_install mailarchive``.

Basic Usage
-----------

To mirror a mailing list (e.g. `Python.org's mailing list`_):

1. Save the following as ``config.yaml`` so we don't have to add too many
   arguments to the proceeding commands::

    list_address: pydotorg-www@python.org
    page_title: pydotorg-www archives
    page_link: http://mail.python.org/pipermail/pydotorg-www/

2. Copy the mailing list::

    mailarchive --config config.yaml --output path/to/document/root \
                build --gzip http://mail.python.org/pipermail/pydotorg-www/2012-April.txt.gz

3. View the compiled HTML at http://host/

Explicit Example (aka script)
-----------------------------

*This assumes you have apache's user directories set up*

::

    # Mac user directory is "Sites"
    if fgrep -iq darwin <<<`uname -a`; then
        USER_DIR=~/Sites
        BROWSER_OPEN=open

    # Linux user directory is "public_html"
    else
        USER_DIR=~/public_html
        BROWSER_OPEN=xdg-open
    fi

    cat > config.yaml <<EOF
    list_address: pydotorg-www@python.org
    page_title: pydotorg-www archives
    page_link: http://mail.python.org/pipermail/pydotorg-www/
    web_root: /~$USER/
    EOF

    # only needs to be run once for each config
    mailarchive --config config.yaml --output $USER_DIR static-files

    for month in April March February ; do
        url=http://mail.python.org/pipermail/pydotorg-www/2012-$month.txt.gz

        mailarchive --config config.yaml --output $USER_DIR/2012-$month \
            messages --gzip $url

        mailarchive --config config.yaml --output $USER_DIR/2012-$month \
            indices --gzip $url

    done

    $BROWSER_OPEN http://localhost/~$USER/2012-April/thread.html


.. _Mailman: http://www.gnu.org/software/mailman/index.html
.. _Python.org's mailing list: http://mail.python.org/pipermail/pydotorg-www/
