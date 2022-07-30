from django.db.models import TextField
from django.utils.translation import ugettext_lazy as _

from .validators import validate_comma_separated_emails


class CommaSeparatedEmailField(TextField):
    default_validators = [validate_comma_separated_emails]
    description = _("Comma-separated emails")

    def __init__(self, *args, **kwargs):
        kwargs['blank'] = True
        super(CommaSeparatedEmailField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {
            'error_messages': {
                'invalid': _('Only comma separated emails are allowed.'),
            }
        } | kwargs

        return super(CommaSeparatedEmailField, self).formfield(**defaults)

    def from_db_value(self, value, expression, connection, context=None):
        return self.to_python(value)

    def get_prep_value(self, value):
        """
        We need to accomodate queries where a single email,
        or list of email addresses is supplied as arguments. For example:

        - OutgoingEmail.objects.filter(to='mail@example.com')
        - OutgoingEmail.objects.filter(to=['one@example.com', 'two@example.com'])
        """
        if isinstance(value, str):
            return value
        else:
            return ', '.join(map(lambda s: s.strip(), value))

    def to_python(self, value):
        if isinstance(value, str):
            return [] if value == '' else [s.strip() for s in value.split(',')]
        else:
            return value
