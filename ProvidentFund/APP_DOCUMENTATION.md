# Application Documentation

## Admin App

### Overview

The Admin app handles user management, authentication, and system administration. It implements multi-tenancy and role-based access control.

### Models

#### User

- **Description**: Custom user model extending Django's AbstractUser
- **Fields**:
  - tenant (ForeignKey to Tenant)
  - inactive_status (BooleanField)
  - groups (ManyToManyField to Group)
  - user_permissions (ManyToManyField to Permission)

#### Role

- **Description**: Defines system roles and their permissions
- **Fields**:
  - name (CharField)
  - permissions (ManyToManyField to Permission)

#### Activity

- **Description**: Logs user activities in the system
- **Fields**:
  - user (ForeignKey to User)
  - description (CharField)
  - timestamp (DateTimeField)

### Key Features

- Multi-tenant user management
- Role-based access control
- Activity logging
- User authentication and authorization
- Admin dashboard

## Member App

### Overview

The Member app manages member profiles, registrations, and member-specific operations.

### Models

#### Member

- **Description**: Stores member information
- **Fields**:
  - user (OneToOneField to User)
  - member_id (CharField)
  - date_of_birth (DateField)
  - address (TextField)
  - phone_number (CharField)
  - employment_details (JSONField)
  - status (CharField)

#### MemberDocument

- **Description**: Stores member-related documents
- **Fields**:
  - member (ForeignKey to Member)
  - document_type (CharField)
  - file (FileField)
  - upload_date (DateTimeField)

### Key Features

- Member registration
- Profile management
- Document management
- Member status tracking

## Fund App

### Overview

The Fund app handles fund management, contributions, and financial operations.

### Models

#### Fund

- **Description**: Represents a provident fund
- **Fields**:
  - name (CharField)
  - scheme (ForeignKey to Scheme)
  - balance (DecimalField)
  - status (CharField)
  - created_at (DateTimeField)

#### Contribution

- **Description**: Records member contributions
- **Fields**:
  - member (ForeignKey to Member)
  - fund (ForeignKey to Fund)
  - amount (DecimalField)
  - date (DateField)
  - contribution_type (CharField)
  - status (CharField)

### Key Features

- Fund management
- Contribution tracking
- Financial reporting
- Balance calculations

## Chart of Accounts

### Overview

The Chart of Accounts app manages financial accounts and transactions.

### Models

#### Account

- **Description**: Represents a financial account
- **Fields**:
  - code (CharField)
  - name (CharField)
  - type (CharField)
  - parent (ForeignKey to self)
  - balance (DecimalField)
  - is_active (BooleanField)

#### Transaction

- **Description**: Records financial transactions
- **Fields**:
  - account (ForeignKey to Account)
  - amount (DecimalField)
  - type (CharField)
  - date (DateTimeField)
  - reference (CharField)
  - description (TextField)

### Key Features

- Account hierarchy management
- Transaction recording
- Balance tracking
- Financial reporting

## MultiScheme App

### Overview

The MultiScheme app manages multiple provident fund schemes within the system.

### Models

#### Scheme

- **Description**: Defines a provident fund scheme
- **Fields**:
  - name (CharField)
  - code (CharField)
  - description (TextField)
  - rules (JSONField)
  - status (CharField)
  - created_at (DateTimeField)

#### Tenant

- **Description**: Represents a tenant organization
- **Fields**:
  - name (CharField)
  - code (CharField)
  - address (TextField)
  - contact_info (JSONField)
  - status (CharField)

### Key Features

- Scheme management
- Multi-tenant support
- Scheme rules configuration
- Tenant management

## Common Features

### Authentication & Authorization

- Multi-tenant authentication
- Role-based access control
- Session management
- Password policies

### Data Management

- Data isolation between tenants
- Audit logging
- Data backup and recovery
- Data validation

### Reporting

- Financial reports
- Member reports
- Contribution reports
- Audit reports

### Security

- CSRF protection
- XSS prevention
- SQL injection protection
- Rate limiting

### Performance

- Database optimization
- Caching
- Background task processing
- API rate limiting

## Development Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Write docstrings for functions
- Comment complex logic

### Testing

- Write unit tests
- Implement integration tests
- Use test fixtures
- Maintain test coverage

### Deployment

- Use environment variables
- Implement logging
- Monitor performance
- Regular backups

### Maintenance

- Regular updates
- Security patches
- Performance optimization
- Bug fixes
