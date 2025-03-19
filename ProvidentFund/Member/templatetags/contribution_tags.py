from django import template
from django.db.models import Sum
from contributions.models import Contribution, StaffAPI, Tenant  

register = template.Library()

@register.simple_tag
def get_total_contribution(scheme, tenant, staff_number):
    """Fetch total approved contributions for a given scheme and staff number."""

    # Get the StaffAPI instance from the tenant
    member = tenant.staff_api.filter(staff_number=staff_number).first()

    # Ensure we now have a valid StaffAPI instance
    if not isinstance(member, StaffAPI):
        return "Invalid Member"

    # Get total contributions for this scheme and member
    total = Contribution.objects.filter(
        investment_scheme=scheme, 
        member=member, 
        approved_contribution=True
    ).aggregate(total=Sum('total_contribution'))['total']
    
    return total if total else 0.00  # Default to 0.00 if no contributions exist
