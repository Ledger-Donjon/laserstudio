# Laser Studio

An open source python3 software designed to control hardware evaluation benches
to conduct automatized evaluations.

Laser Studio permits to have a visual representation of a spatial environment,
define zones of interests, and launch an automated scanning process to physically
and randomly go through these zones, by controlling motion devices.

## Installation

Laser Studio works on Python 3.9+.

It can be installed through PyPI with:

```shell
pip install laserstudio
```

Otherwise, you can clone and install the project with:

```shell
git clone https://github.com/Ledger-Donjon/laserstudio.git
pip install ./laserstudio
```

### Package depedencies

It depends following packages to run:

- [PyQt6]
- [pystages]
- [Pillow]
- [opencv-python]
- [pyusb]
- [PyYAML]
- [shapely]
- [triangle]
- [requests]
- [numpy]
- [pypdm]
- [flask]
- [flask-restx]
- [hidapi]

## Usage

To run Laser Studio, open a terminal and run Laser Studio with the following command:

```shell
laserstudio
```

# Documentation

Advanced documentation of Laser Studio is available on [Read The Docs].

## Licensing

LaserStudio is released under GNU Lesser General Public License version 3 (LGPLv3). See LICENSE and LICENSE.LESSER for license detail

[PyQt6]: https://pypi.org/project/PyQt6/
[Pillow]: https://pillow.readthedocs.io/en/stable/index.html
[opencv-python]: https://github.com/opencv/opencv-python
[PyYAML]: https://pypi.org/project/PyYAML/
[pystages]: https://github.com/Ledger-Donjon/pystages
[shapely]: https://shapely.readthedocs.io/en/stable/manual.html
[triangle]: https://rufat.be/triangle/
[pyusb]: https://pypi.org/project/pyusb/
[requests]: https://pypi.org/project/requests/
[numpy]: https://pypi.org/project/numpy
[pypdm]: https://pypi.org/project/pypdm
[flask]: https://pypi.org/project/flask
[flask-restx]: https://pypi.org/project/flask-restx
[hidapi]: https://pipy.org/project/hidapi
[Read the Docs]: https://laserstudio.readthedocs.io/
