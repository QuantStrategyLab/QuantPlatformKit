from setuptools import find_packages, setup


setup(
    name="quant-platform-kit",
    version="0.9.0",
    description="Shared broker adapters, domain models, execution ports, and notification utilities for QuantStrategyLab strategies.",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
