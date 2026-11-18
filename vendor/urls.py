from django.urls import path
from .views import RestaurantProfileView,CategoryListCreateAPIView,CategoryDetailAPIView, RestaurantTimingView,FoodItemListCreateAPIView,FoodItemDetailAPIView, ToggleRestaurantStatusView

urlpatterns = [
    # Endpoint: /api/vendor/profile/
    path('profile/', RestaurantProfileView.as_view(), name='restaurant-profile'),
    path('timing/', RestaurantTimingView.as_view(), name='restaurant-timing'),
    
    path('menu-categories/', CategoryListCreateAPIView.as_view(), name='category-list-create'),
    path('menu-categories/<int:pk>/', CategoryDetailAPIView.as_view(), name='category-detail'),
    
    path('food-items/', FoodItemListCreateAPIView.as_view(), name='fooditem-list-create'),
    path('food-items/<int:pk>/', FoodItemDetailAPIView.as_view(), name='fooditem-detail'),
    
    path('profile/status/toggle/', ToggleRestaurantStatusView.as_view(), name='restaurant-status-toggle'),

]