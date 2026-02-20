from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os

class DatasetStorage(FileSystemStorage):
    def __init__(self, location=None, base_url=None):
        if location is None:
            location = os.path.join(settings.BASE_DIR, "rfr_model", "datasets")
        super().__init__(location, base_url)
