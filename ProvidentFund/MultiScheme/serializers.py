from rest_framework import serializers
from .models import Tenant

# create Tenant Serializers
class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model= Tenant
        fields = ['id','name','api_endpoint_member','api_endpoint_contribution','tel_number','email','address']