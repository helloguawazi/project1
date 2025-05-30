from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db import transaction as django_db_transaction # For atomic operations
from decimal import Decimal, InvalidOperation # For refund amount conversion

from .models import Currency, Transaction
from shop.models import Order # Needed for linking transactions to orders
from shop.models import OrderTimeline # For logging payment events on order timeline

from .serializers import (
    CurrencySerializer, TransactionSerializer, 
    TransactionCreateSerializer, TransactionUpdateSerializer
)

# A mock payment gateway client for demonstration
class MockPaymentGateway:
    def process_payment(self, amount, currency_code, payment_method_details):
        # Simulate gateway processing
        print(f"MockGateway: Processing payment of {amount} {currency_code} with details: {payment_method_details}")
        if "fail" in payment_method_details.lower(): # Simulate failure
            return {"success": False, "transaction_id": None, "error": "Payment declined by mock gateway."}
        import uuid
        return {"success": True, "transaction_id": f"MOCK_GW_{uuid.uuid4().hex[:10].upper()}", "error": None}

    def process_refund(self, original_transaction_id, amount, currency_code):
        print(f"MockGateway: Processing refund for {original_transaction_id} of {amount} {currency_code}")
        import uuid
        return {"success": True, "refund_id": f"MOCK_REF_{uuid.uuid4().hex[:8].upper()}", "error": None}


mock_gateway = MockPaymentGateway()


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [permissions.IsAdminUser] # Only admins manage currencies
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code', 'is_default', 'is_active']

    @action(detail=False, methods=['get'], url_path='active', permission_classes=[permissions.AllowAny]) # Allow anyone to see active currencies
    def active_currencies(self, request):
        active = Currency.objects.filter(is_active=True)
        serializer = self.get_serializer(active, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        currency = self.get_object()
        currency.is_default = True
        currency.save() # This will trigger the logic in model's save method
        return Response(self.get_serializer(currency).data)


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all().select_related('order', 'user', 'currency', 'parent_transaction')
    permission_classes = [permissions.IsAdminUser] # Generally, direct transaction manipulation is for admins. Users interact via order payment flow.
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'status': ['exact'],
        'transaction_type': ['exact'],
        'currency__code': ['exact'],
        'order__order_number': ['exact'],
        'user__username': ['exact'],
        'created_at': ['gte', 'lte'],
        'processed_at': ['gte', 'lte'],
        'amount': ['gte', 'lte'],
    }
    search_fields = ['transaction_id_external', 'order__order_number', 'user__username', 'payment_method_details']
    ordering_fields = ['created_at', 'processed_at', 'amount', 'status']

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'process_order_payment': # Using a more specific action name now
            return TransactionCreateSerializer
        elif self.action in ['update', 'partial_update'] or self.action in ['complete_payment_callback', 'fail_payment_callback']: # Specific actions for updates
            return TransactionUpdateSerializer
        return TransactionSerializer

    # This is a simplified "create" - typically payment initiation is more complex
    # and tied to an order. Direct creation of transactions by API might be rare for users.
    # For admin creation:
    def perform_create(self, serializer):
        # Ensure admin user is logged if they are manually creating a transaction
        user = self.request.user if self.request.user.is_authenticated else None
        transaction = serializer.save(user=user)
        # Log on order timeline if order is present
        if transaction.order:
            OrderTimeline.objects.create(
                order=transaction.order,
                note=f"Transaction record created manually: ID {transaction.transaction_id_external or transaction.id}. Amount: {transaction.amount} {transaction.currency.code}.",
                user_triggered=user
            )

    @action(detail=False, methods=['post'], url_path='process-order-payment', permission_classes=[permissions.IsAuthenticated])
    def process_order_payment(self, request):
        """
        Simulates initiating a payment for an order.
        Expects: order_id, amount, currency_id, payment_method_details (e.g., card nonce from a frontend)
        """
        serializer = TransactionCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        order = validated_data['order']
        amount = validated_data['amount']
        currency = validated_data['currency']
        payment_method_details = validated_data.get('payment_method_details', "N/A")
        user = request.user

        if order.status == 'paid' or order.status == 'completed': # Using a hypothetical 'paid' or 'completed' status for Order
             return Response({'detail': 'Order is already paid.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if there's already a successful or pending payment for this order to prevent duplicates
        # This logic might need to be more sophisticated based on business rules
        existing_transactions = Transaction.objects.filter(order=order, status__in=['pending', 'successful'])
        if existing_transactions.exists():
            return Response({'detail': 'A payment is already pending or successful for this order.'}, status=status.HTTP_400_BAD_REQUEST)


        # Create a pending transaction record BEFORE calling the gateway
        transaction = Transaction.objects.create(
            order=order,
            user=user,
            amount=amount,
            currency=currency,
            transaction_type='payment', # Or validated_data['transaction_type'] if more flexible
            status='pending',
            payment_method_details=payment_method_details,
            notes=validated_data.get('notes', "Payment initiated by user.")
        )
        OrderTimeline.objects.create(order=order, note=f"Payment initiated. Amount: {amount} {currency.code}.", user_triggered=user, status_changed_to=order.status)

        # Simulate calling a payment gateway
        gateway_response = mock_gateway.process_payment(amount, currency.code, payment_method_details)

        with django_db_transaction.atomic():
            if gateway_response["success"]:
                transaction.transaction_id_external = gateway_response["transaction_id"]
                transaction.status = 'successful'
                transaction.processed_at = timezone.now()
                transaction.gateway_response_raw = str(gateway_response) # Store raw response
                transaction.save()

                # Update order status (simplified)
                order.status = 'processing' # Or 'paid', 'completed' depending on your Order model's status flow
                order.save(update_fields=['status'])
                OrderTimeline.objects.create(order=order, note=f"Payment successful. Transaction ID: {transaction.transaction_id_external}.", status_changed_to=order.status, user_triggered=user)
                
                return Response(TransactionSerializer(transaction).data, status=status.HTTP_200_OK)
            else:
                transaction.status = 'failed'
                transaction.processed_at = timezone.now()
                transaction.gateway_response_raw = str(gateway_response)
                transaction.notes = (transaction.notes or "") + f"\nGateway error: {gateway_response['error']}"
                transaction.save()
                OrderTimeline.objects.create(order=order, note=f"Payment failed. Error: {gateway_response['error']}", user_triggered=user)
                return Response({
                    "detail": "Payment processing failed.", 
                    "gateway_error": gateway_response["error"],
                    "transaction": TransactionSerializer(transaction).data # Show details of the failed transaction
                }, status=status.HTTP_400_BAD_REQUEST)


    # These would typically be callback URLs hit by the payment gateway, or admin actions
    @action(detail=True, methods=['post'], url_path='complete-payment') # Example for a successful async payment
    def complete_payment_callback(self, request, pk=None):
        transaction = self.get_object()
        if transaction.status != 'pending' and transaction.status != 'requires_action':
            return Response({'detail': f'Transaction is not in a pending state. Current status: {transaction.status}'}, status=status.HTTP_400_BAD_REQUEST)

        transaction.status = 'successful'
        # transaction.transaction_id_external = request.data.get('gateway_transaction_id', transaction.transaction_id_external) # If gateway provides ID later
        # transaction.gateway_response_raw = str(request.data) # Store callback data
        transaction.save() # This will update processed_at via model's save method

        if transaction.order:
            transaction.order.status = 'processing' # Or 'paid' etc.
            transaction.order.save(update_fields=['status'])
            OrderTimeline.objects.create(order=transaction.order, note=f"Payment completed for TxID: {transaction.transaction_id_external}.", status_changed_to=transaction.order.status, user_triggered=None) # System triggered
        return Response(TransactionSerializer(transaction).data)

    @action(detail=True, methods=['post'], url_path='fail-payment') # Example for a failed async payment
    def fail_payment_callback(self, request, pk=None):
        transaction = self.get_object()
        transaction.status = 'failed'
        # transaction.gateway_response_raw = str(request.data)
        transaction.save()

        if transaction.order:
            # Order status might remain 'pending' or move to a 'payment_failed' status
            OrderTimeline.objects.create(order=transaction.order, note=f"Payment failed for TxID: {transaction.transaction_id_external}.", user_triggered=None) # System triggered
        return Response(TransactionSerializer(transaction).data)


    @action(detail=True, methods=['post'], url_path='refund')
    def refund_transaction(self, request, pk=None):
        original_transaction = self.get_object()
        if original_transaction.status != 'successful' or original_transaction.transaction_type not in ['payment', 'capture']:
            return Response({'detail': 'Only successful payment or capture transactions can be refunded.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if already fully refunded
        existing_refunds = Transaction.objects.filter(parent_transaction=original_transaction, status='successful', transaction_type='refund')
        total_refunded_amount = sum(ref.amount for ref in existing_refunds)
        
        # Allow partial refunds by specifying an amount, otherwise full refund
        refund_amount_str = request.data.get('amount')
        if refund_amount_str:
            try:
                refund_amount = Decimal(refund_amount_str)
                if refund_amount <= 0 or refund_amount > (original_transaction.amount - total_refunded_amount):
                    raise ValueError("Invalid refund amount.")
            except (ValueError, TypeError, InvalidOperation): # Add InvalidOperation
                return Response({'detail': 'Invalid refund amount provided.'}, status=status.HTTP_400_BAD_REQUEST)
        else: # Default to full remaining refundable amount
            refund_amount = original_transaction.amount - total_refunded_amount


        if refund_amount <= 0: # Check if there's anything to refund
             return Response({'detail': 'This transaction has already been fully refunded or refund amount is zero.'}, status=status.HTTP_400_BAD_REQUEST)


        # Create a pending refund transaction record
        refund_tx = Transaction.objects.create(
            order=original_transaction.order,
            user=request.user, # User performing the refund (admin/staff)
            amount=refund_amount, 
            currency=original_transaction.currency,
            transaction_type='refund',
            status='pending',
            payment_method_details=original_transaction.payment_method_details, # Or specific refund method
            notes=f"Refund initiated for transaction {original_transaction.transaction_id_external}. Amount: {refund_amount}",
            parent_transaction=original_transaction
        )

        # Simulate calling gateway for refund
        gateway_response = mock_gateway.process_refund(original_transaction.transaction_id_external, refund_amount, original_transaction.currency.code)
        
        with django_db_transaction.atomic():
            if gateway_response["success"]:
                refund_tx.transaction_id_external = gateway_response["refund_id"]
                refund_tx.status = 'successful'
                refund_tx.processed_at = timezone.now()
                refund_tx.gateway_response_raw = str(gateway_response)
                refund_tx.save()

                # Update order status (e.g., to 'refunded' or 'partially_refunded')
                if original_transaction.order:
                    new_order_status = 'refunded' # Simplified
                    current_total_refunded = total_refunded_amount + refund_tx.amount
                    if current_total_refunded < original_transaction.order.total_amount: # Check against order total
                        new_order_status = 'partially_refunded' # Custom status you might add
                    
                    # original_transaction.order.status = new_order_status 
                    # original_transaction.order.save(update_fields=['status'])
                    OrderTimeline.objects.create(
                        order=original_transaction.order, 
                        note=f"Refund successful. Amount: {refund_tx.amount} {refund_tx.currency.code}. Refund TxID: {refund_tx.transaction_id_external}.",
                        status_changed_to=new_order_status, # This might be an order status
                        user_triggered=request.user
                    )
                return Response(TransactionSerializer(refund_tx).data, status=status.HTTP_200_OK)
            else:
                refund_tx.status = 'failed'
                refund_tx.processed_at = timezone.now()
                refund_tx.gateway_response_raw = str(gateway_response)
                refund_tx.notes = (refund_tx.notes or "") + f"\nGateway refund error: {gateway_response['error']}"
                refund_tx.save()
                if original_transaction.order:
                    OrderTimeline.objects.create(order=original_transaction.order, note=f"Refund failed for original TxID: {original_transaction.transaction_id_external}. Error: {gateway_response['error']}", user_triggered=request.user)
                return Response({
                    "detail": "Refund processing failed.", 
                    "gateway_error": gateway_response["error"],
                    "transaction": TransactionSerializer(refund_tx).data
                }, status=status.HTTP_400_BAD_REQUEST)
