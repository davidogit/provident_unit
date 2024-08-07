from MultiScheme.models import Tenant
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.db import models

class User(AbstractUser):
    # Adding a tenant field to the User model
    tenant = models.ForeignKey(Tenant, null=True, on_delete=models.CASCADE)
    
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
    # Role name with a maximum length of 50 characters
    name = models.CharField(max_length=50)
    # Many-to-many relationship with permissions
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        # String representation of the Role object
        return self.name
