from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProvidentFund.settings')


app = Celery('ProvidentFund')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Celery beat Scheduler

app.conf.beat_schedule = {
    'daily_calculation':{
        'task':'Fund.tasks.member_interest',
        'schedule': crontab(hour='*', minute='*', day_of_week='*', day_of_month='*', month_of_year='*'),
    },
    'reduce_day_by_1':{
        'task': 'Fund.tasks.reduce_date',
        'schedule': crontab(hour='*', minute='*', day_of_week='*', day_of_month='*', month_of_year='*')
    }
}


app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')