import email
import os.path
import time

from django.conf import settings
from django.test import TestCase

from django_mail_admin import models
from django_mail_admin.models import Mailbox, IncomingEmail
from django_mail_admin.settings import get_allowed_mimetypes,strip_unallowed_mimetypes,get_text_stored_mimetypes
class EmailIntegrationTimeout(Exception):
    pass


def get_email_as_text(name):
    with open(
        os.path.join(
            os.path.dirname(__file__),
            'messages',
            name,
        ),
        'rb'
    ) as f:
        return f.read()


class EmailMessageTestCase(TestCase):
    ALLOWED_EXTRA_HEADERS = [
        'MIME-Version',
        'Content-Transfer-Encoding',
    ]

    def setUp(self):

        self._ALLOWED_MIMETYPES = get_allowed_mimetypes()
        self._STRIP_UNALLOWED_MIMETYPES = (
            strip_unallowed_mimetypes()
        )
        self._TEXT_STORED_MIMETYPES = get_text_stored_mimetypes()

        self.mailbox = Mailbox.objects.create(from_email='from@example.com')

        self.test_account = os.environ.get('EMAIL_ACCOUNT')
        self.test_password = os.environ.get('EMAIL_PASSWORD')
        self.test_smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
        self.test_from_email = 'nobody@nowhere.com'

        self.maximum_wait_seconds = 60 * 5

        settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
        settings.EMAIL_HOST = self.test_smtp_server
        settings.EMAIL_PORT = 587
        settings.EMAIL_HOST_USER = self.test_account
        settings.EMAIL_HOST_PASSWORD = self.test_password
        settings.EMAIL_USE_TLS = True
        super(EmailMessageTestCase, self).setUp()

    def _get_new_messages(self, mailbox, condition=None):
        maximum_wait = time.time() + self.maximum_wait_seconds
        while True:
            if time.time() > maximum_wait:
                raise EmailIntegrationTimeout()
            if messages := self.mailbox.get_new_mail(condition):
                return messages
            time.sleep(5)

    def _get_email_as_text(self, name):
        with open(
            os.path.join(
                os.path.dirname(__file__),
                'messages',
                name,
            ),
            'rb'
        ) as f:
            return f.read()

    def _get_email_object(self, name):
        copy = self._get_email_as_text(name)
        return email.message_from_bytes(copy)

    def _headers_identical(self, left, right, header=None):
        """ Check if headers are (close enough to) identical.

         * This is particularly tricky because Python 2.6, Python 2.7 and
           Python 3 each handle header strings slightly differently.  This
           should mash away all of the differences, though.
         * This also has a small loophole in that when re-writing e-mail
           payload encodings, we re-build the Content-Type header, so if the
           header was originally unquoted, it will be quoted when rehydrating
           the e-mail message.

        """
        if header.lower() == 'content-type':
            # Special case; given that we re-write the header, we'll be quoting
            # the new content type; we need to make sure that doesn't cause
            # this comparison to fail.  Also, the case of the encoding could
            # be changed, etc. etc. etc.
            left = left.replace('"', '').upper()
            right = right.replace('"', '').upper()
        left = left.replace('\n\t', ' ').replace('\n ', ' ')
        right = right.replace('\n\t', ' ').replace('\n ', ' ')
        return right == left

    def compare_email_objects(self, left, right):
        # Compare headers
        for key, value in left.items():
            if not right[key]:
                if key in self.ALLOWED_EXTRA_HEADERS:
                    continue
                raise AssertionError("Extra header '%s'" % key)
            if not self._headers_identical(right[key], value, header=key):
                raise AssertionError(
                    "Header '%s' unequal:\n%s\n%s" % (
                        key,
                        repr(value),
                        repr(right[key]),
                    )
                )
        for key, value in right.items():
            if not left[key]:
                if key in self.ALLOWED_EXTRA_HEADERS:
                    continue
                raise AssertionError("Extra header '%s'" % key)
            if not self._headers_identical(left[key], value, header=key):
                raise AssertionError(
                    "Header '%s' unequal:\n%s\n%s" % (
                        key,
                        repr(value),
                        repr(right[key]),
                    )
                )
        if left.is_multipart() != right.is_multipart():
            self._raise_mismatched(left, right)
        if left.is_multipart():
            left_payloads = left.get_payload()
            right_payloads = right.get_payload()
            if len(left_payloads) != len(right_payloads):
                self._raise_mismatched(left, right)
            for n in range(len(left_payloads)):
                self.compare_email_objects(
                    left_payloads[n],
                    right_payloads[n]
                )
        elif left.get_payload() is None or right.get_payload() is None:
            if left.get_payload() is None and right.get_payload is not None:
                self._raise_mismatched(left, right)
            if right.get_payload() is None and left.get_payload is not None:
                self._raise_mismatched(left, right)
        elif left.get_payload().strip() != right.get_payload().strip():
            self._raise_mismatched(left, right)

    def _raise_mismatched(self, left, right):
        raise AssertionError(
            "IncomingEmail payloads do not match:\n%s\n%s" % (
                left.as_string(),
                right.as_string()
            )
        )

    def assertEqual(self, left, right):  # noqa: N802
        return (
            self.compare_email_objects(left, right)
            if isinstance(left, email.message.Message)
            else super(EmailMessageTestCase, self).assertEqual(left, right)
        )

    def tearDown(self):
        for message in IncomingEmail.objects.all():
            message.delete()
        models.ALLOWED_MIMETYPES = self._ALLOWED_MIMETYPES
        models.STRIP_UNALLOWED_MIMETYPES = self._STRIP_UNALLOWED_MIMETYPES
        models.TEXT_STORED_MIMETYPES = self._TEXT_STORED_MIMETYPES

        self.mailbox.delete()
        super(EmailMessageTestCase, self).tearDown()
