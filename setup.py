from setuptools import setup, find_packages

exec(open('j1939/version.py').read())

description = open("README.rst").read()
# Change links to stable documentation
description = description.replace("/latest/", "/stable/")

setup(
    name="j1939",
    url="https://github.com/benkfra/j1939",
    version=__version__,
    packages=find_packages(exclude=['docs', 'examples']),
    author="Frank Benkert",
    author_email="opensource@frank-benkert.de",
    description="SAE J1939 stack implementation",
    keywords="CAN SAE J1939",
    long_description=description,
    long_description_content_type='text/x-rst',
    license="MIT",
    platforms=["any"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering"
    ],
    install_requires=["python-can>=2.0.0"],
    include_package_data=True,

    # Tests can be run using `python setup.py test`
    test_suite="nose.collector",
    tests_require=["nose"]
)
