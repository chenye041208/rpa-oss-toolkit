from setuptools import setup, find_packages

setup(
    name="rpa-oss-toolkit",
    version="1.1.3",
    packages=find_packages(),
    install_requires=[
        "oss2>=2.0.0",
    ],
    project_urls={
        "Source": "https://github.com/chenye041208/rpa-oss-toolkit",
        "Bug Reports": "https://github.com/chenye041208/rpa-oss-toolkit/issues",
    },
)
