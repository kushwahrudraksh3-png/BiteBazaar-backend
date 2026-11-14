from django.urls import path
from .views import RestaurantProfileView, RestaurantTimingView

urlpatterns = [
    # Endpoint: /api/vendor/profile/
    path('profile/', RestaurantProfileView.as_view(), name='restaurant-profile'),
    path('timing/', RestaurantTimingView.as_view(), name='restaurant-timing'),
]