from django.urls import path
from orders.views import CheckoutAPIView

urlpatterns = [
    path('checkout/', CheckoutAPIView.as_view(), name='order-checkout'),
]