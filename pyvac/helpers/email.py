from __future__ import absolute_import

# Import smtplib for the actual sending function
import smtplib
# Import the email modules we'll need
from email.mime.text import MIMEText
import logging

log = logging.getLogger(__name__)


def send_mail(src, dst, req_type, text):

    # Create a text/plain message
    msg = MIMEText(text)

    msg['Subject'] = 'Request %s' % req_type
    msg['From'] = src
    msg['To'] = dst

    s = smtplib.SMTP('mail.example.com', 25)
    s.sendmail(src, [dst], msg.as_string())
    s.quit()

    log.info('Message sent through SMTP.')
