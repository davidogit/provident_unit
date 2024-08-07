from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, Permission
from django.utils.translation import gettext_lazy as _
from .models import User, Tenant
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class UserAdmin(BaseUserAdmin):

    add_form = UserCreationForm
    form = UserChangeForm
    model = User


    # Define the fields to be used in displaying the User model.
    # These fields will be displayed in the 'list' view of the admin.
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'tenant')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'tenant')
    
    # Fields to be used in displaying the User model in the 'change' view of the admin.
    # These fields will be displayed in the order defined here.
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Tenant info'), {'fields': ('tenant',)}),
    )
    
    # Fields to be used when creating a User via the admin interface.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'tenant'),
        }),
    )
    
    # These fields will be used to search the User model in the admin interface.
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions',)

# Register the new UserAdmin
admin.site.register(User, UserAdmin)

# Unregister the Group model from admin. If you still want to manage groups in admin, you can remove the following line.
# admin.site.unregister(Group)
