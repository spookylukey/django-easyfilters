import django
if django.VERSION < (1, 6):
    from .test_filterset import *  # NOQA
    from .test_ranges import *  # NOQA
