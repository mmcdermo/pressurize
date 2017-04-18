#!/usr/bin/env python
from setuptools import setup, find_packages

install_requires = [
    'click',
    'boto3==1.4.2',
    'requests'
]

setup(
    name='pressurize',
    version='0.1',
    description='Cloud Machine Learning Deployment',
    author='Morgan McDermott',
    author_email='morganmcdermott@gmail.com',
    long_description='',
    url='https://github.com/mmcdermo/pressurize',
    license='All rights reserved',
    zip_safe=False,
    keywords='',
    packages=find_packages(),
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'pressurize = pressurize.cli:main',
        ]
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
    ]
)
