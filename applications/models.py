from django.db import models
import uuid
from django.conf import settings
# Create your models here.

def upload_path(instance, kind, filename):
    # reference_id is generated before save; fall back to uuid in edge cases
    ref = instance.reference_id or ("TMP-" + uuid.uuid4().hex[:8].upper())
    return f"applications/{ref}/{kind}/{filename}"

def passport_upload_path(instance, filename):
    return upload_path(instance, "passport", filename)

def signature_upload_path(instance, filename):
    return upload_path(instance, "signature", filename)

def nin_upload_path(instance, filename):
    return upload_path(instance, "nin", filename)

class Application(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        PENDING = "pending", "Pending Review"
        QUERIED = "queried", "Queried"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_id = models.CharField(max_length=30, unique=True, editable=False, db_index=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")

    proposed_name_1 = models.CharField(max_length=200)
    proposed_name_2 = models.CharField(max_length=200, blank=True)

    nature_of_business = models.CharField(max_length=60)
    business_type = models.CharField(max_length=60)

    
    state = models.CharField(max_length=60)
    lga = models.CharField(max_length=60)
    business_address = models.CharField(max_length=255)

    owner_first_name = models.CharField(max_length=60)
    owner_last_name = models.CharField(max_length=60)
    owner_email = models.EmailField()
    owner_phone = models.CharField(max_length=30)

    business_description = models.TextField(blank=True)

    passport = models.ImageField(upload_to=passport_upload_path)
    signature = models.ImageField(upload_to=signature_upload_path)
    nin = models.FileField(upload_to=nin_upload_path)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    agent_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = "BN-" + uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_id} - {self.proposed_name_1}"
