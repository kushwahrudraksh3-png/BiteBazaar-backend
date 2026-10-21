from rest_framework import serializers
from .models import Vendor, OpeningHour
from .validators import validate_image_size



class VendorSerializer(serializers.ModelSerializer):
    vendor_license = serializers.ImageField(validators=[validate_image_size])
    
    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "vendor_slug",
            "vendor_license",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["id", "vendor_slug", "created_at", "modified_at"]


class OpeningHourSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source="get_day_display", read_only=True)

    class Meta:
        model = OpeningHour
        
        fields = ["id", "day", "day_display", "from_hour", "to_hour", "is_closed"]
        read_only_fields = ["id"]
        validators = []
        
    def validate(self, attrs):
        vendor = self.context["request"].user.vendor
        instance = self.instance

        # PATCH me kuch fields nahi aate, to purani value se kaam chalao
        day = attrs.get("day", getattr(instance, "day", None))
        is_closed = attrs.get("is_closed", getattr(instance, "is_closed", False))
        from_hour = attrs.get("from_hour", getattr(instance, "from_hour", None))
        to_hour = attrs.get("to_hour", getattr(instance, "to_hour", None))

        others = OpeningHour.objects.filter(vendor=vendor, day=day)
        if instance:
            others = others.exclude(pk=instance.pk)

        if is_closed:
            attrs["from_hour"] = None
            attrs["to_hour"] = None
            if others.exists():
                raise serializers.ValidationError(
                    "Is din ki timing pehle se hai. Closed karne se pehle unhe hatao."
                )
        else:
            if not from_hour or not to_hour:
                raise serializers.ValidationError(
                    "Open din ke liye from_hour aur to_hour dono chahiye."
                )
            if from_hour >= to_hour:
                raise serializers.ValidationError(
                    "from_hour, to_hour se pehle hona chahiye."
                )
            if others.filter(is_closed=True).exists():
                raise serializers.ValidationError("Ye din pehle se closed marked hai.")
            if others.filter(from_hour__lt=to_hour, to_hour__gt=from_hour).exists():
                raise serializers.ValidationError(
                    "Ye timing is din ki kisi doosri timing se takra rahi hai."
                )

        return attrs