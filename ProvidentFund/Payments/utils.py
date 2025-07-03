import requests
from django.conf import settings

class PaystackAPI:
    base_url = "https://api.paystack.co"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    @classmethod
    def verify_transaction(cls, reference):
        url = f"{cls.base_url}/transaction/verify/{reference}"
        response = requests.get(url, headers=cls.headers)
        return response.json()
