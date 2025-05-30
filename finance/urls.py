from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrencyViewSet, TransactionViewSet

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
    # Example: if you had a specific, non-Viewset view for initiating payment for an order.
    # path('orders/<int:order_id>/initiate-payment/', InitiatePaymentView.as_view(), name='initiate-order-payment'),
    # However, the current design uses an action `process-order-payment` on the TransactionViewSet.
]
