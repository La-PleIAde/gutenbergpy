from setuptools import find_packages
from setuptools import setup

setup(
    packages=find_packages(),
    package_data={'gutenbergpy.caches': ['*.sql']},
    include_package_data=True)