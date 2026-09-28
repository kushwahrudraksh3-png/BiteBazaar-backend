from django.contrib import admin
from . models import User,UserProfile
from django.contrib.auth.admin import UserAdmin

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'username', 'role', 'is_active','approval_status',)
    ordering = ('-date_joined',)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = (
        ('Personal Information', {
            'fields': (
                'first_name',
                'last_name',
                'username',
                'email',
                'phone_number',
            )
        }),

        ('Role & Approval', {
            'fields': (
                'role',
                'approval_status',
            )
        }),

        ('Account Status', {
            'fields': (
                'is_active',
                'is_staff',
                'is_admin',
                'is_superadmin',
            )
        }),

        ('Important Dates', {
            'fields': (
                'last_login',
                'date_joined',
                'created_at',
                'modified_date',
            )
        }),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(UserProfile)