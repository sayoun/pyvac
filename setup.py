import re
import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

with open(os.path.join(here, 'pyvac', '__init__.py')) as v_file:
    version = re.compile(r".*__version__ = '(.*?)'",
                         re.S).match(v_file.read()).group(1)

requires = [
    'pyramid',
    'waitress',
    'SQLAlchemy',

    'pyramid_filterwarnings',
    'pyramid_jinja2',
    'pyramid_tm',
    'zope.sqlalchemy',

    'celery==2.5.3',
    'redis',
    # debian kombu package version does not exist in version 2.5.X
    'kombu==2.1.8',
    'simplejson >=2.1, <3',
    'jsonschema >=0.7, <0.8',
    'pyyaml',

    'cryptacular',
    # 'requests >=1.2, <1.0',  # version excluded bugs in case a proxy is used
    # 'docutils',
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
      keywords='web wsgi bfg pylons pyramid',
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
      """,
      paster_plugins=['pyramid'],
      data_files=data_files,
      )
