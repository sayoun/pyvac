
settings = {'jinja2.directories': 'pyvac:templates',
            'jinja2.filters': '\nflash_type = pyvac.helpers.util:flash_type\nflash_msg = pyvac.helpers.util:flash_msg\nhournow = pyvac.helpers.util:hournow\ndatenow = pyvac.helpers.util:datenow\nschedule_date = pyvac.helpers.util:schedule_date\nis_manager = pyvac.helpers.util:is_manager',
            'sqlalchemy.echo': False,
            'sqlalchemy.url': 'sqlite://',
            'sqlalchemy.pool_size': 1,
            'pyvac.cookie_key': 's3cr3t3c00k13',
            }
