# Provident Fund Management System

A comprehensive Django-based web application for managing provident funds, including member management, contributions, and fund administration.

## Features

- Member Management
- Fund Administration
- Multi-Scheme Support
- Chart of Accounts
- Contribution Management
- Admin Dashboard
- Celery-based Background Tasks
- REST API Support

## Tech Stack

- **Backend Framework**: Django 5.0.7
- **Database**: MySQL
- **Task Queue**: Celery with Redis
- **API**: Django REST Framework & FastAPI
- **Testing**: pytest
- **Background Tasks**: django-celery-beat
- **SMS Integration**: AfricasTalking & Twilio

## Prerequisites

- Python 3.x
- MySQL Server
- Redis Server
- Virtual Environment (recommended)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd Provident-Fund
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r ProvidentFund/requirements.txt
```

4. Set up environment variables:
   Create a `.env` file in the project root with the following variables:

```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=mysql://user:password@localhost:3306/dbname
REDIS_URL=redis://localhost:6379/0
```

5. Run migrations:

```bash
cd ProvidentFund
python manage.py migrate
```

6. Create a superuser:

```bash
python manage.py createsuperuser
```

## Running the Application

1. Start the development server:

```bash
python manage.py runserver
```

2. Start Celery worker (in a separate terminal):

```bash
celery -A ProvidentFund worker -l info
```

3. Start Celery beat (in a separate terminal):

```bash
celery -A ProvidentFund beat -l info
```

## Project Structure

```
ProvidentFund/
├── Admin/              # Admin management module
├── Chart_of_Accounts/ # Financial accounting module
├── Fund/              # Fund management module
├── Member/            # Member management module
├── MultiScheme/       # Multi-scheme support
├── contributions/     # Contribution management
├── media/            # User-uploaded files
├── profile_images/   # User profile pictures
└── manage.py         # Django management script
```

## Testing

Run tests using pytest:

```bash
pytest
```

## API Documentation

The project includes both Django REST Framework and FastAPI endpoints. API documentation is available at:

- DRF API: `/api/docs/`
- FastAPI: `/api/v1/docs`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]

## Support

For support, please contact [your contact information]
