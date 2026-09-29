from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register-customer/', views.RegisterCustomerView.as_view(), name='register'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', views.ResendVerificationEmailView.as_view(), name='resend-verification'),
    
    path('register-restaurant/', views.RegisterVendorView.as_view(), name='register-restaurant'),
    
    path('admin/create-admin/',views.CreateAdminView.as_view(),name='create-admin'),
    path('admin/vendors/',views.VendorListView.as_view(),name='vendor-list'),
    path('admin/vendors/<int:vendor_id>/approve/',views.ApproveVendorView.as_view(),name='approve-vendor'),
    path('admin/vendors/<int:vendor_id>/reject/',views.RejectVendorView.as_view(),name='reject-vendor'),
    
    path('login/',views.LoginView.as_view(),name='login'),
    path('token/refresh/',TokenRefreshView.as_view(),name='token-refresh'),
    
]