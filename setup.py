"""Setup configuration for miso-client package."""

from setuptools import setup, find_packages

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="miso-client",
    version="3.7.0",
    author="AI Fabrix Team",
    author_email="team@aifabrix.ai",
    description="Python client SDK for AI Fabrix authentication, authorization, and logging",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aifabrix/miso-client-python",
    project_urls={
        "Homepage": "https://github.com/aifabrix/miso-client-python",
        "Documentation": "https://docs.aifabrix.ai/miso-client-python",
        "Repository": "https://github.com/aifabrix/miso-client-python",
        "Issues": "https://github.com/aifabrix/miso-client-python/issues",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "Topic :: System :: Logging",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0",
        "httpx>=0.25.0",
        "redis[hiredis]>=5.0.0",
        "PyJWT>=2.8.0",
        "cryptography>=41.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-mock>=3.12.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.5.0",
            "ruff>=0.1.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

