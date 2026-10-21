
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError


class Vendor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,related_name="vendor",on_delete=models.CASCADE,)
    vendor_name = models.CharField(max_length=50)
    vendor_slug = models.SlugField(max_length=100, unique=True, blank=True)
    vendor_license = models.ImageField(upload_to="vendor/license")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # slug sirf pehli baar banega, naam badalne par link na toote
        if not self.vendor_slug:
            self.vendor_slug = f"{slugify(self.vendor_name)}-{self.user_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.vendor_name
    

class OpeningHour(models.Model):
    DAYS = [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]

    vendor = models.ForeignKey(
        Vendor,
        related_name="opening_hours",
        on_delete=models.CASCADE,
    )
    day = models.PositiveSmallIntegerField(choices=DAYS)
    from_hour = models.TimeField(null=True, blank=True)
    to_hour = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ("day", "from_hour")
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "day", "from_hour", "to_hour"],
                name="unique_vendor_day_hours",
            ),
            models.UniqueConstraint(
                fields=["vendor", "day"],
                condition=models.Q(is_closed=True),
                name="unique_vendor_day_closed",
            ),
        ]

    def clean(self):
        if self.is_closed:
            # band din ke hours rakhne ka matlab nahi
            self.from_hour = None
            self.to_hour = None
            return
        if not self.from_hour or not self.to_hour:
            raise ValidationError("Open day ke liye from_hour aur to_hour dono chahiye.")
        if self.from_hour >= self.to_hour:
            raise ValidationError("from_hour, to_hour se pehle hona chahiye.")

    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.get_day_display()}"