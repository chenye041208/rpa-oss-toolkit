from pathlib import Path

from setuptools import setup, find_packages

README = Path(__file__).resolve().parent.parent / "README.md"
long_description = README.read_text(encoding="utf-8")

setup(
    name="rpa-oss-toolkit",
    use_scm_version={"root": ".."},
    setup_requires=["setuptools-scm"],
    python_requires=">=3.8",
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "oss2>=2.18.0",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "Source": "https://github.com/chenye041208/rpa-oss-toolkit",
        "Bug Reports": "https://github.com/chenye041208/rpa-oss-toolkit/issues",
    },
)
