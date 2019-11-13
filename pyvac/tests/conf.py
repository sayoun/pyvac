

import os.path
from pyramid.paster import get_appsettings


here = os.path.dirname(__file__)
settings = get_appsettings(os.path.join(here, '../../', 'test.ini'))
