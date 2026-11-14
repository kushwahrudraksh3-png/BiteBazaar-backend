from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models as gis_models 

User = get_user_model()

class Restaurant(models.Model):
    # Sirf unhi users ko allow karega jinka role RESTAURENT (1) hai
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="restaurant_profile",
        limit_choices_to={'role': User.RESTAURENT}
    )
    
    restaurant_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # UI aur Branding
    logo = models.ImageField(upload_to='vendor/logos/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='vendor/banners/', blank=True, null=True)
    
    # Legal aur Contact
    fssai_license_number = models.CharField(max_length=50, unique=True)
    support_phone = models.CharField(max_length=15, blank=True, null=True)
    
    # PostGIS Location aur Address
    location = gis_models.PointField(geography=True, spatial_index=True, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    
    is_open = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.restaurant_name} - {self.user.email}"
    
    
    
class RestaurantTiming(models.Model):
    DAYS_OF_WEEK = (
        (1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'),
        (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday'),
    )
    
    # Yahan humne ForeignKey use kiya hai kyunki 1 Restaurant -> Multiple (7) Timings hongi
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='timings')
    day = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK)
    open_time = models.TimeField()
    close_time = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('restaurant', 'day') # Ensure karta hai ki ek din ki ek hi entry ho
        ordering = ['day']

    def __str__(self):
        return f"{self.restaurant.restaurant_name} - {self.get_day_display()}"