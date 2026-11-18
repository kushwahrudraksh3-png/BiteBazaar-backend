from django.urls import path
from .views import RestaurantProfileView, RestaurantTimingView, ToggleRestaurantStatusView

urlpatterns = [
    # Endpoint: /api/vendor/profile/
    path('profile/', RestaurantProfileView.as_view(), name='restaurant-profile'),
    path('timing/', RestaurantTimingView.as_view(), name='restaurant-timing'),
    path('profile/status/toggle/', ToggleRestaurantStatusView.as_view(), name='restaurant-status-toggle'),

]