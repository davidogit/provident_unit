# API Documentation

## Admin App

### Authentication Endpoints

#### Login

- **URL**: `/admin/login/<tenant_id>/`
- **Method**: POST
- **Description**: Authenticate user and create session
- **Request Body**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **Response**: Redirects to admin panel on success

#### Logout

- **URL**: `/admin/logout/<tenant_id>/`
- **Method**: GET
- **Description**: End user session
- **Response**: Redirects to login page

### User Management Endpoints

#### Add User

- **URL**: `/admin/add_user/<tenant_id>/`
- **Method**: POST
- **Description**: Create new user in the system
- **Required Role**: Admin
- **Request Body**: UserForm data
- **Response**: Redirects to assign roles page

#### Assign Roles

- **URL**: `/admin/assign_roles/<tenant_id>/`
- **Method**: POST
- **Description**: Assign roles to users
- **Required Role**: Admin
- **Request Body**:
  ```json
  {
    "username": "string",
    "role": "string"
  }
  ```
- **Response**: Success/error message

#### Manage Users

- **URL**: `/admin/manage_users/<tenant_id>/`
- **Method**: GET, POST
- **Description**: View and manage user roles
- **Required Role**: Admin
- **Response**: User management interface

#### Delete User

- **URL**: `/admin/delete_user/<tenant_id>/<user_id>/`
- **Method**: POST
- **Description**: Remove user from system
- **Required Role**: Admin
- **Response**: Redirects to manage users page

### Activity Logging

- **Model**: Activity
- **Fields**:
  - user (ForeignKey to User)
  - description (CharField)
  - timestamp (DateTimeField)

## Member App

### Member Management Endpoints

#### Member Registration

- **URL**: `/member/register/`
- **Method**: POST
- **Description**: Register new member
- **Request Body**: Member registration form data
- **Response**: Member profile page

#### Member Profile

- **URL**: `/member/profile/<member_id>/`
- **Method**: GET
- **Description**: View member details
- **Required Role**: Member, Admin
- **Response**: Member profile data

#### Update Member Details

- **URL**: `/member/update/<member_id>/`
- **Method**: POST
- **Description**: Update member information
- **Required Role**: Member, Admin
- **Request Body**: Updated member data
- **Response**: Updated profile page

## Fund App

### Fund Management Endpoints

#### Fund Overview

- **URL**: `/fund/overview/`
- **Method**: GET
- **Description**: View fund statistics and summary
- **Required Role**: Admin, HR
- **Response**: Fund overview dashboard

#### Contribution Management

- **URL**: `/fund/contributions/`
- **Method**: GET, POST
- **Description**: Manage member contributions
- **Required Role**: Admin, HR
- **Response**: Contribution management interface

#### Fund Reports

- **URL**: `/fund/reports/`
- **Method**: GET
- **Description**: Generate fund reports
- **Required Role**: Admin
- **Query Parameters**:
  - start_date
  - end_date
  - report_type
- **Response**: Report data in specified format

## Chart of Accounts

### Account Management Endpoints

#### Account List

- **URL**: `/chart_of_accounts/list/`
- **Method**: GET
- **Description**: View all accounts
- **Required Role**: Admin, Finance
- **Response**: List of accounts

#### Account Creation

- **URL**: `/chart_of_accounts/create/`
- **Method**: POST
- **Description**: Create new account
- **Required Role**: Admin
- **Request Body**: Account details
- **Response**: Created account data

#### Account Transactions

- **URL**: `/chart_of_accounts/transactions/<account_id>/`
- **Method**: GET
- **Description**: View account transactions
- **Required Role**: Admin, Finance
- **Response**: Transaction history

## MultiScheme App

### Scheme Management Endpoints

#### Scheme List

- **URL**: `/scheme/list/`
- **Method**: GET
- **Description**: View all schemes
- **Required Role**: Admin
- **Response**: List of schemes

#### Scheme Creation

- **URL**: `/scheme/create/`
- **Method**: POST
- **Description**: Create new scheme
- **Required Role**: Admin
- **Request Body**: Scheme details
- **Response**: Created scheme data

#### Scheme Configuration

- **URL**: `/scheme/configure/<scheme_id>/`
- **Method**: GET, POST
- **Description**: Configure scheme parameters
- **Required Role**: Admin
- **Response**: Scheme configuration interface

## Authentication & Authorization

### Role-Based Access Control

The system implements role-based access control with the following roles:

- Admin: Full system access
- HR: Member and contribution management
- Finance: Financial operations and reporting
- Member: Personal profile and contribution viewing

### Multi-Tenancy

All endpoints require tenant context:

- Tenant ID is included in URLs
- User authentication is tenant-specific
- Data isolation between tenants

### Security

- All endpoints require authentication
- Role-based authorization checks
- Session-based authentication
- CSRF protection enabled

## Error Handling

### Common Error Responses

- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

### Error Response Format

```json
{
  "error": "string",
  "message": "string",
  "details": {}
}
```

## Rate Limiting

- API requests are limited to 100 requests per minute per user
- Rate limit headers included in responses:
  - X-RateLimit-Limit
  - X-RateLimit-Remaining
  - X-RateLimit-Reset
