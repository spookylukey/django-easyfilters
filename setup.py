#!/usr/bin/env python
from setuptools import setup, find_packages
import os


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()


def find_package_data(pkg, filetypes):
    import glob

    out = []
    for f in filetypes:
        for x in range(0, 20):
            pattern = pkg + '/' + ('*/' * x) + f
            out.extend([p[len(pkg) + 1:] for p in glob.glob(pattern)])
    return out


setup(
    name="django-easyfilters",
    version='0.6',
    packages=find_packages(),
    include_package_data=True,
    author="Luke Plant",
    author_email="L.Plant.98@cantab.net",
    url="https://bitbucket.org/spookylukey/django-easyfilters/",
    description="Easy creation of link-based filtering for a list of Django model objects.",
    long_description=(
        read('README.rst')
        + "\n\n" +
        read('CHANGES.rst')
    ),
    license = "MIT",
    keywords = "django filter autofilter drilldown easy simple",
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Framework :: Django",
        "Topic :: Software Development :: User Interfaces",
    ],
    install_requires = [
        'django >= 1.3',
        'python-dateutil',
        'six'
    ],
)
