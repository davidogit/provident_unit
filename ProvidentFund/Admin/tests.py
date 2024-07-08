
from django.test import TestCase
from .models import Role

class RoleModelTest(TestCase):
    def setUp(self):
        Role.objects.create(name="Admin")

    def test_role_name(self):
        role = Role.objects.get(name="Admin")
        self.assertEqual(role.name, "Admin")

