
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, Role

class UserForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2',)

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ('name', 'permissions')
