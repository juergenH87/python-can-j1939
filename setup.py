from setuptools import setup, find_packages, Extension

exec(open('j1939/version.py').read())

description = open("README.rst").read()
# Change links to stable documentation
description = description.replace("/latest/", "/stable/")

setup(
    name="can-j1939",
    url="https://github.com/juergenH87/python-can-j1939",
    version=__version__,
    packages=find_packages(exclude=['docs', 'examples']),
    author="Juergen Heilgemeir",
    description="SAE J1939 stack implementation",
    keywords="CAN SAE J1939 J1939-FD J1939-22",
    long_description=description,
    long_description_content_type='text/x-rst',
    license="MIT",
    platforms=["any"],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering"
    ],
    install_requires=[
        "python-can>=3.3.4",
        "numpy >= 1.17.0",
        "pytest >= 6.2.5",
    ],
    include_package_data=True,

    # Tests can be run using `python setup.py test`
    test_suite="nose.collector",
    tests_require=["nose"]
)
