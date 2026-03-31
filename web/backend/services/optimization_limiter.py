import threading


OPTIMIZATION_SEMAPHORE = threading.BoundedSemaphore(value=1)
