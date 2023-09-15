# Laser Studio

An open source python3 software designed to control hardware evaluation benches
to conduct automatized evaluations.

Laser Studio permits to have a visual representation of a spatial environment,
define zones of interests, and launch an automated scanning process to physically
and randomly go through these zones, by controlling motion devices.

## Installation

Laser Studio works on Python 3.9+.

It requires following packages to run:

- [PyQt6]
- [Pillow]
- [opencv-python]
- [pystages]
- [PyYAML]
- [shapely]
- [triangle]

After cloning the repository, you can install those by using the `requirements.txt` file.

```shell
git clone https://github.com/Ledger-Donjon/laserstudio.git
python3 -m pip install --upgrade -r requirements.txt
```

## Usage

To run Laser Studio, tune your configuration file `config.yaml` with appropriate
information about your hardware instruments, then a terminal and run Laser Studio as a module.

```shell
python3 -m laserstudio
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
[Read the Docs]: https://laserstudio.readthedocs.io/
