import string
import random

# Investment INVOICE number generator
def generate_invoice_number():
    length = 6
    while True:
        invoice_number = ''.join(random.choices(string.digits,k=length))

        return invoice_number