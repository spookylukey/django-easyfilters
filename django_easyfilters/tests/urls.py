# URLs to make it easy to add more data for the test suite.
try:
    from django.conf.urls.defaults import *
except ImportError:
    from django.conf.urls import *
from django.contrib import admin
admin.autodiscover()


urlpatterns = patterns('',
                       (r'^books/', 'django_easyfilters.tests.views.books'),
                       (r'^book-search/', 'django_easyfilters.tests.views.book_search'),
                       (r'^authors/', 'django_easyfilters.tests.views.authors'),
                       (r'^admin/', include(admin.site.urls)),

)

