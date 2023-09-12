# Laser Studio

Hardware evaluation bench control software running on Python.

Laser Studio permits to have a visual representation of a spatial environment,
define zones of interests, and launch an automated to physically and randomly
go through these zones, by controlling motion devices.

## Installation

Laser Studio works on Python 3.9+.

It requires following packages to run:

- [PyQt6]
- [Pillow]
- [opencv-python]
- [pystages]
- [PyYAML]

You can install those by using the `requirements.txt` file.

```shell
python3 -m pip install --upgrade -r requirements.txt
```

## Licensing

LaserStudio is released under GNU Lesser General Public License version 3 (LGPLv3). See LICENSE and LICENSE.LESSER for license detail

[PyQt6]: https://pypi.org/project/PyQt6/
[Pillow]: https://pillow.readthedocs.io/en/stable/index.html
[opencv-python]: https://github.com/opencv/opencv-python
[PyYAML]: https://pypi.org/project/PyYAML/
[pystages]: https://github.com/Ledger-Donjon/pystages
