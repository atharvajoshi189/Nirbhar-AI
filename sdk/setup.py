from setuptools import setup, find_packages

setup(
    name="agenttrust",
    version="0.1.0",
    description="Python SDK for AI agents proposing payments to Nirbhar AI Trust Layer",
    author="Nirbhar AI Core Team",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
        "cryptography>=42.0.0",
    ],
    python_requires=">=3.9",
)

