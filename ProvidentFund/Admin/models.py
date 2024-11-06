import json
from django.dispatch import receiver
from django.db.models.signals import post_save,pre_delete,pre_save
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_str
from Fund.models import AuditTrail
from django.contrib.auth import get_user_model
from MultiScheme.models import Tenant
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.db import models
# from simple_history.models import HistoricalRecords
from django.conf import settings
from django.utils import timezone


class User(AbstractUser):
    tenant = models.ForeignKey(Tenant, null=True, on_delete=models.CASCADE)
    inactive_status = models.BooleanField(default=False)
    
    # Use unique related_name to avoid conflict with the built-in User model
    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_set',  # Updated related_name
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions_set',  # Updated related_name
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

    # History
    # history = HistoricalRecords()

class Role(models.Model):
    name = models.CharField(max_length=50)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name

# Add the Activity model here
class Activity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # ForeignKey to your custom User model
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.description} at {self.timestamp}"


@receiver(post_save, sender=User)
def audit_log_save(sender,instance,created,**kwargs):
    from Fund.middleware import get_current_user
    object_id = instance.pk

    action = 'created' if created else 'updated'
    user = get_current_user()
    # get_object_or_404(get_user_model(),id=instance.pk)
    # Assign name 
    if created:
        instance.name = user.username
        instance.save()

    # Get changes to model
    changes = {}

    for field in instance._meta.fields:
        field_name = field.name
        new_value = getattr(instance,field_name)
        changes[field_name] = force_str(new_value)
    
    

    # Create an AuditTrail instance
    # AuditTrail.objects.create(
    #     user = user,
    #     model_name = User.__name__,
    #     action = action,
    #     object_id = object_id,
    #     changes = json.dumps(changes),
    #     timestamp = timezone.now(),
    #     name = user.username
    # )

@receiver(pre_delete, sender=User)
def audit_log_delete(sender,instance,**kwargs):
    from Fund.middleware import get_current_user
    object_id = instance.pk

    action = 'deleted'
    
    user = get_current_user()
    # get_object_or_404(get_user_model(),id=instance.pk)

    # Create an AuditTrail instance
    AuditTrail.objects.create(
        user = user,
        model_name = User.__name__,
        action = action,
        object_id = object_id,
        changes = f'User {user.username} made a delete operation at {timezone.now()}',
        timestamp = timezone.now(),
        name = user.username
    )
