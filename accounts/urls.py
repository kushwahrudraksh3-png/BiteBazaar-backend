from django.urls import path
from . import views


urlpatterns = [
    path('register-customer/', views.RegisterCustomerView.as_view(), name='register'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', views.ResendVerificationEmailView.as_view(), name='resend-verification'),
    
    path('register-restaurant/', views.RegisterVendorView.as_view(), name='register-restaurant'),
    
]