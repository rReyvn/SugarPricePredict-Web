import os
from django.db import models
from django.conf import settings
from datetime import datetime
import pandas as pd
from .storage import DatasetStorage # Import the custom storage

class UploadedFile(models.Model):
    file = models.FileField(storage=DatasetStorage()) # Use the custom storage
    upload_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new_file = self._state.adding # Check if it's a new instance being added
        # Save the model instance first to ensure self.file is populated and has a temporary path
        super().save(*args, **kwargs)

        # Only process if it's a new file and dates haven't been set yet
        if is_new_file and self.file and not self.start_date and not self.end_date:
            original_temp_file_path = self.file.path # Path to the initially uploaded file
            try:
                with open(original_temp_file_path, 'rb') as f:
                    df = pd.read_excel(f)

                dates = []
                for col in df.columns:
                    try:
                        dates.append(pd.to_datetime(col, format="%d/ %m/ %Y"))
                    except (ValueError, TypeError):
                        continue

                if dates:
                    start_date = min(dates).date()
                    end_date = max(dates).date()

                    self.start_date = start_date
                    self.end_date = end_date
                    
                    _, file_extension = os.path.splitext(self.file.name)
                    new_filename = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}{file_extension}"
                    
                    # --- Start of new logic to handle replacement ---
                    # Check if a file with the new_filename already exists in the database
                    existing_files_with_same_name = UploadedFile.objects.filter(file=new_filename)
                    # Important: Ensure we don't try to delete the current instance if it somehow matches
                    # (e.g., if we were updating an existing instance, though current flow creates new ones)
                    if self.pk: # if it's an existing object
                        existing_files_with_same_name = existing_files_with_same_name.exclude(pk=self.pk)

                    for existing_file in existing_files_with_same_name:
                        # This deletes both the DB record and the file on disk via the model's delete method
                        existing_file.delete() 
                    # --- End of new logic ---

                    # Construct the final path where the current file should be moved
                    final_storage_path = self.file.storage.path(new_filename)

                    # Rename (move) the temporarily saved file to its final, derived name
                    os.rename(original_temp_file_path, final_storage_path)
                    
                    # Update the FileField's name attribute to reflect the new name relative to storage
                    self.file.name = new_filename
                    
                    # Save the model again with the updated file name and date fields
                    super().save(update_fields=['file', 'start_date', 'end_date'])

                else:
                    # If no dates are found, delete the initially saved temporary file and this model instance
                    if os.path.exists(original_temp_file_path):
                        os.remove(original_temp_file_path)
                    self.delete()

            except Exception as e:
                # Clean up: remove the initially saved temporary file and this model instance
                if os.path.exists(original_temp_file_path):
                    os.remove(original_temp_file_path)
                self.delete()

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
