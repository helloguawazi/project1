from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    available = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, related_name='products_created', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at'] # Default ordering for products

    def save(self, *args, **kwargs):
        if not self.slug:
            # Create a unique slug if multiple products have the same name
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='product_images/')
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name} - {self.caption if self.caption else self.id}"

class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, related_name='attributes', on_delete=models.CASCADE)
    name = models.CharField(max_length=100) # e.g., Color, Size, Material
    value = models.CharField(max_length=255) # e.g., Red, XL, Cotton

    class Meta:
        unique_together = ('product', 'name', 'value') # Ensures no duplicate attributes for the same product
        ordering = ['name', 'value']


    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"


# Order related models
class Address(models.Model):
    user = models.ForeignKey(User, related_name='addresses', on_delete=models.CASCADE, null=True, blank=True) # Null if guest checkout with address
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state_province_region = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address_type = models.CharField(max_length=10, choices=[('billing', 'Billing'), ('shipping', 'Shipping')], default='shipping')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Guest'} - {self.address_line_1}, {self.city} ({self.address_type})"

class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    user = models.ForeignKey(User, related_name='orders', on_delete=models.SET_NULL, null=True, blank=True) # Allow guest orders
    email = models.EmailField(max_length=255, blank=True, null=True) # For guest orders or if user email is different
    shipping_address = models.ForeignKey(Address, related_name='shipping_orders', on_delete=models.SET_NULL, null=True, blank=True)
    billing_address = models.ForeignKey(Address, related_name='billing_orders', on_delete=models.SET_NULL, null=True, blank=True)
    
    order_number = models.CharField(max_length=100, unique=True, blank=True) # Can be generated
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # coupon = models.ForeignKey('Coupon', null=True, blank=True, on_delete=models.SET_NULL) # Assuming Coupon model exists or will be created
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    
    notes = models.TextField(blank=True, null=True) # Customer notes or admin notes
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate a unique order number (e.g., based on timestamp and ID)
            # This is a simplified version. A more robust solution might be needed.
            import uuid
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}" 
        super().save(*args, **kwargs)
        # Recalculate totals if OrderItems change (handled by signals or methods)

    def __str__(self):
        return f"Order {self.order_number} by {self.user.username if self.user else self.email if self.email else 'Guest'}"

    def update_totals(self):
        """Recalculates subtotal and total amount based on order items."""
        subtotal = sum(item.get_total_price() for item in self.items.all())
        self.subtotal_amount = subtotal
        # Assuming discount_amount is set elsewhere (e.g., when applying a coupon)
        self.total_amount = self.subtotal_amount - self.discount_amount
        self.save(update_fields=['subtotal_amount', 'total_amount'])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.PROTECT) # Protect product from deletion if in an order
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2) # Store price at time of purchase

    class Meta:
        unique_together = ('order', 'product') # Prevent duplicate product entries in the same order

    def save(self, *args, **kwargs):
        if not self.pk: # If new item, set price_at_purchase
            self.price_at_purchase = self.product.price
        super().save(*args, **kwargs)
        # After saving an item, update order totals and potentially inventory
        # self.order.update_totals() # This can cause recursion if not handled carefully with signals

    def get_total_price(self):
        return self.price_at_purchase * self.quantity

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in Order {self.order.order_number}"


# Order Timeline/History (Optional, for tracking status changes and notes)
class OrderTimeline(models.Model):
    order = models.ForeignKey(Order, related_name='timeline_events', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    status_changed_to = models.CharField(max_length=50, blank=True, null=True) # e.g., 'shipped'
    note = models.TextField(blank=True, null=True) # e.g., "Payment received", "Coupon XYZ applied"
    user_triggered = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Who made the change

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Event for Order {self.order.order_number} at {self.timestamp}"


# Shipping and Carrier Models
class Carrier(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    website_url = models.URLField(blank=True, null=True)
    tracking_url_template = models.CharField(
        max_length=255, blank=True, null=True, 
        help_text="Template for tracking URL, e.g., 'https://example.com/track?id={tracking_number}'"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Shipment(models.Model):
    SHIPMENT_STATUS_CHOICES = [
        ('pending', 'Pending'), # Shipment created, not yet processed
        ('ready_to_ship', 'Ready to Ship'), # Items packed, label generated
        ('shipped', 'Shipped'), # Handed over to carrier
        ('in_transit', 'In Transit'), # Carrier has picked up
        ('delivered', 'Delivered'), # Confirmed delivery
        ('failed_delivery', 'Failed Delivery'),
        ('cancelled', 'Cancelled'),
    ]
    order = models.OneToOneField(Order, related_name='shipment', on_delete=models.CASCADE) # Each order has one shipment
    carrier = models.ForeignKey(Carrier, related_name='shipments', on_delete=models.SET_NULL, null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=SHIPMENT_STATUS_CHOICES, default='pending')
    estimated_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # Shipping cost can be stored here if it's separate from order total or varies by shipment
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True) # Internal notes about the shipment

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) # When the shipment record itself was last updated
    shipped_at = models.DateTimeField(null=True, blank=True) # When status changes to 'shipped'

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Shipment for Order {self.order.order_number} via {self.carrier.name if self.carrier else 'N/A'}"

    def save(self, *args, **kwargs):
        # If status is 'shipped' and shipped_at is not set, set it.
        if self.status == 'shipped' and not self.shipped_at:
            from django.utils import timezone
            self.shipped_at = timezone.now()
        super().save(*args, **kwargs)
