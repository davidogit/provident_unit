from django.db.models.signals import post_save,pre_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver,Signal
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.encoding import force_str
import json
from Fund.models import AuditTrail
from .middleware import get_current_user
from django.contrib.auth.models import AnonymousUser

# Update and Create signal definition
@receiver(post_save)
def audit_log_save(sender,instance,created,**kwargs):
    if sender == AuditTrail:
        # Omit changes on the AuditTrail model
        return

    model_name = ContentType.objects.get_for_model(sender).model
    object_id = instance.pk

    action = 'created' if created else 'updated'

    # get user from middleware
    user = get_current_user()

    # Check if the user is authenticated before creating an audit trail entry
    if user and isinstance(user, AnonymousUser) or (user.is_anonymous if hasattr(user, 'is_anonymous') else True):
        user = None  # Set to None or handle appropriately, e.g., use a default user

    # Get changes to model
    changes = {}

    for field in instance._meta.fields:
        field_name = field.name
        new_value = getattr(instance,field_name)
        changes[field_name] = force_str(new_value)
    
    # Create an AuditTrail instance
    AuditTrail.objects.create(
        user = user,
        model_name = model_name,
        action = action,
        object_id = object_id,
        changes = json.dumps(changes),
        timestamp = timezone.now()
    )


# Delete signal definition
@receiver(pre_delete)
def audit_log_delete(sender,instance,**kwargs):
    if sender == AuditTrail:
        return
    
    model_name = ContentType.objects.get_for_model(sender).model
    object_id = instance.pk

    user = get_current_user()

    # Check if the user is authenticated before creating an audit trail entry
    if user and isinstance(user, AnonymousUser) or (user.is_anonymous if hasattr(user, 'is_anonymous') else True):
        user = None  # Set to None or handle appropriately, e.g., use a default user

    action = 'deleted'

    AuditTrail.objects.create(
        user = user,
        model_name = model_name,
        action = action,
        object_id = object_id,
        changes = '',
        timestamp = timezone.now()
    )


# Signal definition for user login and logout

# Log in signal
@receiver(user_logged_in)
def audit_log_user_log_in(sender,user,**kwargs):
    # Create an AuditTrail whenever a user logs in onto the system

    AuditTrail.objects.create(
        user = user,
        model_name = 'User',
        action = 'logged in',
        object_id = user.pk,
        changes = f'{user.username} logged in at {timezone.now()}',
        timestamp = timezone.now()
    )

# Log out signal
@receiver(user_logged_out)
def audit_log_user_log_out(sender,user,**kwargs):
    # Create an AuditTrail whenever a user logs out

    AuditTrail.objects.create(
        user = user,
        model_name = 'User',
        action = 'logged out',
        object_id = user.pk,
        changes = f'{user.username} logged out at {timezone.now()}',
        timestamp = timezone.now()
    )