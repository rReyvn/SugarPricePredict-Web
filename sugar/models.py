import os
import io
from django.db import models
from django.conf import settings
from datetime import datetime
import pandas as pd
from .storage import DatasetStorage # Import the custom storage

class UploadedFile(models.Model):
    PRICE_TYPE_CHOICES = [
        ("local", "Local"),
        ("premium", "Premium"),
    ]
    price_type = models.CharField(
        max_length=10,
        choices=PRICE_TYPE_CHOICES,
        default="local",
    )
    file = models.FileField(storage=DatasetStorage()) # Use the custom storage
    upload_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # This logic only applies when a file is being added for the first time.
        if self._state.adding and self.file:
            price_type = self.price_type
            if not price_type:
                # This should be caught by the model validation, but as a safeguard:
                raise ValueError("Price type must be set.")

            try:
                # Process the file in memory.
                self.file.seek(0)
                df = pd.read_excel(io.BytesIO(self.file.read()))

                dates = [pd.to_datetime(col, format="%d/ %m/ %Y", errors='coerce') for col in df.columns]
                dates = [d for d in dates if not pd.isna(d)]

                if not dates:
                    raise ValueError("No valid dates found in file columns.")

                self.start_date = min(dates).date()
                self.end_date = max(dates).date()

                _, file_extension = os.path.splitext(self.file.name)
                
                # Check for and delete any existing file with the same name to avoid duplicates.
                new_filename_base = f"{price_type.capitalize()}_{self.start_date.strftime('%Y-%m-%d')}_{self.end_date.strftime('%Y-%m-%d')}{file_extension}"
                new_filename_with_path = os.path.join(price_type, new_filename_base)

                existing_files = UploadedFile.objects.filter(file=new_filename_with_path)
                for f in existing_files:
                    f.delete() # This will also delete the file from storage.

                # Set the final name, which the storage backend will use.
                self.file.name = new_filename_with_path

            except Exception as e:
                # If any part of the processing fails, abort the save.
                # By not calling super().save(), the object is never persisted.
                print(f"Failed to process and save new file: {e}")
                return 

        # Call the actual save method. For new files, this happens after processing.
        super().save(*args, **kwargs)

    def __str__(self):
        return os.path.basename(self.file.name)

    @property
    def name(self):
        return os.path.basename(self.file.name)

    def delete(self, *args, **kwargs):
        # Delete the file from storage first, then the model instance
        if self.file and self.file.name: # Ensure file attribute is set and has a name
            try:
                self.file.storage.delete(self.file.name)
            except Exception as e:
                print(f"Error deleting file from storage: {self.file.name} - {e}")
        super().delete(*args, **kwargs)
