from django.urls import path
from .views import RestaurantProfileView

urlpatterns = [
    # Endpoint: /api/vendor/profile/
    path('profile/', RestaurantProfileView.as_view(), name='restaurant-profile'),
]