from setuptools import setup, find_packages
setup(
    name="weedit-native", version="2.0.0", packages=find_packages(),
    install_requires=["typer>=0.9.0", "rich>=13.0.0", "pydantic>=2.0.0", "pyyaml>=6.0", "numpy>=1.24.0"],
    entry_points={"console_scripts": ["weed=cli.main:app"]},
)
