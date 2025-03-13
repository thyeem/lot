import re

import setuptools

setuptools.setup(
    name="lot",
    version=re.compile(r"__version__\s*=\s*['\"](.*)['\"]").findall(
        open("lot/main.py", "r").read()
    )[0],
    description="",
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/thyeem/lot",
    author="Francis Lim",
    author_email="thyeem@gmail.com",
    license="MIT",
    classifiers=[
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    keywords="parser CSP DSL SAT",
    packages=setuptools.find_packages(),
    install_requires=["ortools", "openpyxl", "foc", "ouch"],
    python_requires=">=3.6",
)
