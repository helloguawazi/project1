from django.db import models
from django.contrib.auth.models import User
# To link Transactions to Orders in the 'shop' app
# from shop.models import Order 
# Using a string 'shop.Order' to avoid circular imports at model definition time. Django will resolve it.

class Currency(models.Model):
    name = models.CharField(max_length=50, unique=True) # e.g., US Dollar, Euro
    code = models.CharField(max_length=3, unique=True) # e.g., USD, EUR
    symbol = models.CharField(max_length=5) # e.g., $, €
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000, help_text="Exchange rate relative to a base currency (e.g., USD).")
    is_default = models.BooleanField(default=False, help_text="Is this the default currency for the system?")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Currencies"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if self.is_default:
            # Ensure only one currency is default
            Currency.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('authorization', 'Authorization'), # e.g. card pre-auth
        ('capture', 'Capture'), # Capture a pre-authorized amount
        ('void', 'Void'), # Void an authorization or unsettled transaction
    ]
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Pending'), # Transaction initiated
        ('successful', 'Successful'), # Payment completed
        ('failed', 'Failed'), # Payment failed
        ('cancelled', 'Cancelled'), # Transaction cancelled by user/system
        ('requires_action', 'Requires Action'), # e.g. 3D Secure
    ]
    
    order = models.ForeignKey('shop.Order', related_name='transactions', on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, related_name='transactions', on_delete=models.SET_NULL, null=True, blank=True) # User who initiated or is associated with transaction
    
    transaction_id_external = models.CharField(max_length=100, unique=True, help_text="ID from the payment gateway, e.g., Stripe charge ID.")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.ForeignKey(Currency, related_name='transactions', on_delete=models.PROTECT) # Protect currency from deletion if used in transactions
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='pending')
    
    payment_method_details = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., 'Visa ending in 1234'")
    gateway_response_raw = models.TextField(blank=True, null=True, help_text="Raw response from the payment gateway for debugging.")
    notes = models.TextField(blank=True, null=True, help_text="Internal notes about the transaction.")

    created_at = models.DateTimeField(auto_now_add=True) # When the transaction record was created in our system
    processed_at = models.DateTimeField(null=True, blank=True) # When the transaction was processed by the gateway

    parent_transaction = models.ForeignKey('self', null=True, blank=True, related_name='child_transactions', on_delete=models.SET_NULL, help_text="For linking refunds/captures to original payments/authorizations.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.transaction_id_external} for Order {self.order.order_number if self.order else 'N/A'} - {self.amount} {self.currency.code} ({self.status})"

    def save(self, *args, **kwargs):
        if self.status in ['successful', 'failed', 'cancelled'] and not self.processed_at:
            from django.utils import timezone
            self.processed_at = timezone.now()
        super().save(*args, **kwargs)
