Getting started
===============


Installation
------------

Laser Studio needs an environment with Python 3.9+, and some extra packages.

It is commonly used on Ubuntu 22.04 and macOS, but should also run on Windows.

From source
^^^^^^^^^^^

You can get the latest version of Laser Studio by cloning the repository from GitHub:

.. code-block:: sh

    git clone https://github.com/Ledger-Donjon/laserstudio.git

Then, you can install the application by running the following command:

.. code-block:: sh
    
    python3 -m pip install -e ./laserstudio

From PyPI
^^^^^^^^^

You can get Laser Studio installed on your computer by using ``pip``:

.. code-block:: sh

    python3 -m pip install laserstudio

Configuration
-------------

Laser Studio needs a configuration file to run. This file is a YAML file that
contains the configuration of the application. You can find an example of this
file in the repository, under the name ``config.yaml.example``.

You can copy this file and modify it to describe your bench configuration.
For more details see the :ref:`configuration file <conf_file:Configuration File>` page.

Running
-------

After installing the application and get your configuration file ready, 
Laser Studio can be run as a python module with following command:

.. code-block:: sh

    python3 -m laserstudio

Main interface
--------------
