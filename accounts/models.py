from django.conf import settings
from django.db import models


# Create your models here.
class Profile(models.Model):
    ACCOUNT_TYPES = (
        ("public", "Public User"),
        ("agent", "Accredited Agent"),
        ("entity", "Entity / Organization"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    phone_number = models.CharField(max_length=20)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)

    def __str__(self):
        return f"{self.user.email} ({self.account_type})"



