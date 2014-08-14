import re
import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

with open(os.path.join(here, 'pyvac', '__init__.py')) as v_file:
    version = re.compile(r".*__version__ = '(.*?)'",
                         re.S).match(v_file.read()).group(1)

requires = [
    'pyramid',
    'SQLAlchemy',

    'pyramid_jinja2',
    'pyramid_tm',
    'zope.sqlalchemy',

    'celery',
    'kombu',
    'simplejson >=2.1',
    'jsonschema >=0.7',
    'pyyaml',

    'cryptacular',
    'passlib',

    'caldav',
    'icalendar',
    'python-ldap',
]

if sys.version_info[:2] < (2, 7):
    requires.extend(['logutils'])

data_files = []

setup(name='pyvac',
      version=version,
      description='pyvac',
      long_description=README + '\n\n' + CHANGES,
      classifiers=["Programming Language :: Python",
                   "Framework :: Pyramid",
                   "Topic :: Internet :: WWW/HTTP",
                   "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
                   ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='pyvac',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = pyvac:main
      [console_scripts]
      pyvac_install = pyvac.bin.install:main
      pyvac_shell = pyvac.bin.shell:main
      pyvac_celeryd = pyvac.bin.celerycmd:celeryd
      pyvac_import = pyvac.bin.importldap:main
      pyvac_replay = pyvac.bin.replay:main
      """,
      paster_plugins=['pyramid'],
      data_files=data_files,
      )
