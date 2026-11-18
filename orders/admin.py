from django.contrib import admin
from .models import Order, SubOrder, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('food_item', 'quantity', 'price')

class SubOrderInline(admin.TabularInline):
    model = SubOrder
    extra = 0
    readonly_fields = ('vendor', 'suborder_total', 'status', 'created_at')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__username', 'customer__email', 'id')
    readonly_fields = ('total_price', 'created_at', 'updated_at', 'delivery_location')
    inlines = [SubOrderInline]

@admin.register(SubOrder)
class SubOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'vendor', 'suborder_total', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('vendor__restaurant_name', 'order__id')
    readonly_fields = ('suborder_total', 'created_at', 'updated_at')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'sub_order', 'food_item', 'quantity', 'price')
    search_fields = ('food_item__name', 'sub_order__id')
    readonly_fields = ('price',)