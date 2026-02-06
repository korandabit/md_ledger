from setuptools import setup, find_packages

setup(
    name='md_ledger_tool',
    version='0.1',
    packages=find_packages(),
    install_requires=[],  # add dependencies if needed
    entry_points={
        'console_scripts': [
            'md-ledger=md_ledger_tool.main:main',
        ],
    },
    include_package_data=True,
    description='CLI tool for ingesting and querying Markdown tables with provenance tracking.',
    author='Mark Koranda',
)
