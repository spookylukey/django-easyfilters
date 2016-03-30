==================
django-easyfilters
==================


Status
======

This library is lacking a maintainer! I'm not actively using it any longer,
which means that it is only getting the most basic fixes.

If you would like to take over the project, please get in contact. (Providing
fixes for the existing issues would be a good start for showing your ability to
take it on :-).

Overview
========

This library provides filters similar in some ways to ``list_filter`` and
``date_hierarchy`` in Django's admin, but for use outside the
admin. Importantly, it also includes result counts for the choices. It is
designed to be very easy to get started with.

Download/install
================
Just install as a Python library.

PyPI page: http://pypi.python.org/pypi/django-easyfilters

Docs
====

See the docs/ directory, especially docs/overview.rst

Also hosted here: http://packages.python.org/django-easyfilters
And here: https://django-easyfilters.readthedocs.org/en/latest/

Demo
====

A small demo app is included, see the instructions in docs/develop.rst


Status
======

The library is in a useful state and is used in production. Test coverage is
extensive. Feedback regarding API or features is very welcome!

Support
=======

File bugs/feature request in the 'issues' in BitBucket:

https://bitbucket.org/spookylukey/django-easyfilters/issues?status=new&status=open

Or drop `me <http://lukeplant.me.uk/>`_ an email, I always like to hear when
people are using my stuff.

TODO
====

* Possible: ability to specify 'defaults' attribute for FilterSet
* Allow the automatic 'page' resetting to be customized