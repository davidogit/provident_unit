import string
import random

# Investment INVOICE number generator
def generate_invoice_number():
    length = 6
    while True:
        invoice_number = ''.join(random.choices(string.digits,k=length))

        return invoice_number

def generate_short_alpha_numeric_id(model, length=12):
    while True:
        # Generate a random alphanumeric string of the specified length
        gen_id = ''.join(random.choices(string.digits + string.ascii_lowercase, k=length))
        # Check if the generated ID is unique
        if not model.objects.filter(id=gen_id).exists():
            return gen_id