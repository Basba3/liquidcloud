from setuptools import setup, find_packages

setup(
    name="liquidcloud",
    version="1.0.0",
    packages=find_packages(),
    package_data={"liquidcloud": ["*.tcss", "styles.tcss"]},
    include_package_data=True,
    install_requires=[
        "textual>=0.70.0",
        "yt-dlp>=2024.0.0",
    ],
    entry_points={
        "console_scripts": [
            "liquidcloud = liquidcloud.app:main",
            "sctui = liquidcloud.app:main",
        ],
    },
)
