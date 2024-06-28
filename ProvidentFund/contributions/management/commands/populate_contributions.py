from django.core.management.base import BaseCommand
from contributions.models import StaffAPI, Contribution
from datetime import datetime
import calendar

class Command(BaseCommand):
    help = 'Populate contributions for each member starting from 2020'

    def handle(self, *args, **kwargs):
        start_year = 2020
        end_year = datetime.now().year

        months = [calendar.month_name[i] for i in range(1, 13)]

        members = StaffAPI.objects.all()
        for member in members:
            for year in range(start_year, end_year + 1):
                for month in months:
                    Contribution.objects.get_or_create(
                        member=member,
                        month=month,
                        year=str(year),
                        defaults={
                            'EmployeeAmount': 0,
                            'EmployerAmount': 0,
                            'RetroEmployeeAmount': 0,
                            'RetroEmployerAmount': 0,
                            'Employee55Amount': 0,
                            'Employer55Amount': 0,
                            'RetroEmployee55Amount': 0,
                            'RetroEmployer55Amount': 0,
                            'ContributionDate': datetime.strptime(f'01 {month} {year}', '%d %B %Y')
                        }
                    )
        self.stdout.write(self.style.SUCCESS('Successfully populated contributions for each member'))
