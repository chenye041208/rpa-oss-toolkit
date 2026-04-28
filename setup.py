from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="rpa-oss-toolkit",
    version="1.1.4",
    packages=find_packages(),
    install_requires=[
        "oss2>=2.0.0",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "Source": "https://github.com/chenye041208/rpa-oss-toolkit",
        "Bug Reports": "https://github.com/chenye041208/rpa-oss-toolkit/issues",
    },
)
