from django.core.exceptions import ValidationError

MAX_LICENSE_SIZE_MB = 2


def validate_image_size(file):
    if file.size > MAX_LICENSE_SIZE_MB * 1024 * 1024:
        raise ValidationError(
            f"Image {MAX_LICENSE_SIZE_MB}MB se badi nahi honi chahiye."
        )