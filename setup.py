#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

from setuptools import setup, find_packages

with open('README') as readme:
    documentation = readme.read()

setup(
    name = 'mailarchive',
    version = '1.0',
    packages = find_packages(),

    install_requires = ['jsontemplate', 'python-dateutil'],

    author = 'Terence Honles',
    author_email = 'terence@honles.com',
    description = 'Alternative web interface for GNU Mailman mail archives',
    long_description = documentation,
    license = 'PSF',
    keywords = 'Mailman WebArchive Pipermail Archives Mail Email',

    entry_points = {
        'console_scripts': [
            'mbox2json = mailarchive.utils:run_convert',
        ],
    },
)
