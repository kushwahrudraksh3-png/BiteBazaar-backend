from django.urls import path
from . views import RestaurantListView, RestaurantMenuView, CartView


urlpatterns = [
    path('restaurants/',RestaurantListView.as_view(), name='customer-restaurant-list'),
    path('restaurants/<int:restaurant_id>/menu/', RestaurantMenuView.as_view(), name='customer-restaurant-menu'),
    path('cart/', CartView.as_view(), name='customer-cart'),
]
