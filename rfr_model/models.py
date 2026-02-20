from django.db import models

# Create your models here.
class TrainingLock(models.Model):
    is_locked = models.BooleanField(default=False)
