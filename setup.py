import setuptools

setuptools.setup(
    name="ablinfer",
    version="1.2.1",
    author="Ben Connors",
    description="Library for dispatching medical images to registration and segmentation toolkits.",
    url="https://github.com/Auditory-Biophysics-Lab/ablinfer",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.3",
    install_requires=[
        "docker>=4.3.0",
        "requests",
    ],
)
