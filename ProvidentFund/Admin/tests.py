from django.test import TestCase
from .models import Role

# Test case for the Role model
class RoleModelTest(TestCase):
    
    # Setup method to create a Role object before running tests
    def setUp(self):
        # Create a Role object with the name "Admin"
        Role.objects.create(name="Admin")

    # Test method to verify the role name
    def test_role_name(self):
        # Retrieve the Role object with the name "Admin"
        role = Role.objects.get(name="Admin")
        # Assert that the name of the retrieved Role object is "Admin"
        self.assertEqual(role.name, "Admin")
