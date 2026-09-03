from django.db import models


class NotificationLog(models.Model):
    channel = models.CharField(max_length=32)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")
    ok = models.BooleanField(default=False)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
