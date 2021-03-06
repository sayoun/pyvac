import re
import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

with open(os.path.join(here, 'pyvac', '__init__.py')) as v_file:
    version = re.compile(r".*__version__ = '(.*?)'",
                         re.S).match(v_file.read()).group(1)

requires = [
    'cryptacular',
    'caldav',
    'celery',
    'icalendar',
    'jsonschema >=0.7',
    'kombu',
    'redis',
    'passlib',
    'psycopg2',
    'pyramid',
    'pyramid_jinja2',
    'pyramid_tm',
    'python-ldap',
    'pyyaml',
    'simplejson >=2.1',
    'SQLAlchemy',
    'translationstring',
    'unidecode',
    'workalendar < 1.0',
    'zope.sqlalchemy',
    # dev only
    'waitress',
]

tests_require = ['nose', 'mock', 'tox', 'freezegun']
extras_require = {
    'test': tests_require,
}

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
      tests_require=tests_require,
      extras_require=extras_require,
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
      data_files=data_files,
      )
