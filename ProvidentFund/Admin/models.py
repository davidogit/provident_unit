
from MultiScheme.models import Tenant
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models

class User(AbstractUser):
    tenant = models.ForeignKey(Tenant, default = "", on_delete=models.CASCADE)
    groups = models.ManyToManyField(
        Group,
        related_name='admin_user_set', 
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='admin_user_permissions_set',  
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
        related_query_name='user',
    )

class Role(models.Model):
    name = models.CharField(max_length=50)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name

