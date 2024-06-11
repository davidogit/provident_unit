from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.PositiveIntegerField(unique=True, null=False, blank=False, max_length=10)
    tel_number = models.PositiveIntegerField(max_length=10)

    def __str__(self):
        return f'{self.user.username}\'s account'
