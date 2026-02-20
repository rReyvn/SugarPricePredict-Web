from .models import TrainingLock

def training_complete_hook(task):
    """
    Hook to be called when the training task is complete.
    Releases the training lock.
    """
    lock = TrainingLock.objects.get(pk=1)
    lock.is_locked = False
    lock.save()
