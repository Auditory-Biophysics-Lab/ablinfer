import setuptools

setuptools.setup(
    name="ablinfer",
    version="1.1.0",
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
        "docker>=4.2.0, <=4.2.2", ## Still waiting for device requests to be merged >.>
        "requests",
    ],
)
