from django.urls import path
from . views import RestaurantListView, RestaurantMenuView, CartView, CustomerProfileAPIView
from vendor.views import RestaurantSearchView
from orders.views import CustomerOrderListAPIView, CustomerOrderDetailAPIView

urlpatterns = [
    path('customer-profile/', CustomerProfileAPIView.as_view(), name='customer-profile'),
    path('restaurants/',RestaurantListView.as_view(), name='customer-restaurant-list'),
    path('restaurants/<int:restaurant_id>/menu/', RestaurantMenuView.as_view(), name='customer-restaurant-menu'),
    path('restaurants/search/', RestaurantSearchView.as_view(), name='restaurant-search'),
    path('cart/', CartView.as_view(), name='customer-cart'),
    
    path('my-orders/', CustomerOrderListAPIView.as_view(), name='customer-order-list'),
    path('my-orders/<int:order_id>/', CustomerOrderDetailAPIView.as_view(), name='customer-order-detail'),
]
