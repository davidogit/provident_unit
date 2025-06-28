from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from MultiScheme.models import Tenant,InvestmentScheme
from django.db.models import UniqueConstraint
from django.core.exceptions import ValidationError

# Create your models here.
class AccountParameters(models.Model):
    """
    Represents account-specific parameters associated with a tenant.

    This model is used to define parameters related to account configurations
    for a specific tenant, such as the account code length. It establishes a
    foreign key relationship with the Tenant model, allowing for the association
    of multiple AccountParameters with a single Tenant instance.

    Attributes:
        tenant: Foreign key relation to the Tenant model, ensuring a link between
                these parameters and their respective tenant.
        account_code_length: Field specifying the length constraint on account codes.

    Meta:
        verbose_name: A human-readable singular name for the model.
        verbose_name_plural: A human-readable plural name for the model.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='account_params'
    )
    account_code_length = models.CharField(
        max_length=30,
    )

    class Meta:
        verbose_name = 'Account Parameter'
        verbose_name_plural = 'Account Parameters'
    




class ChartOfAccounts(models.Model):
    """
    Represents a Chart of Accounts models, typically used to define account structures within an
    organization. This model facilitates the classification of financial transactions into accounts,
    the organization of accounts hierarchically, and the calculation of balances for reporting
    and accounting purposes.

    The ChartOfAccounts model includes attributes for an account type, status, balance, and hierarchy.
    It provides functionality to manage accounts' relationships and to calculate aggregated balances
    of child accounts.

    Attributes:
        ACCOUNT_TYPES: List of valid types for the account classification. Possible values are
            'ASSET', 'REVENUE', 'CAPITAL', 'EXPENSE', and 'LIABILITY'.
        ACCOUNT_STATUS: List of statuses indicating the account's operational state. Can be 'ACTIVE'
            or 'CLOSED'.
    """
    ACCOUNT_TYPES =[
        ('ASSET', 'ASSET'),
        ('REVENUE', 'REVENUE'),
        ('CAPITAL', 'CAPITAL'),
        ('EXPENSE', 'EXPENSE'),
        ('LIABILITY', 'LIABILITY'),
    ]
    ACCOUNT_STATUS =[
        ('ACTIVE','ACTIVE'),
        ('CLOSED','CLOSED')
    ]
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=False,
        related_name='chart_of_accounts'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children'
    )
    name = models.CharField(
        max_length=255
    )
    description = models.TextField(
        null=True,
        blank=True
    )
    account_type = models.CharField(
        max_length=11,
        choices=ACCOUNT_TYPES,
        null=False,
        blank=False
    )
    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS,
        null=True,
        blank=True,
        default=''
    )
    account_code = models.CharField(
        max_length=20,
        unique=True,
        null=False
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0.00)
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = 'Chart of Account'
        verbose_name_plural = 'Chart of Accounts'
        ordering = ['account_code']
    
    def __str__(self):
        return f'{self.account_code} - {self.name}'
    
    # We can use this to get the hierarchy of an instance
    def get_hierarchy(self):
        
        children = self.children.all()
        hierarchy =list(children)

        #referencing the related name on the parent field
        for child in children: 
            hierarchy.extend(child.get_hierarchy())

        return hierarchy #returns a down-top (child to the highest parent) tree of account tree
    
    def calculate_total_balance(self):
        """
        calculates total balance for the account, including individual balance of its children
        """
        total_balance = self.current_balance
        # call hierarchy on obj to return its
        children = self.get_hierarchy()
        for child in children:
            total_balance += child.current_balance
        return total_balance


class AccountLedgerEntry(models.Model):
    """
    Represents an entry in the account ledger for a tenant, recording individual financial transactions.

    This model is used to track transactions associated with a tenant's account, including the transaction type,
    amount, description, and resulting balance. The model supports both debit and credit operations and keeps
    a record of the user who created each transaction. Transactions are automatically timestamped and can
    be filtered or ordered based on their date. This class is a core component of financial tracking within
    the application.

    Attributes:
        tenant (ForeignKey): A reference to the tenant associated with this transaction.
        account (ForeignKey): The account within the chart of accounts that this transaction relates to.
        date (DateTimeField): The date and time at which the transaction was created. Auto-set on creation.
        description (TextField): An optional textual description of the transaction.
        amount (DecimalField): The financial amount of the transaction.
        transaction_type (CharField): The type of the transaction, either 'DEBIT' or 'CREDIT'.
        balance (DecimalField): The balance of the account after the current transaction.
        created_by (ForeignKey): A reference to the user who created this transaction.

    Meta:
        verbose_name (str): Singular name for the model representation.
        verbose_name_plural (str): Plural name for the model representation.
        ordering (list): Default ordering for querysets, descending by date.
    """
    TRANSACTION_TYPES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='account_transactions'
    )
    account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    date = models.DateTimeField(
        auto_now_add=True
    )
    description = models.TextField(
        null=True, blank=True
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )
    transaction_type = models.CharField(
        max_length=6,
        choices=TRANSACTION_TYPES
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal(0.00)
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Account Transaction'
        verbose_name_plural = 'Account Transactions'
        ordering = ['-date']

    def __str__(self):
        return f'{self.account.name} - {self.transaction_type} - {self.amount}'



class AccountingService:
    """
    Handles accounting operations including account mapping, debit, and credit transactions.

    This class provides utility functions to manage and perform operations related to
    account mapping and ledger entries in an accounting system. It ensures atomic
    transactions during debit and credit operations and offers validation for inputs
    to ensure consistency and integrity of the accounts' system.

    Attributes:
        tenant ('Tenant'): The tenant associated with the accounting service.
        User ('settings.AUTH_USER_MODEL'): The user performing operations.

    Methods:
        get_account_mapping(action: str) -> AccountMapping:
            Retrieves the account mapping for a given action.

        Create_entry(action: str, amount: Decimal, description: str) -> None:
            Creates a ledger entry by performing debit and credit operations.

    Raises:
        ValidationError: Raised when invalid parameters or conditions are encountered.
    """
    def __init__(self,tenant: 'Tenant', user: 'settings.AUTH_USER_MODEL', scheme: InvestmentScheme = None):
        self.tenant = tenant
        self.user = user
        self.scheme = scheme

    def __get_account_mapping(self, action: str):
        """
        Retrieve account mapping information based on the specified action, tenant,
        and scheme properties. If the scheme is defined, it retrieves all matching
        account mappings. Otherwise, it returns the first matching account mapping.

        Parameters
        ----------
        action : str
            The name of the action used to filter account mappings.

        Returns
        -------
        QuerySet or AccountMapping or None
            If a scheme is provided, returns a QuerySet of all matching
            AccountMapping objects; otherwise, returns the first matching
            AccountMapping object or None if no matching objects are found.
        """
        if self.scheme:
            return AccountMapping.objects.filter(
                tenant=self.tenant,
                name=action,
                scheme=self.scheme
            )
        else:
            return AccountMapping.objects.filter(
                tenant=self.tenant,
                name=action
            ).first()

    def __perform_debit(self, account: ChartOfAccounts, amount: Decimal, description: str):
        """
        Performs a debit transaction for a specified account by adjusting its balance and
        creating a corresponding ledger entry.

        Args:
            account (ChartOfAccounts): The account being debited.
            amount (Decimal): The amount to debit from the account.
            description (str): A description of the transaction.

        Raises:
            ValidationError: If the account type is invalid.
        """
        with transaction.atomic():
            if account.account_type in ['ASSET','EXPENSE']:
                # For assets, debit increases the balance
                account.current_balance += amount
            elif account.account_type in ['REVENUE','CAPITAL','LIABILITY']:
                # For revenue, capital, and liability, debit decreases the balance
                account.current_balance -= amount
            else:
                raise ValidationError(f'Invalid account type: {account.account_type}')
            account.save()

            # Create a ledger entry for the debit transaction
            AccountLedgerEntry.objects.create(
                tenant=self.tenant,
                account=account,
                amount=amount,
                transaction_type='DEBIT',
                description=description,
                balance=account.current_balance,
                created_by=self.user,
            )

    def __perform_credit(self, account: ChartOfAccounts, amount: Decimal, description: str):
        """
        Executes a credit operation on a specific account. Updates the account balance
        based on an account type, records the transaction in the ledger, and ensures
        atomicity of the operation.

        Args:
            account (ChartOfAccounts): The account to be credited.
            amount (Decimal): The amount to credit.
            description (str): A brief description of the credit transaction.

        Raises:
            ValidationError: If the account type is invalid.
        """
        with transaction.atomic():
            if account.account_type in ['ASSET','EXPENSE']:
                # For assets, credit decreases the balance
                account.current_balance -= amount
            elif account.account_type in ['REVENUE','CAPITAL','LIABILITY']:
                # For revenue, capital, and liability, credit increases the balance
                account.current_balance += amount
            else:
                raise ValidationError(f'Invalid account type: {account.account_type}')
            account.save()

            # Create a ledger entry for the credit transaction
            AccountLedgerEntry.objects.create(
                tenant=self.tenant,
                account=account,
                amount=amount,
                transaction_type='CREDIT',
                description=description,
                balance=account.current_balance,
                created_by=self.user,
            )

    def create_entry(self, action: str, amount: Decimal, description: str):
        """
        Creates a financial entry for a given action.

        This method handles the creation of financial entries, ensuring data validity,
        and performs necessary debit and credit operations using account mappings.
        Each entry is associated with a specific financial action, amount, and a
        description. It verifies input integrity, validates the financial action,
        and then processes the corresponding debits and credits.

        Parameters:
            action (str): The financial action to associate with the entry.
            amount (Decimal): The monetary value for the entry. It must be greater
                than zero.
            description (str): A description or narrative for the financial entry.

        Raises:
            ValidationError: If the amount is less than or equal to zero.
            ValidationError: If the action parameter is empty or invalid.
            ValidationError: If no account mapping is found for the given action.
        """

        if amount <= 0:
            raise ValidationError('Amount must be greater than zero')

        if not action:
            raise ValidationError('Entry cannot be empty')

        # Check if the account exists
        if not AccountMapping.is_valid_action(action):
            raise ValidationError(f'Invalid entry: {action}')

        # Get the account mapping for the entry
        account_mapping = self.__get_account_mapping(action)

        if not account_mapping:
            raise ValidationError(f'No account mapping found for action: {action}')

        self.__perform_debit(account_mapping.debit_acc, amount, description)
        self.__perform_debit(account_mapping.credit_acc, amount, description)

    def create_manual_entry(self, debit_acc: ChartOfAccounts, credit_acc: ChartOfAccounts, amount: Decimal, description: str):
        """
        Creates a manual entry by performing debit and credit operations on the specified accounts.

        Parameters:
            debit_acc (ChartOfAccounts): The account to be debited.
            credit_acc (ChartOfAccounts): The account to be credited.
            amount (Decimal): The amount for the transaction.
            description (str): Description of the transaction.

        Raises:
            ValidationError: If the accounts are invalid, or if the amount is not greater than zero.
        """
        if amount <= 0:
            raise ValidationError('Amount must be greater than zero')

        if debit_acc == credit_acc:
            raise ValidationError('Debit and Credit accounts cannot be the same')

        self.__perform_debit(debit_acc, amount, description)
        self.__perform_credit(credit_acc, amount, description)



class AccountMapping(models.Model):
    """
    Represents the mapping between actions and corresponding debit and credit accounts
    in the system. It allows the definition of account relations based on specific
    financial events or transactions within the context of a tenant and potentially
    an investment scheme.

    The class ensures data integrity by enforcing constraints such as disallowing
    duplicate events for a tenant or invalid configurations like having the same
    account for both debit and credit purposes.

    Attributes:
        ACTIONS: A predefined list of actions representing financial events.
        name: The name of the action, selected from the predefined list of actions.
        debit_acc: The debit account mapped to the financial event.
        credit_acc: The credit account mapped to the financial event.
        tenant: The tenant to which the account mapping belongs.
        scheme: The investment scheme associated with the account mapping.
        created_on: The timestamp when the record was created.
        updated_on: The timestamp when the record was last updated.
        created_by: The user who created the record.
    """
    ACTIONS = [
        ('Contribution','Contribution'),
        ('Approved Contribution','Approved Contribution'),
        ('Investment','Investment'),
        ('Earned Revenue','Earned Revenue'),
        ('Approved Revenue','Approved Revenue'),
        ('Delayed Interest','Delayed Interest'),
        ('Approved Delayed Interest','Approved Delayed Interest'),
        ('Benefit Payout','Benefit Payout'),
        ('Benefit Accrued','Benefit Accrued'),
        ('Exit Payout','Exit Payout'),
        ('Redeem Investment','Redeem Investment'),
        ('Roll Over','Roll Over'),
        ('Supplier Invoice Creation','Supplier Invoice Creation'),
        ('Supplier Invoice Payment','Supplier Invoice Payment'),
        ('Member Withdrawal Invoice','Member Withdrawal Invoice'),
        ('Member Withdrawal Invoice Payment','Member Withdrawal Invoice Payment'),
    ]
    name = models.CharField(
        max_length=255,
        choices=ACTIONS,
        default=''
    )
    debit_acc = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='debit_mapping'
    )
    credit_acc = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='credit_mapping'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    scheme = models.ForeignKey(
        InvestmentScheme,
        on_delete=models.CASCADE,
        null=True,
        blank= True,
        related_name='account_mapping'
    )
    created_on = models.DateTimeField(auto_now_add=True,null=True)
    updated_on = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    @classmethod
    def is_valid_action(cls, action_name):
        """
        Determines if the provided action name is valid by checking it against
        the predefined list of valid actions in the ACTIONS class attribute.

        Parameters:
        action_name (str): The name of the action to validate.

        Returns:
        bool: True if the action name is valid, otherwise False.
        """
        return any(action_name == action[0] for action in cls.ACTIONS)

    # Prevent duplicate events for a single tenant
    class Meta:
        constraints = [
            UniqueConstraint(fields=['tenant','scheme','name'], name='unique_name_per_tenant')
        ]

    def __str__(self):
        return f'{self.tenant.name} - {self.scheme} - {self.name}'

    def clean(self):
        if self.debit_acc == self.credit_acc:
            raise ValidationError('Debits and Credits account cannot be the same')
        
    def check_for_existing(self):
        # Allow for only one instance of supplier invoice and payment for each tenant
        if AccountMapping.objects.filter(
            tenant=self.tenant,
            name__in = ['Supplier Invoice Creation','Supplier Invoice Payment']
        ).exists():
            raise ValidationError(f'The event "{self.name}" can only be mapped once.')
        
    def save(self,*args,**kwargs):
        self.clean()
        if not self.pk and self.name in ['Supplier Invoice Creation','Supplier Invoice Payment']:
            self.check_for_existing()
        super().save(*args,**kwargs)


class BankAccount(models.Model):
    CURRENCY = [
        ('GHS','GHS'),
        ('USD','USD'),
        ('EUR','EUR')
    ]
    ACCOUNT_TYPE = [
        ('current','Current'),
        ('checking','Checking'),
        ('savings','Savings'),
        ('fixed deposit','Fixed Deposit'),
        ('business','Business')
    ]
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='bank_accounts'
    )
    account_number = models.CharField(
        max_length=255
    )
    bank_name = models.CharField(
        max_length=255
    )
    account_holder_name = models.CharField(
        max_length=255
    )
    branch = models.CharField(
        max_length=255
    )
    account_type = models.CharField(
        max_length=255,
        choices=ACCOUNT_TYPE,
        default='business'
    )
    parent_Account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.SET_NULL,
        related_name='bank_accounts',
        null=True
    )
    bank_email = models.EmailField(
        null=True,
        blank=False
    )
    currency = models.CharField(
        max_length=255,
        choices=CURRENCY,
        default='GHS'
    )

    def __str__(self):
        return f'{self.bank_name} | {self.branch} | {self.account_number}'
