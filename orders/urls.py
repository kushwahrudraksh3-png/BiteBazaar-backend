from django.urls import path
from orders.views import CheckoutAPIView, VerifyPaymentAPIView, VendorSubOrderListAPIView

urlpatterns = [
    path('checkout/', CheckoutAPIView.as_view(), name='order-checkout'),
    path('verify-payment/', VerifyPaymentAPIView.as_view(), name='verify-payment'),
]





# signature generate krnee ke liye python shell se 
# import hmac, hashlib
# from django.conf import settings

# order_id = "order_U1cx9wgw8nDhcC"
# payment_id = "pay_dummy_999"

# message = f"{order_id}|{payment_id}".encode('utf-8')
# secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')

# print("NEW SIGNATURE:", hmac.new(secret, message, hashlib.sha256).hexdigest())