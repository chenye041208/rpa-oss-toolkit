from setuptools import setup, find_packages

setup(
    name="aliyunoss_rpa",
    version="1.1.0",
    packages=find_packages(),
    install_requires=[
        "oss2>=2.0.0",
    ],
)
