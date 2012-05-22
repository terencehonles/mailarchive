#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

from setuptools import setup, find_packages

with open('README') as readme:
    documentation = readme.read()

setup(
    name = 'mailarchive',
    version = '1.0',
    packages = find_packages(),

    install_requires = ['PyYAML', 'jsontemplate', 'python-dateutil'],

    author = 'Terence Honles',
    author_email = 'terence@honles.com',
    description = 'Alternative web interface for GNU Mailman mail archives',
    long_description = documentation,
    license = 'PSF',
    keywords = 'Mailman WebArchive Pipermail Archives Mail Email',
    url = 'https://github.com/terencehonles/mailarchive',

    entry_points = {
        'console_scripts': [
            'mbox2json = mailarchive.utils:run_convert',
            'mailarchive = mailarchive.utils:run_mailarchive',
        ],
    },

    package_data = {
        'mailarchive': [
            # Templates
            'mailarchive/data/templates/*.jst',
            'mailarchive/data/templates/partials/*.jst',

            # Scripts
            'mailarchive/data/scripts/*.js',
            'mailarchive/data/scripts/*.js.jst',

            # Styles
            'mailarchive/data/styles/*.css',
        ],
    }
)
