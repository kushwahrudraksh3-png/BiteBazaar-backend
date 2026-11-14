from django.contrib import admin
from .models import Restaurant, RestaurantTiming, Category, FoodItem

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    # Admin panel ki table mein kya kya columns dikhenge
    list_display = ['restaurant_name', 'user', 'fssai_license_number', 'is_open', 'created_at']
    
    # Search bar mein kin fields se search kar sakte hain
    search_fields = ['restaurant_name', 'fssai_license_number', 'user__email']
    
    # Right side mein filter options
    list_filter = ['is_open', 'created_at']
    
    # Data display karte time ordering
    ordering = ['-created_at']

@admin.register(RestaurantTiming)
class RestaurantTimingAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'day', 'open_time', 'close_time', 'is_closed']
    list_filter = ['day', 'is_closed']
    search_fields = ['restaurant__restaurant_name']
    


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant', 'created_at')
    search_fields = ('name', 'restaurant__restaurant_name')
    list_filter = ('restaurant',)

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'restaurant', 'category', 'price', 'is_veg', 'is_available')
    search_fields = ('name', 'restaurant__restaurant_name', 'category__name')
    list_filter = ('is_veg', 'is_available', 'restaurant')
    list_editable = ('is_available', 'price') # Direct admin panel se price aur availability change karne ke liye
