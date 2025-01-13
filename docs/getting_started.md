# Getting started


## Installation

Laser Studio needs an environment with Python 3.9+, and some extra packages.

It is commonly used on Ubuntu 22.04 and macOS, but should also run on Windows.

You can get Laser Studio installed on your computer by creating a specific python environment and using ``pip``:

```sh
python3 -m venv laserstudio
source laserstudio/bin/activate
pip install laserstudio
```

Laser Studio can then be run following command:

```sh
laserstudio
```

At first run, Laser Studio will prompt you to generate a configuration file to describe your bench. 
You can get more information on this page: {doc}`conf_file`.

## Main interface

The main interface of Laser Studio is composed of 3 main parts:

- The **{doc}`viewer`**, in the main window, where you have a view of the camera and many elements overlaying, such as markers, scan zones, probes and laser positions...
- The **Toolbars** that can be detached and moved around, and that contain the main actions and settings of the software and the {doc}`instruments`.
