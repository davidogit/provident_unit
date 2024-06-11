from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.PositiveIntegerField(unique=True, null=False, blank=False)
    tel_number = models.PositiveIntegerField()
    name = models.CharField(max_length=40)

    def __str__(self):
        return f'{self.user.username}\'s account'
