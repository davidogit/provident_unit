from django.db import models
from MultiScheme.models import InvestmentScheme,Tenant
from Fund.models import AuditTrail
from django.utils import timezone
import json
from django.db.models.signals import pre_delete,post_save
from django.dispatch import receiver
from django.utils.encoding import force_str
from Fund.middleware import get_current_user
# from simple_history.models import HistoricalRecords
# from django.utils import timezone

class StaffAPI(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    # Using Many-to-Many relationship to allow users to have multiple schemes
    investment_scheme = models.ManyToManyField(InvestmentScheme)
    Id = models.AutoField(primary_key=True, unique=True,editable=False)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    staff_number = models.IntegerField(unique=True)
    date_joined = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, blank=True, null=True, default='active')
    fund_type = models.CharField(max_length=50)
    _amount = models.FloatField(null=True,blank=True,default=0.00)
    exited_date = models.DateField(null=True, blank=True)
    exited_flag = models.BooleanField(default=False)
    profit = models.FloatField(default=0.00)
    actual_profit = models.FloatField(default=0.00)
    subscription_date = models.DateField(null=True)
    updated_date = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f'{self.last_name} {self.first_name}'
    
    @property
    def amount(self):
        return self._amount
    
    @amount.setter
    def amount(self,value):
        self._amount += value



# Signals for StaffAPI
@receiver(post_save, sender=StaffAPI)
def audit_log_save(sender,instance,created,update_fields,**kwargs):
    object_id = instance.pk

    action = 'created' if created else 'updated'

    # User making the change
    user = get_current_user() or None
    # Assign name 
    if created:
        instance.name = user.username
        instance.save()

    # Get changes to model
    changes = {}

    for field in instance._meta.fields:
        field_name = field.name
        new_value = getattr(instance,field_name)
        changes[field_name] = force_str(new_value)
    
    

    # Create an AuditTrail instance
    AuditTrail.objects.create(
        user = user,
        model_name = StaffAPI.__name__,
        action = action,
        object_id = object_id,
        changes = json.dumps(changes),
        timestamp = timezone.now(),
        name = user.username
    )

@receiver(pre_delete, sender=StaffAPI)
def audit_log_delete(sender,instance,**kwargs):
    object_id = instance.pk

    action = 'deleted'

    user = get_current_user() 
    # get_object_or_404(get_user_model(),id=instance.pk)

    # Create an AuditTrail instance
    AuditTrail.objects.create(
        user = user,
        model_name = StaffAPI.__name__,
        action = action,
        object_id = object_id,
        changes = f'User {user.username} made a delete operation at {timezone.now()}',
        timestamp = timezone.now(),
        name = user.username
    )



class Contribution(models.Model):
    # tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True)
    investment_scheme = models.ForeignKey(InvestmentScheme, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(StaffAPI, on_delete=models.CASCADE)
    month = models.CharField(max_length=20)
    year = models.CharField(max_length=4)
    employee_amount = models.FloatField()
    employer_amount = models.FloatField()
    retro_employee_amount = models.FloatField()
    retro_employer_amount = models.FloatField()
    contribution_date = models.DateField()


    def calculated_total_contributions(self):
        a = self.employee_amount
        b = self.employer_amount
        c = self.retro_employee_amount
        d = self.retro_employer_amount
        
        return (a + b + c + d)

    @property
    def total_contributions(self):
        return self.calculated_total_contributions()

    def __str__(self):
        return f"{self.member.last_name}'s - {self.month} {self.year}"
    

    # Saving every contribution for user whenever a contribution is made
    def save(self, *args, **kwargs):

        super().save(*args,**kwargs)

        # update member.amount field
        self.member.amount = self.total_contributions
        self.member.save()
