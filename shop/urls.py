from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, ProductViewSet, ProductSearchView,
    AddressViewSet, OrderViewSet, CarrierViewSet, ShipmentViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'carriers', CarrierViewSet, basename='carrier')
router.register(r'shipments', ShipmentViewSet, basename='shipment')


urlpatterns = [
    path('', include(router.urls)),
    path('search/products/', ProductSearchView.as_view(), name='product_search'),
]
