import django
if django.VERSION < (1, 6):
    from .test_filterset import *
    from .test_ranges import *

