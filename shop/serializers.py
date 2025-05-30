from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Category, Product, ProductImage, ProductAttribute, 
    Address, Order, OrderItem, OrderTimeline,
    Carrier, Shipment # Added Carrier and Shipment
)

class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ['id', 'name', 'value']

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'caption', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    # Allow associating by category ID during product creation/update
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), write_only=True)


    class Meta:
        model = Product
        fields = [
            'id', 'category', 'category_name', 'name', 'slug', 'description', 'price', 
            'stock', 'available', 'images', 'attributes', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ('slug', 'created_at', 'updated_at', 'category_name')

    def create(self, validated_data):
        # created_by is not part of the serializer fields for direct input,
        # it will be set in the view based on the request user.
        # Category is handled by PrimaryKeyRelatedField
        product = Product.objects.create(**validated_data)
        return product

class CategorySerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True) # Read-only, products are managed via Product endpoints
    parent_slug = serializers.SlugRelatedField(slug_field='slug', queryset=Category.objects.all(), source='parent', required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'parent_slug', 'products', 'created_at', 'updated_at']
        read_only_fields = ('slug', 'created_at', 'updated_at')
        # Ensure parent is writeable for associating parent category by ID
        extra_kwargs = {
            'parent': {'write_only': True, 'required': False, 'allow_null': True}
        }
    
    def validate_name(self, value):
        # Ensure category name is unique (case-insensitive check can be added if needed)
        if Category.objects.filter(name=value).exists() and (self.instance is None or self.instance.name != value) :
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        # To avoid recursion issues when listing categories with children that also list parents
        request = self.context.get('request', None)
        if request and request.method == 'GET': # Only modify for GET requests if needed for specific views
             # If 'omit_parent_slug' is passed in context by the view, we can use it here
            if self.context.get('omit_parent_slug_if_null', False) and not self.instance.parent:
                 # This logic might be better handled in the view or by using different serializers for different actions
                 pass # Example of how context could be used
        return fields


# Serializers for adding images and attributes to products
class ProductImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['image', 'caption']

class ProductAttributeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ['name', 'value']

# Address Serializer
class AddressSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True, required=False, allow_null=True)

    class Meta:
        model = Address
        fields = [
            'id', 'user', 'user_id', 'address_line_1', 'address_line_2', 'city', 
            'state_province_region', 'postal_code', 'country', 'phone_number', 'address_type'
        ]
        # User can be set based on authenticated user in the view, or explicitly for admin roles
        # For guest checkouts, user_id will be null.

# OrderItem Serializers
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    total_price = serializers.DecimalField(source='get_total_price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_slug', 'quantity', 'price_at_purchase', 'total_price']
        read_only_fields = ['price_at_purchase', 'total_price'] # price_at_purchase is set on creation

class OrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity'] # price_at_purchase will be set automatically


# OrderTimeline Serializer
class OrderTimelineSerializer(serializers.ModelSerializer):
    user_triggered = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OrderTimeline
        fields = ['id', 'timestamp', 'status_changed_to', 'note', 'user_triggered']
        read_only_fields = ['timestamp', 'user_triggered']


# Order Serializers
class OrderSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    billing_address = AddressSerializer(read_only=True)
    timeline_events = OrderTimelineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'email', 'shipping_address', 'billing_address', 
            'total_amount', 'subtotal_amount', 'discount_amount', 'status', 'notes', 
            'items', 'timeline_events', 'created_at', 'updated_at'
        ]
        read_only_fields = ('order_number', 'total_amount', 'subtotal_amount', 'created_at', 'updated_at', 'timeline_events')


class OrderCreateUpdateSerializer(serializers.ModelSerializer):
    items = OrderItemCreateSerializer(many=True, required=True)
    # Address details can be provided as IDs of existing addresses or new address data
    shipping_address_id = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), source='shipping_address', required=False, allow_null=True)
    billing_address_id = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), source='billing_address', required=False, allow_null=True)
    
    # Allow creating new addresses during order creation
    # shipping_address_data = AddressSerializer(required=False, write_only=True, allow_null=True) 
    # billing_address_data = AddressSerializer(required=False, write_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = [
            'email', # For guest or if different from user's default
            'shipping_address_id', 'billing_address_id', 
            # 'shipping_address_data', 'billing_address_data', 
            'notes', 'items' 
            # status, total_amount, discount_amount are handled by the backend
        ]

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one order item is required.")
        # Further validation: check product availability and stock (can be done in create/update)
        for item_data in value:
            product = item_data['product']
            if not product.available:
                raise serializers.ValidationError(f"Product '{product.name}' is not available.")
            if product.stock < item_data['quantity']:
                raise serializers.ValidationError(f"Not enough stock for product '{product.name}'. Available: {product.stock}, Requested: {item_data['quantity']}.")
        return value
        
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user if self.context['request'].user.is_authenticated else None
        
        # Handle addresses (simplified: assumes IDs are provided for existing addresses)
        # More complex logic would be needed for creating new addresses from shipping_address_data/billing_address_data

        order = Order.objects.create(user=user, **validated_data)

        total_order_subtotal = 0
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            order_item = OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price_at_purchase=product.price # Set price at time of purchase
            )
            total_order_subtotal += order_item.get_total_price()
            
            # Inventory Management: Decrease stock
            product.stock -= quantity
            product.save(update_fields=['stock'])

        order.subtotal_amount = total_order_subtotal
        order.total_amount = total_order_subtotal # Assuming no discount initially
        order.save()
        
        OrderTimeline.objects.create(order=order, note="Order created.", user_triggered=user, status_changed_to=order.status)
        return order

    def update(self, instance, validated_data):
        # Updating order items is complex: handle additions, removals, quantity changes.
        # For simplicity, this example won't fully implement item updates within the order update.
        # Usually, item modifications would be separate endpoints or handled with careful logic here.
        # This example focuses on updating order-level fields like addresses or notes.

        items_data = validated_data.pop('items', None) # Items are not typically updated this way in a single step.

        # Update order fields
        instance.email = validated_data.get('email', instance.email)
        instance.shipping_address = validated_data.get('shipping_address', instance.shipping_address)
        instance.billing_address = validated_data.get('billing_address', instance.billing_address)
        instance.notes = validated_data.get('notes', instance.notes)
        # Status changes should have dedicated methods/actions
        
        instance.save()

        # If items_data is provided, one might implement logic to sync items,
        # but this is non-trivial (e.g., what if an item is removed, quantity changes, new item added?).
        # A common pattern is to have separate endpoints for managing items in an existing order.
        # For now, we'll assume items are set at creation and managed via other means if needed.

        OrderTimeline.objects.create(order=instance, note="Order details updated.", user_triggered=self.context['request'].user)
        return instance


# Carrier Serializer
class CarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrier
        fields = ['id', 'name', 'slug', 'website_url', 'tracking_url_template', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ('slug', 'created_at', 'updated_at')

# Shipment Serializers
class ShipmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    carrier_name = serializers.CharField(source='carrier.name', read_only=True, allow_null=True)
    # Provide a way to set carrier by ID
    carrier_id = serializers.PrimaryKeyRelatedField(queryset=Carrier.objects.filter(is_active=True), source='carrier', write_only=True, required=False, allow_null=True)


    class Meta:
        model = Shipment
        fields = [
            'id', 'order', 'order_number', 'carrier', 'carrier_id', 'carrier_name', 'tracking_number', 
            'status', 'estimated_delivery_date', 'actual_delivery_date', 
            'shipping_cost', 'notes', 'created_at', 'updated_at', 'shipped_at'
        ]
        read_only_fields = ('order_number', 'carrier_name', 'created_at', 'updated_at', 'shipped_at')
        # Order is typically set internally when a shipment is created for an order, not via direct API input usually.
        extra_kwargs = {
            'order': {'read_only': True} 
        }


class ShipmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a shipment, typically linked to an order."""
    carrier_id = serializers.PrimaryKeyRelatedField(
        queryset=Carrier.objects.filter(is_active=True), 
        source='carrier', 
        required=True # A carrier must be assigned to create a shipment
    )
    # Order ID will be passed in the URL or context, not in the request body for this specific serializer
    
    class Meta:
        model = Shipment
        fields = [
            'carrier_id', 'tracking_number', 'estimated_delivery_date', 
            'shipping_cost', 'notes'
            # Status defaults to 'pending'
            # Order is set in the view
        ]

class ShipmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating shipment, e.g., status, tracking, delivery dates."""
    carrier_id = serializers.PrimaryKeyRelatedField(
        queryset=Carrier.objects.filter(is_active=True), 
        source='carrier', 
        required=False, # Allow updating without changing carrier
        allow_null=True
    )

    class Meta:
        model = Shipment
        fields = [
            'carrier_id', 'tracking_number', 'status', 
            'estimated_delivery_date', 'actual_delivery_date',
            'shipping_cost', 'notes'
        ]
        # Some fields like 'shipped_at' are updated automatically based on status change (in model's save method)
