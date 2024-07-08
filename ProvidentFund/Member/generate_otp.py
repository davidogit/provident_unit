import random
import string
# from .models import Member

def generate_unique_code():
    length = 4 
    while True:
        code = ''.join(random.choices(string.digits, k=length))
        # if not Member.objects.filter(otp_secret=code).exists():
        return code

# class YourModel(models.Model):
#     code = models.CharField(max_length=10, unique=True, default=generate_unique_code)

# default = generate_unique_code()

# print(default)