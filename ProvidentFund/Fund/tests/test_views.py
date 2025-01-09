from django.test import TestCase,Client
from Fund.models import InvestmentDetail,InvestmentScheme,BankInterest
from django.urls import reverse
from Fund.views import Invest
from MultiScheme.models import Tenant
from Admin.models import User

class TestInvestView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            username = 'testuser',
            password = 'password'
        )
        self.url = reverse('finance_page', args=[1])
        Tenant.objects.create(
            name ='Tenant 1',
        )

    def test_invest_view_authenticated_GET(self):
        
        self.client.login(username = 'testuser',password = 'password')

        response = self.client.get(self.url,)

        self.assertEquals(response.status_code, 200)
        # self.assertEquals(response, 'login.html')