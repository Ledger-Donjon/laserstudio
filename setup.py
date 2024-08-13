import codecs
import os.path
from setuptools import setup


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_info(info: str, rel_path: str):
    for line in read(rel_path).splitlines():
        if line.startswith(info):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError(f"Unable to find {info} string.")


setup(
    name="laserstudio",
    version=get_info("__version__", "laserstudio/__init__.py"),
    author=get_info("__author__", "laserstudio/__init__.py"),
    description="Python3 software for hardware evaluation",
    long_description="""
# Laser Studio

An open source python3 software designed to control hardware evaluation benches
to conduct automatized evaluations.

Laser Studio permits to have a visual representation of a spatial environment,
define zones of interests, and launch an automated scanning process to physically
and randomly go through these zones, by controlling motion devices.""",
    long_description_content_type="text/markdown",
    url="https://github.com/Ledger-Donjon/laserstudio/",
    python_requires=">=3.9",
    license="LGPLv3",
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 4 - Beta",
        # Indicate who your project is intended for
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    project_urls={
        "Documentation": "https://laserstudio.readthedocs.org/",
    },
    install_requires=[
        "PyQt6",
        "pystages==1.1.1",
        "Pillow==10.3.0",
        "opencv-python==4.9.0.80",
        "pyusb==1.2.1",
        "PyYAML==6.0.1",
        "shapely==2.0.3",
        "triangle==20200424",
        "requests==2.31.0",
        "numpy==1.26.4",
        "pypdm==1.1",
        "Flask==3.0.2",
        "flask-restx==1.3.0",
        "hidapi==0.14.0",
    ],
)
