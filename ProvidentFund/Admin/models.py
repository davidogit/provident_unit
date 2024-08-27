from MultiScheme.models import Tenant
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.db import models

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
