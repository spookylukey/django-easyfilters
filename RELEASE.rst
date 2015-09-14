Release process
===============

Requirements:
* sphinx
* tox

Process:
* Run tox and ensure there are no failures
* Also run against test_settings_postgres::

   ./manage.py test --settings=test_settings_postgres django_easyfilters

* Check version numbers in setup.py and docs/conf.py

* Build docs:

  * (could use ./setup.py build_sphinx but it is borked by setuptools/distribute)
  * cd docs; make html

  * Check built docs in browser
  * cd html, then something like::

     find . -name '*~' -delete -o -name '*.pyc' -delete;  zip -r ../django-easyfilters-0.5.zip *

* Checks::

  check-manifest

* Upload package: ./setup.py sdist bdist_wheel register upload
* Upload docs to pypi using web interface
* tag the release in hg
* Push to bitbucket
* Check readthedocs.org
