from setuptools import setup

setup(
    name="phoney",
    version="0.1.0",
    description="Linux companion for your Android phone via the KDE Connect protocol",
    packages=["phoney", "phoney.plugins"],
    python_requires=">=3.10",
    install_requires=["cryptography>=42"],
    scripts=["cli.py"],
    entry_points={
        "console_scripts": ["phoney=cli:main"],
    },
)
