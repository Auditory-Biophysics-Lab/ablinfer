import setuptools

setuptools.setup(
    name="ablinfer",
    version="0.0.1",
    author="Ben Connors",
    author_email="ben.connors@uwo.ca",
    description="Library for dispatching to inference models",
    url="",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operation System :: OS Independent",
    ],
    python_requires=">=3.3",
    install_requires=[
        "docker==4.2.0",
        "requests",
    ],
)
