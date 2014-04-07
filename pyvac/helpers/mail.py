# Import smtplib for the actual sending function
import smtplib
# Import the email modules we'll need
from email.mime.text import MIMEText
import logging

log = logging.getLogger(__name__)


class SmtpWrapper(object):
    """ Simple smtp class wrapper"""
    host = None
    port = None
    starttls = None
    must_auth = None
    starttls = None
    login = None
    password = None
    _from = None

    def __init__(self, config):

        self.host = config['host']
        self.port = config.get('port', 25)
        self.starttls = config['starttls']
        self.must_auth = config['must_auth']
        self.login = config['login']
        self.password = config['password']
        self._from = config['from']

        log.info('Smtp wrapper initialized')

    def send_mail(self, src, dst, req_type, text):
        """ Send a mail through smtp using given parameters """
        # Create a text/plain message
        msg = MIMEText(text)

        msg['Subject'] = 'Request %s' % req_type
        msg['From'] = src
        msg['To'] = dst

        conn = smtplib.SMTP(self.host, self.port)
        if self.starttls:
            conn.starttls()
        _from = self._from if self._from else src
        conn.sendmail(_from, [dst], msg.as_string())
        conn.quit()

        log.info('Message sent through SMTP.')


class SmtpCache(object):
    """ Email cache class singleton """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            raise RuntimeError('Email is not initialized')

        return cls._instance

    @classmethod
    def configure(cls, settings):
        cls._instance = cls.from_config(settings)

    @classmethod
    def from_config(cls, config, **kwargs):
        """
        Return a Email object configured from the given configuration.
        """
        return SmtpWrapper(config)
