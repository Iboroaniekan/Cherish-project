from django.db import models
from django.utils import timezone
import uuid
from django.conf import settings
import random
import string
import hashlib
import qrcode
from io import BytesIO
from django.core.files import File

def upload_path(instance, kind, filename):
    ref = instance.reference_id or ("TMP-" + uuid.uuid4().hex[:8].upper())
    return f"applications/{ref}/{kind}/{filename}"

def passport_upload_path(instance, filename):
    return upload_path(instance, "passport", filename)

def signature_upload_path(instance, filename):
    return upload_path(instance, "signature", filename)

def nin_upload_path(instance, filename):
    return upload_path(instance, "nin", filename)

def qr_upload_path(instance, filename):
    return upload_path(instance, "qr", filename)

class Application(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        PENDING = "pending", "Pending Review"
        QUERIED = "queried", "Queried"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_id = models.CharField(max_length=30, unique=True, editable=False, db_index=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")

    proposed_name_1 = models.CharField(max_length=200,)
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
    registration_number = models.CharField(max_length=12,unique=True,blank=True,null=True,editable=False)
    verification_token = models.CharField(max_length=64, blank=True)
    qr_code = models.ImageField(upload_to=qr_upload_path, blank=True, null=True)
    digital_signature = models.CharField(max_length=64, blank=True, null=True)
    business_description = models.TextField(blank=True)

    passport = models.ImageField(upload_to=passport_upload_path)
    signature = models.ImageField(upload_to=signature_upload_path)
    nin = models.FileField(upload_to=nin_upload_path)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    agent_note = models.TextField(blank=True)  # active CAC query
    previous_notes = models.JSONField(default=list, blank=True)  # query history

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_applications")
 

    def __str__(self):
        return f"{self.reference_id} - {self.proposed_name_1}"

    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = "BN-" + uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

#    generate  unique registeration number
    def generate_registration_number(self):
        while True:
            number = "RC-" + ''.join(random.choices(string.digits, k=8))
            if not Application.objects.filter(registration_number=number).exists():
                self.registration_number = number
                return number
    

    def generate_signature(self):
        data = f"{self.registration_number}{self.proposed_name_1}{self.owner_first_name}{self.owner_last_name}{self.approved_at}"
        self.digital_signature = hashlib.sha256(data.encode("utf-8")).hexdigest()
        return self.digital_signature
    
    # Generate secure verification token
    def generate_verification_token(self):
        if not self.verification_token:  # prevent regeneration
            raw_string = f"{self.registration_number}{self.proposed_name_1}{uuid.uuid4()}"
            self.verification_token = hashlib.sha256(raw_string.encode()).hexdigest()
        return self.verification_token

    # Generate QR code image
    def generate_qr_code(self):
        if not self.registration_number or not self.verification_token:
            return
         # Prevent regenerating QR if it already exists
        if self.qr_code:
            return
        verification_url = f"{settings.SITE_URL}/applications/verify/v/?token={self.verification_token}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data( verification_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        filename = f"QR-{self.registration_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)


    def approve(self, staff_user=None):
        if self.status == self.Status.APPROVED:
            return
        self.status = self.Status.APPROVED
        self.agent_note = ""
        self.approved_at = timezone.now()
        if staff_user:
            self.approved_by = staff_user
        # Generate registration number + token + QR
        if not self.registration_number:
            self.generate_registration_number()
        if not self.verification_token:
            self.generate_verification_token()
        self.generate_qr_code()
        self.generate_signature()
        self.save()
    

    def add_query_note(self, note):
        """Staff adds a new query note"""
        if self.agent_note:
            self.previous_notes.append(self.agent_note)
        self.agent_note = note
        self.status = self.Status.QUERIED
        self.save()

    def clear_query_note(self):
        """User resubmits after correction"""
        self.agent_note = ""
        self.status = self.Status.PENDING
        self.save()


   