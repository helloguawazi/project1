from django.shortcuts import render, get_object_or_404, redirect # For template views
from django.contrib.auth.decorators import login_required # For template views
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction as django_db_transaction

from .forms import CategoryForm, ProductForm, ProductImageForm, ProductAttributeForm

# Existing DRF API View imports
from rest_framework import generics, permissions, status, viewsets # Ensure status is imported
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone 
from django.contrib.auth.models import User 
from decimal import Decimal

from .models import (
    Category, Product, ProductImage, ProductAttribute,
    Address, Order, OrderItem, OrderTimeline, 
    Carrier, Shipment 
)
from .serializers import (
    CategorySerializer, ProductSerializer, 
    ProductImageSerializer, ProductAttributeSerializer,
    ProductImageCreateSerializer, ProductAttributeCreateSerializer,
    AddressSerializer, OrderSerializer, OrderCreateUpdateSerializer,
    OrderItemCreateSerializer, OrderTimelineSerializer,
    CarrierSerializer, ShipmentSerializer, ShipmentUpdateSerializer 
)


# API ViewSets (Keep all existing API Viewsets as they are)
# CategoryViewSet, ProductViewSet, AddressViewSet, OrderViewSet, CarrierViewSet, ShipmentViewSet, ProductSearchView
# ... (all existing API view code remains here) ...
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('children', 'products')
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] 
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['name', 'slug', 'parent']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    lookup_field = 'slug' # Allow lookup by slug

    @action(detail=False, methods=['get'], url_path='root-categories')
    def root_categories(self, request):
        root_cats = Category.objects.filter(parent__isnull=True)
        serializer = self.get_serializer(root_cats, many=True, context={'omit_parent_slug_if_null': True, 'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='products')
    def products_in_category(self, request, slug=None): # Changed pk to slug
        category = self.get_object()
        products = Product.objects.filter(category=category)
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().prefetch_related('images', 'attributes')
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'category__slug': ['exact'], # Filter by category slug
        'name': ['icontains'],
        'price': ['gte', 'lte', 'exact'],
        'available': ['exact'],
        'created_by__username': ['exact'], 
    }
    search_fields = ['name', 'description', 'category__name', 'attributes__name', 'attributes__value']
    ordering_fields = ['name', 'price', 'stock', 'created_at', 'updated_at']
    lookup_field = 'slug' # Allow lookup by slug

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='add-image', serializer_class=ProductImageCreateSerializer)
    def add_image(self, request, slug=None): # Changed pk to slug
        product = self.get_object()
        serializer = ProductImageCreateSerializer(data=request.data)
        if serializer.is_valid():
            ProductImage.objects.create(product=product, image=serializer.validated_data['image'], caption=serializer.validated_data.get('caption', ''))
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-image/(?P<image_id>[^/.]+)')
    def delete_image(self, request, slug=None, image_id=None): # Changed pk to slug
        product = self.get_object()
        try:
            image = ProductImage.objects.get(id=image_id, product=product)
            image.delete()
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)
        except ProductImage.DoesNotExist:
            return Response({'detail': 'Image not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='add-attribute', serializer_class=ProductAttributeCreateSerializer)
    def add_attribute(self, request, slug=None): # Changed pk to slug
        product = self.get_object()
        serializer = ProductAttributeCreateSerializer(data=request.data)
        if serializer.is_valid():
            if ProductAttribute.objects.filter(product=product, name=serializer.validated_data['name'], value=serializer.validated_data['value']).exists():
                return Response({'detail': 'This attribute already exists for the product.'}, status=status.HTTP_400_BAD_REQUEST)
            ProductAttribute.objects.create(product=product, name=serializer.validated_data['name'], value=serializer.validated_data['value'])
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='delete-attribute/(?P<attribute_id>[^/.]+)')
    def delete_attribute(self, request, slug=None, attribute_id=None): # Changed pk to slug
        product = self.get_object()
        try:
            attribute = ProductAttribute.objects.get(id=attribute_id, product=product)
            attribute.delete()
            return Response(ProductSerializer(product, context={'request': request}).data, status=status.HTTP_200_OK)
        except ProductAttribute.DoesNotExist:
            return Response({'detail': 'Attribute not found.'}, status=status.HTTP_404_NOT_FOUND)

class ProductSearchView(generics.ListAPIView):
    queryset = Product.objects.all().prefetch_related('images', 'attributes')
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'category__slug': ['exact'],
        'price': ['gte', 'lte'],
        'available': ['exact'],
        'attributes__name': ['exact'],
        'attributes__value': ['exact'], 
    }
    search_fields = ['name', 'description', 'category__name'] 
    ordering_fields = ['name', 'price', 'created_at']
    permission_classes = [permissions.AllowAny]

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated] 

    def get_queryset(self):
        if self.request.user.is_staff:
            return Address.objects.all()
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if not serializer.validated_data.get('user_id') or not self.request.user.is_staff:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().select_related(
        'user', 'shipping_address', 'billing_address'
    ).prefetch_related(
        'items__product', 'timeline_events__user_triggered'
    )
    permission_classes = [permissions.IsAuthenticated] 
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
    lookup_field = 'order_number' # Use order_number for lookup

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return OrderCreateUpdateSerializer
        return OrderSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        # Allow users to see their own orders, identified by user or by email for guest orders.
        # This requires careful consideration if email is not unique across User accounts and guest orders.
        # For simplicity, if user is authenticated, show their orders.
        # If staff, show all. Access for guest orders via API would need a different mechanism (e.g. signed URL or specific token).
        return Order.objects.filter(user=self.request.user)


    def perform_create(self, serializer):
        order = serializer.save() # User is set in serializer context

    @action(detail=True, methods=['post'], url_path='add-note')
    def add_note(self, request, order_number=None): # Changed pk to order_number
        order = self.get_object()
        note_text = request.data.get('note')
        if not note_text:
            return Response({'detail': 'Note text is required.'}, status=status.HTTP_400_BAD_REQUEST)
        OrderTimeline.objects.create(order=order, note=note_text, user_triggered=request.user)
        return Response(OrderSerializer(order, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='cancel-order')
    def cancel_order(self, request, order_number=None): # Changed pk to order_number
        order = self.get_object()
        if order.status in ['shipped', 'delivered', 'cancelled', 'refunded']:
            return Response({'detail': f'Order in status "{order.status}" cannot be cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        for item in order.items.all():
            item.product.stock += item.quantity
            item.product.save(update_fields=['stock'])
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        OrderTimeline.objects.create(order=order, note="Order cancelled.", user_triggered=request.user, status_changed_to='cancelled')
        return Response(OrderSerializer(order, context={'request': request}).data)
    
    @action(detail=True, methods=['get'], url_path='timeline')
    def view_timeline(self, request, order_number=None): # Changed pk to order_number
        order = self.get_object()
        timeline_events = order.timeline_events.all().order_by('timestamp')
        serializer = OrderTimelineSerializer(timeline_events, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add-item', serializer_class=OrderItemCreateSerializer)
    def add_order_item(self, request, order_number=None): # Changed pk to order_number
        order = self.get_object()
        if order.status != 'pending':
            return Response({'detail': 'Items can only be added to orders with appropriate status (e.g. pending).'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = OrderItemCreateSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.validated_data['product']
            quantity = serializer.validated_data['quantity']
            if product.stock < quantity:
                return Response({'detail': f'Not enough stock for {product.name}.'}, status=status.HTTP_400_BAD_REQUEST)
            order_item, created = OrderItem.objects.get_or_create(
                order=order, product=product,
                defaults={'quantity': quantity, 'price_at_purchase': product.price}
            )
            if not created:
                if product.stock < (order_item.quantity + quantity) : 
                     return Response({'detail': f'Not enough stock for additional quantity of {product.name}.'}, status=status.HTTP_400_BAD_REQUEST)
                order_item.quantity += quantity
                order_item.save()
            product.stock -= quantity 
            product.save(update_fields=['stock'])
            order.update_totals()
            OrderTimeline.objects.create(order=order, note=f"Item {product.name} (Qty: {quantity}) added.", user_triggered=request.user)
            return Response(OrderSerializer(order, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='remove-item/(?P<item_id>[^/.]+)')
    def remove_order_item(self, request, order_number=None, item_id=None): # Changed pk to order_number
        order = self.get_object()
        if order.status != 'pending':
             return Response({'detail': 'Items can only be removed from orders with appropriate status.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order_item = OrderItem.objects.get(id=item_id, order=order)
        except OrderItem.DoesNotExist:
            return Response({'detail': 'Order item not found.'}, status=status.HTTP_404_NOT_FOUND)
        product = order_item.product
        quantity_removed = order_item.quantity
        order_item.delete()
        product.stock += quantity_removed
        product.save(update_fields=['stock'])
        order.update_totals()
        OrderTimeline.objects.create(order=order, note=f"Item {product.name} (Qty: {quantity_removed}) removed.", user_triggered=request.user)
        return Response(OrderSerializer(order, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='apply-coupon')
    def apply_coupon(self, request, order_number=None): # Changed pk to order_number
        order = self.get_object()
        coupon_code = request.data.get('coupon_code')
        if not coupon_code:
            return Response({'detail': 'Coupon code is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if coupon_code == "DISCOUNT10":
            discount = order.subtotal_amount * Decimal('0.10')
            if order.discount_amount > 0:
                 return Response({'detail': 'A discount is already applied.'}, status=status.HTTP_400_BAD_REQUEST)
            order.discount_amount = discount.quantize(Decimal('0.01'))
            order.total_amount = order.subtotal_amount - order.discount_amount
            order.save(update_fields=['discount_amount', 'total_amount'])
            OrderTimeline.objects.create(order=order, note=f"Coupon {coupon_code} applied. Discount: {order.discount_amount}", user_triggered=request.user)
            return Response(OrderSerializer(order, context={'request': request}).data)
        else:
            return Response({'detail': 'Invalid coupon code.'}, status=status.HTTP_400_BAD_REQUEST)

class CarrierViewSet(viewsets.ModelViewSet):
    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer
    permission_classes = [permissions.IsAdminUser] 
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['name', 'created_at']
    lookup_field = 'slug'

    @action(detail=False, methods=['get'], url_path='active', permission_classes=[permissions.IsAuthenticated])
    def active_carriers(self, request):
        active_carriers = Carrier.objects.filter(is_active=True)
        serializer = self.get_serializer(active_carriers, many=True)
        return Response(serializer.data)

class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.all().select_related('order', 'carrier')
    permission_classes = [permissions.IsAdminUser] 
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
    lookup_field = 'pk' # Default, or order.shipment.id if using order as base

    def get_serializer_class(self):
        if self.action == 'create': # Direct creation by admin
            return ShipmentSerializer 
        elif self.action in ['update', 'partial_update', 'update_shipment_status', 'process_shipment']: # Added process_shipment here
            return ShipmentUpdateSerializer
        return ShipmentSerializer

    def perform_create(self, serializer): # For admin direct creation
        order_id = self.request.data.get('order_id')
        if not order_id:
            raise serializers.ValidationError({'order_id': 'Order ID is required to create a shipment.'})
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise serializers.ValidationError({'order_id': 'Order not found.'})
        if hasattr(order, 'shipment'):
             raise serializers.ValidationError({'order_id': 'Shipment already exists for this order.'})
        shipment = serializer.save(order=order) # Assign order to the shipment
        OrderTimeline.objects.create(order=order, note=f"Shipment created with ID {shipment.id}, Carrier: {shipment.carrier.name if shipment.carrier else 'N/A'}.", user_triggered=self.request.user)
        if order.status == 'pending':
            order.status = 'processing' 
            order.save(update_fields=['status'])
            OrderTimeline.objects.create(order=order, note="Order status changed to processing due to shipment creation.", status_changed_to='processing', user_triggered=self.request.user)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_shipment_status(self, request, pk=None):
        shipment = self.get_object()
        new_status = request.data.get('status')
        if not new_status or new_status not in [choice[0] for choice in Shipment.SHIPMENT_STATUS_CHOICES]:
            return Response({'detail': 'Valid status is required.'}, status=status.HTTP_400_BAD_REQUEST)
        old_status = shipment.status
        shipment.status = new_status
        if new_status == 'shipped' and not shipment.shipped_at:
            shipment.shipped_at = timezone.now()
        elif new_status == 'delivered' and not shipment.actual_delivery_date:
            shipment.actual_delivery_date = timezone.now().date()
            if shipment.order.status != 'delivered':
                shipment.order.status = 'delivered'
                shipment.order.save(update_fields=['status'])
                OrderTimeline.objects.create(order=shipment.order, note="Order marked as delivered.", status_changed_to='delivered', user_triggered=request.user)
        shipment.save()
        OrderTimeline.objects.create(
            order=shipment.order, 
            note=f"Shipment status changed from {old_status} to {new_status}. Tracking: {shipment.tracking_number or 'N/A'}",
            user_triggered=request.user,
            status_changed_to=new_status 
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
        return Response(ShipmentSerializer(shipment, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='process', serializer_class=ShipmentUpdateSerializer) # Use update serializer for processing
    def process_shipment(self, request, pk=None):
        shipment = self.get_object()
        if shipment.status != 'pending':
             return Response({'detail': 'Shipment must be in pending state to be processed.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use the serializer for validation and partial update
        serializer = ShipmentUpdateSerializer(shipment, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            # Carrier must be assigned either now or previously
            carrier = serializer.validated_data.get('carrier', shipment.carrier)
            if not carrier:
                 return Response({'detail': 'Carrier must be assigned to process shipment.'}, status=status.HTTP_400_BAD_REQUEST)

            new_status = serializer.validated_data.get('status', 'ready_to_ship') # Default to ready_to_ship if not specified
            serializer.save(status=new_status) # status is part of ShipmentUpdateSerializer

            OrderTimeline.objects.create(
                order=shipment.order, 
                note=f"Shipment processed. Carrier: {shipment.carrier.name}. Tracking: {shipment.tracking_number or 'N/A'}. Status: {new_status}",
                user_triggered=request.user,
                status_changed_to=new_status
            )
            return Response(ShipmentSerializer(shipment, context={'request': request}).data) # Return full serializer
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Django Template Views for Shop Management (AdminLTE)
@staff_member_required
def category_list_view(request):
    # Fetch all categories to correctly build the parent dropdown in forms later if needed,
    # but the template will display them hierarchically starting from roots.
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('children__children') # Deeper prefetch for multi-level
    all_categories_for_select = Category.objects.all().order_by('name') # For dropdowns
    context = {
        'categories': categories, # Root categories for display
        'all_categories_for_select': all_categories_for_select, # For forms
        'page_title': 'Shop Categories',
        'breadcrumb_active': 'Categories'
    }
    return render(request, 'shop/category_list.html', context)

@staff_member_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{form.cleaned_data['name']}' created successfully.")
            return redirect('shop_ui:category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm()
    
    context = {
        'form': form,
        'form_type': 'create',
        'page_title': 'Create Category',
        'breadcrumb_active': 'Create Category'
    }
    return render(request, 'shop/category_form.html', context)

@staff_member_required
def category_edit_view(request, category_slug):
    category = get_object_or_404(Category, slug=category_slug)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated successfully.")
            return redirect('shop_ui:category_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CategoryForm(instance=category)
        
    context = {
        'form': form,
        'category_instance': category,
        'form_type': 'edit',
        'page_title': f'Edit Category: {category.name}',
        'breadcrumb_active': 'Edit Category'
    }
    return render(request, 'shop/category_form.html', context)


@staff_member_required
def product_list_view(request):
    products = Product.objects.all().select_related('category', 'created_by').prefetch_related('images').order_by('-created_at')
    context = {
        'products': products,
        'page_title': 'Product List',
        'breadcrumb_active': 'Products'
    }
    return render(request, 'shop/product_list.html', context)

@staff_member_required
def product_create_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES or None)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            # form.save_m2m() # If ProductForm had direct M2M fields like tags
            messages.success(request, f"Product '{product.name}' created successfully.")
            return redirect('shop_ui:product_edit', product_slug=product.slug) # Redirect to edit page to add images/attributes
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProductForm()
        
    all_shop_categories = Category.objects.all().order_by('name')
    context = {
        'form': form,
        'all_shop_categories': all_shop_categories,
        'form_type': 'create',
        'page_title': 'Create Product',
        'breadcrumb_active': 'Create Product'
    }
    return render(request, 'shop/product_form.html', context)

@staff_member_required
def product_edit_view(request, product_slug):
    product = get_object_or_404(Product.objects.prefetch_related('images', 'attributes'), slug=product_slug)
    
    if request.method == 'POST':
        form_action = request.POST.get('form_action') # To distinguish between different form submissions on this page
        
        if form_action == 'save_main_details':
            product_form = ProductForm(request.POST, request.FILES or None, instance=product)
            if product_form.is_valid():
                product_form.save()
                messages.success(request, f"Product '{product.name}' details updated successfully.")
                return redirect('shop_ui:product_edit', product_slug=product.slug) # Stay on page
            else:
                messages.error(request, "Error updating product details. Please correct errors below.")
                # Need to re-pass other forms if they were also submitted or had errors
                image_form = ProductImageForm()
                attribute_form = ProductAttributeForm()

        elif form_action == 'upload_image':
            product_form = ProductForm(instance=product) # Keep main form populated
            image_form = ProductImageForm(request.POST, request.FILES)
            attribute_form = ProductAttributeForm()
            if image_form.is_valid():
                image_instance = image_form.save(commit=False)
                image_instance.product = product
                image_instance.save()
                messages.success(request, "Image uploaded successfully.")
                return redirect('shop_ui:product_edit', product_slug=product.slug)
            else:
                messages.error(request, "Error uploading image.")
        
        elif form_action == 'add_attribute':
            product_form = ProductForm(instance=product)
            image_form = ProductImageForm()
            attribute_form = ProductAttributeForm(request.POST)
            if attribute_form.is_valid():
                # Check for duplicates explicitly if needed, though model unique_together handles DB level
                name = attribute_form.cleaned_data['name']
                value = attribute_form.cleaned_data['value']
                if ProductAttribute.objects.filter(product=product, name=name, value=value).exists():
                    messages.warning(request, f"Attribute '{name}: {value}' already exists for this product.")
                else:
                    attr_instance = attribute_form.save(commit=False)
                    attr_instance.product = product
                    attr_instance.save()
                    messages.success(request, "Attribute added successfully.")
                return redirect('shop_ui:product_edit', product_slug=product.slug)
            else:
                messages.error(request, "Error adding attribute.")

        elif form_action and form_action.startswith('delete_image_'):
            image_id_to_delete = form_action.split('delete_image_')[1]
            try:
                image_to_delete = ProductImage.objects.get(id=image_id_to_delete, product=product)
                image_to_delete.delete() # Consider deleting file from storage too
                messages.success(request, "Image deleted successfully.")
            except ProductImage.DoesNotExist:
                messages.error(request, "Image not found or does not belong to this product.")
            return redirect('shop_ui:product_edit', product_slug=product.slug)

        elif form_action and form_action.startswith('delete_attribute_'):
            attr_id_to_delete = form_action.split('delete_attribute_')[1]
            try:
                attr_to_delete = ProductAttribute.objects.get(id=attr_id_to_delete, product=product)
                attr_to_delete.delete()
                messages.success(request, "Attribute deleted successfully.")
            except ProductAttribute.DoesNotExist:
                messages.error(request, "Attribute not found or does not belong to this product.")
            return redirect('shop_ui:product_edit', product_slug=product.slug)
        
        else: # Default to re-rendering forms if action not recognized or main form had errors
            # This path is taken if product_form had errors initially
            if 'product_form' not in locals(): # If not set by 'save_main_details' error path
                 product_form = ProductForm(request.POST, request.FILES or None, instance=product)
                 if not product_form.is_valid(): # Ensure we show errors if main form was intended
                     messages.error(request, "Please correct errors in the product details.")

            if 'image_form' not in locals(): image_form = ProductImageForm()
            if 'attribute_form' not in locals(): attribute_form = ProductAttributeForm()


    else: # GET request
        product_form = ProductForm(instance=product)
        image_form = ProductImageForm() # For adding new images
        attribute_form = ProductAttributeForm() # For adding new attributes
    
    all_shop_categories = Category.objects.all().order_by('name')
    context = {
        'form': product_form, # Main product form
        'image_form': image_form,
        'attribute_form': attribute_form,
        'product_instance': product,
        'all_shop_categories': all_shop_categories,
        'form_type': 'edit',
        'page_title': f'Edit Product: {product.name}',
        'breadcrumb_active': 'Edit Product'
    }
    return render(request, 'shop/product_form.html', context)
