from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User # For user_triggered in OrderTimeline
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone # For setting shipped_at

from .models import (
    Category, Product, ProductImage, ProductAttribute,
    Address, Order, OrderItem, OrderTimeline, # Added Order related models
    Carrier, Shipment # Added Shipment related models
)
from .serializers import (
    CategorySerializer, ProductSerializer,
    ProductImageSerializer, ProductAttributeSerializer,
    ProductImageCreateSerializer, ProductAttributeCreateSerializer,
    AddressSerializer, OrderSerializer, OrderCreateUpdateSerializer,
    OrderItemCreateSerializer, OrderTimelineSerializer,
    CarrierSerializer, ShipmentSerializer, ShipmentUpdateSerializer # Added Carrier and Shipment serializers
)
from decimal import Decimal # Import Decimal for precision

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('children', 'products')
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Allow read for anyone, write for authenticated
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['name', 'slug', 'parent']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    @action(detail=False, methods=['get'], url_path='root-categories')
    def root_categories(self, request):
        root_cats = Category.objects.filter(parent__isnull=True)
        serializer = self.get_serializer(root_cats, many=True, context={'omit_parent_slug_if_null': True, 'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='products')
    def products_in_category(self, request, pk=None):
        category = self.get_object()
        products = Product.objects.filter(category=category)
        # TODO: Add pagination for products
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().prefetch_related('images', 'attributes')
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'category': ['exact'],
        'category__slug': ['exact'],
        'name': ['icontains'],
        'price': ['gte', 'lte', 'exact'],
        'available': ['exact'],
        'created_by__username': ['exact'], # Filter by creator's username
    }
    search_fields = ['name', 'description', 'category__name', 'attributes__name', 'attributes__value']
    ordering_fields = ['name', 'price', 'stock', 'created_at', 'updated_at']

    def perform_create(self, serializer):
        # Set created_by to the current user
        serializer.save(created_by=self.request.user)

    # Add/Delete Product Images
    @action(detail=True, methods=['post'], url_path='add-image', serializer_class=ProductImageCreateSerializer)
    def add_image(self, request, pk=None):
        product = self.get_object()
        serializer = ProductImageCreateSerializer(data=request.data)
        if serializer.is_valid():
            ProductImage.objects.create(product=product, image=serializer.validated_data['image'], caption=serializer.validated_data.get('caption', ''))
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-image/(?P<image_id>[^/.]+)')
    def delete_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        try:
            image = ProductImage.objects.get(id=image_id, product=product)
            image.delete()
            # Optionally, delete the actual image file from storage here if needed
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)
        except ProductImage.DoesNotExist:
            return Response({'detail': 'Image not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Add/Delete Product Attributes
    @action(detail=True, methods=['post'], url_path='add-attribute', serializer_class=ProductAttributeCreateSerializer)
    def add_attribute(self, request, pk=None):
        product = self.get_object()
        serializer = ProductAttributeCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Prevent duplicate attributes
            if ProductAttribute.objects.filter(product=product, name=serializer.validated_data['name'], value=serializer.validated_data['value']).exists():
                return Response({'detail': 'This attribute already exists for the product.'}, status=status.HTTP_400_BAD_REQUEST)
            ProductAttribute.objects.create(product=product, name=serializer.validated_data['name'], value=serializer.validated_data['value'])
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-attribute/(?P<attribute_id>[^/.]+)')
    def delete_attribute(self, request, pk=None, attribute_id=None):
        product = self.get_object()
        try:
            attribute = ProductAttribute.objects.get(id=attribute_id, product=product)
            attribute.delete()
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)
        except ProductAttribute.DoesNotExist:
            return Response({'detail': 'Attribute not found.'}, status=status.HTTP_404_NOT_FOUND)


# For more specific search/filter views if needed, e.g., a dedicated search endpoint
class ProductSearchView(generics.ListAPIView):
    queryset = Product.objects.all().prefetch_related('images', 'attributes')
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'category__slug': ['exact'],
        'price': ['gte', 'lte'],
        'available': ['exact'],
        'attributes__name': ['exact'],
        'attributes__value': ['exact'], # Filter by specific attribute value
    }
    search_fields = ['name', 'description', 'category__name'] # General search
    ordering_fields = ['name', 'price', 'created_at']
    permission_classes = [permissions.AllowAny] # Allow anyone to search products

    def get_queryset(self):
        queryset = super().get_queryset()
        # Example: further refine query based on multiple attribute filters
        # query_params = self.request.query_params
        # for key, value in query_params.items():
        #     if key.startswith('attr_'): # e.g. attr_color=Red&attr_size=XL
        #         attr_name = key.split('attr_')[1]
        #         queryset = queryset.filter(attributes__name__iexact=attr_name, attributes__value__iexact=value)
        return queryset


# Address Management
class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated] # Users can only manage their own addresses

    def get_queryset(self):
        # Users can only see/edit their own addresses. Admins can see all.
        if self.request.user.is_staff:
            return Address.objects.all()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Associate address with the current user if not an admin setting it for someone else
        if not serializer.validated_data.get('user_id') or not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()


# Order Management
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().select_related(
        'user', 'shipping_address', 'billing_address'
    ).prefetch_related(
        'items__product', 'timeline_events__user_triggered'
    )
    permission_classes = [permissions.IsAuthenticated] # Users manage their own orders, admin manage all
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'status': ['exact'],
        'user__username': ['exact'],
        'email': ['exact'],
        'created_at': ['gte', 'lte', 'exact'],
        'total_amount': ['gte', 'lte'],
    }
    search_fields = ['order_number', 'user__username', 'email', 'items__product__name']
    ordering_fields = ['created_at', 'total_amount', 'status']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return OrderCreateUpdateSerializer
        return OrderSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # User is set in the serializer's create method based on context
        order = serializer.save()
        # Initial timeline event is created in serializer

    # Custom actions for Order management
    @action(detail=True, methods=['post'], url_path='add-note')
    def add_note(self, request, pk=None):
        order = self.get_object()
        note_text = request.data.get('note')
        if not note_text:
            return Response({'detail': 'Note text is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        OrderTimeline.objects.create(order=order, note=note_text, user_triggered=request.user)
        return Response(OrderSerializer(order, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='cancel-order')
    def cancel_order(self, request, pk=None):
        order = self.get_object()
        if order.status in ['shipped', 'delivered', 'cancelled', 'refunded']:
            return Response({'detail': f'Order in status "{order.status}" cannot be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Revert inventory (basic example)
        for item in order.items.all():
            item.product.stock += item.quantity
            item.product.save(update_fields=['stock'])
            
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        OrderTimeline.objects.create(order=order, note="Order cancelled by user.", user_triggered=request.user, status_changed_to='cancelled')
        return Response(OrderSerializer(order, context={'request': request}).data)
    
    @action(detail=True, methods=['get'], url_path='timeline')
    def view_timeline(self, request, pk=None):
        order = self.get_object()
        timeline_events = order.timeline_events.all().order_by('timestamp')
        serializer = OrderTimelineSerializer(timeline_events, many=True)
        return Response(serializer.data)

    # Placeholder for adding/removing items - more complex than a simple update
    # For a real system, these would need careful implementation to handle stock, totals, etc.
    @action(detail=True, methods=['post'], url_path='add-item', serializer_class=OrderItemCreateSerializer)
    def add_order_item(self, request, pk=None):
        order = self.get_object()
        if order.status != 'pending': # Or other editable statuses
            return Response({'detail': 'Items can only be added to orders with appropriate status (e.g. pending).'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderItemCreateSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.validated_data['product']
            quantity = serializer.validated_data['quantity']

            # Check stock
            if product.stock < quantity:
                return Response({'detail': f'Not enough stock for {product.name}.'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if item already exists, if so, update quantity, else create
            order_item, created = OrderItem.objects.get_or_create(
                order=order, 
                product=product,
                defaults={'quantity': quantity, 'price_at_purchase': product.price}
            )
            if not created:
                order_item.quantity += quantity
                # Ensure stock check for additional quantity here as well
                if product.stock < order_item.quantity : # Checking total quantity against current stock
                     return Response({'detail': f'Not enough stock for additional quantity of {product.name}.'}, status=status.HTTP_400_BAD_REQUEST)
                order_item.save()
            
            # Decrease stock
            product.stock -= quantity 
            product.save(update_fields=['stock'])
            
            order.update_totals() # Recalculate order totals
            OrderTimeline.objects.create(order=order, note=f"Item {product.name} (Qty: {quantity}) added.", user_triggered=request.user)
            return Response(OrderSerializer(order, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove-item/(?P<item_id>[^/.]+)') # item_id is OrderItem id
    def remove_order_item(self, request, pk=None, item_id=None):
        order = self.get_object()
        if order.status != 'pending': # Or other editable statuses
             return Response({'detail': 'Items can only be removed from orders with appropriate status.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order_item = OrderItem.objects.get(id=item_id, order=order)
        except OrderItem.DoesNotExist:
            return Response({'detail': 'Order item not found.'}, status=status.HTTP_404_NOT_FOUND)

        product = order_item.product
        quantity_removed = order_item.quantity
        
        order_item.delete()
        
        # Increase stock
        product.stock += quantity_removed
        product.save(update_fields=['stock'])
        
        order.update_totals() # Recalculate order totals
        OrderTimeline.objects.create(order=order, note=f"Item {product.name} (Qty: {quantity_removed}) removed.", user_triggered=request.user)
        return Response(OrderSerializer(order, context={'request': request}).data)

    # Placeholder for coupon logic
    @action(detail=True, methods=['post'], url_path='apply-coupon')
    def apply_coupon(self, request, pk=None):
        order = self.get_object()
        coupon_code = request.data.get('coupon_code')
        if not coupon_code:
            return Response({'detail': 'Coupon code is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Dummy coupon logic
        # In a real app, you'd look up the Coupon model, validate it, and apply discount
        if coupon_code == "DISCOUNT10":
            discount = order.subtotal_amount * Decimal('0.10')
            if order.discount_amount > 0: # Prevent applying multiple discounts this way
                 return Response({'detail': 'A discount is already applied.'}, status=status.HTTP_400_BAD_REQUEST)
            order.discount_amount = discount.quantize(Decimal('0.01'))
            order.total_amount = order.subtotal_amount - order.discount_amount
            order.save(update_fields=['discount_amount', 'total_amount'])
            # order.coupon = found_coupon # Link the coupon if you have a Coupon model
            OrderTimeline.objects.create(order=order, note=f"Coupon {coupon_code} applied. Discount: {order.discount_amount}", user_triggered=request.user)
            return Response(OrderSerializer(order, context={'request': request}).data)
        else:
            return Response({'detail': 'Invalid coupon code.'}, status=status.HTTP_400_BAD_REQUEST)


# Carrier Management
class CarrierViewSet(viewsets.ModelViewSet):
    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer
    permission_classes = [permissions.IsAdminUser] # Typically only admins manage carriers
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['name', 'created_at']
    lookup_field = 'slug'

    @action(detail=False, methods=['get'], url_path='active', permission_classes=[permissions.IsAuthenticated]) # Allow any authenticated user to see active carriers
    def active_carriers(self, request):
        active_carriers = Carrier.objects.filter(is_active=True)
        serializer = self.get_serializer(active_carriers, many=True)
        return Response(serializer.data)

# Shipment Management
class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.all().select_related('order', 'carrier')
    permission_classes = [permissions.IsAdminUser] # Only admins/staff manage shipments directly
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'status': ['exact'],
        'carrier__slug': ['exact'],
        'order__order_number': ['exact'],
        'created_at': ['gte', 'lte'],
        'shipped_at': ['gte', 'lte'],
        'estimated_delivery_date': ['gte', 'lte'],
        'actual_delivery_date': ['gte', 'lte'],
    }
    search_fields = ['tracking_number', 'order__order_number', 'carrier__name']
    ordering_fields = ['created_at', 'shipped_at', 'status']

    def get_serializer_class(self):
        if self.action == 'create':
            # This assumes shipment creation is tied to an order processing flow,
            # potentially not directly via a generic 'create' endpoint without an order context.
            # A common pattern is to create a shipment when an order is being processed.
            # For direct creation via API (e.g. by admin):
            return ShipmentSerializer # Or a more specific create serializer if needed
        elif self.action in ['update', 'partial_update']:
            return ShipmentUpdateSerializer
        return ShipmentSerializer

    def perform_create(self, serializer):
        # Example: if creating a shipment directly and order_id is provided in request body
        # This is a simplified direct creation; usually, shipment creation is part of an order workflow.
        order_id = self.request.data.get('order_id')
        if not order_id:
            raise serializers.ValidationError({'order_id': 'Order ID is required to create a shipment.'})
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise serializers.ValidationError({'order_id': 'Order not found.'})

        if hasattr(order, 'shipment'):
             raise serializers.ValidationError({'order_id': 'Shipment already exists for this order.'})

        shipment = serializer.save(order=order)
        OrderTimeline.objects.create(order=order, note=f"Shipment created with ID {shipment.id}, Carrier: {shipment.carrier.name if shipment.carrier else 'N/A'}.", user_triggered=self.request.user)
        # Potentially update order status to 'processing' or similar
        if order.status == 'pending':
            order.status = 'processing' # Example status update
            order.save(update_fields=['status'])
            OrderTimeline.objects.create(order=order, note="Order status changed to processing due to shipment creation.", status_changed_to='processing', user_triggered=self.request.user)


    # Custom actions for Shipment status changes
    @action(detail=True, methods=['post'], url_path='update-status')
    def update_shipment_status(self, request, pk=None):
        shipment = self.get_object()
        new_status = request.data.get('status')
        if not new_status or new_status not in [choice[0] for choice in Shipment.SHIPMENT_STATUS_CHOICES]:
            return Response({'detail': 'Valid status is required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = shipment.status
        shipment.status = new_status
        
        # Specific logic for status changes
        if new_status == 'shipped' and not shipment.shipped_at:
            shipment.shipped_at = timezone.now()
        elif new_status == 'delivered' and not shipment.actual_delivery_date:
            shipment.actual_delivery_date = timezone.now().date()
            # Optionally update order status to 'delivered'
            if shipment.order.status != 'delivered':
                shipment.order.status = 'delivered'
                shipment.order.save(update_fields=['status'])
                OrderTimeline.objects.create(order=shipment.order, note="Order marked as delivered.", status_changed_to='delivered', user_triggered=request.user)

        shipment.save()
        OrderTimeline.objects.create(
            order=shipment.order, 
            note=f"Shipment status changed from {old_status} to {new_status}. Tracking: {shipment.tracking_number or 'N/A'}",
            user_triggered=request.user,
            status_changed_to=new_status # This could be a field on OrderTimeline if more granularity is needed for shipment status vs order status
        )
        return Response(ShipmentSerializer(shipment, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_shipment(self, request, pk=None):
        shipment = self.get_object()
        if shipment.status in ['shipped', 'delivered', 'cancelled']:
            return Response({'detail': f'Shipment in status "{shipment.status}" cannot be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        
        old_status = shipment.status
        shipment.status = 'cancelled'
        shipment.save(update_fields=['status'])
        
        OrderTimeline.objects.create(order=shipment.order, note=f"Shipment cancelled. Was in status: {old_status}.", user_triggered=request.user, status_changed_to='cancelled')
        # Note: Inventory reversion for cancelled shipments might be complex
        # if the order itself isn't cancelled. This assumes order cancellation handles inventory.
        return Response(ShipmentSerializer(shipment, context={'request': request}).data)

    # Action to "process" a shipment - could mean assigning carrier, getting tracking, etc.
    @action(detail=True, methods=['post'], url_path='process')
    def process_shipment(self, request, pk=None):
        shipment = self.get_object()
        if shipment.status != 'pending':
             return Response({'detail': 'Shipment must be in pending state to be processed.'}, status=status.HTTP_400_BAD_REQUEST)

        carrier_id = request.data.get('carrier_id')
        tracking_number = request.data.get('tracking_number')

        if not carrier_id:
            return Response({'detail': 'Carrier ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            carrier = Carrier.objects.get(id=carrier_id, is_active=True)
        except Carrier.DoesNotExist:
            return Response({'detail': 'Active carrier not found.'}, status=status.HTTP_404_NOT_FOUND)

        shipment.carrier = carrier
        shipment.tracking_number = tracking_number
        shipment.status = 'ready_to_ship' # Or 'shipped' if directly handed over
        shipment.save()
        
        OrderTimeline.objects.create(
            order=shipment.order, 
            note=f"Shipment processed. Carrier: {carrier.name}. Tracking: {tracking_number or 'N/A'}.",
            user_triggered=request.user,
            status_changed_to='ready_to_ship'
        )
        return Response(ShipmentSerializer(shipment, context={'request': request}).data)
