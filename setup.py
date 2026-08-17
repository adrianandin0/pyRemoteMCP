from setuptools import setup, find_packages

setup(
    name="pyremoteng",
    version="1.0.0",
    description="Native Python mRemoteNG clone for Linux (KDE/GNOME/XFCE) with legacy SSH and RDP engines",
    author="Antigravity Team",
    packages=find_packages(),
    install_requires=[
        "PySide6",
        "cryptography",
        "paramiko",
        "pyte"
    ],
    entry_points={
        "console_scripts": [
            "pyremoteng=pyremoteng.app:main",
        ],
    },
)
