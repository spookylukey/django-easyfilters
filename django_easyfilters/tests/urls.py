# URLs to make it easy to add more data for the test suite.
from django.conf.urls import patterns, include
from django.contrib import admin
admin.autodiscover()


urlpatterns = patterns(
    '',
    (r'^books/', 'django_easyfilters.tests.views.books'),
    (r'^book-search/', 'django_easyfilters.tests.views.book_search'),
    (r'^authors/', 'django_easyfilters.tests.views.authors'),
    (r'^admin/', include(admin.site.urls)),
)
