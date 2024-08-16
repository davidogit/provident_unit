from django.db import models
from django.contrib.auth.models import User
from MultiScheme.models import Tenant
from django.conf import settings

# Create your models here.

class Member(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE,null=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member')
    staff_id = models.PositiveIntegerField(unique=True, null=False, blank=False)
    tel_number = models.PositiveIntegerField()


    def __str__(self):
        return f'{self.user.username}\'s account'
