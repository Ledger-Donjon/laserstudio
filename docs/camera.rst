Cameras
========

A camera is an instrument that can be configured to get a live image of the current device under test.

Refreshing time
---------------

In order to display a live image, a refreshing time is set to hundreds of milliseconds by default.
This value can be overrident in the :ref:`configuration file<camera:configuration file examples>`
through the ``camera.refresh_interval`` key with a value given in milliseconds.

USB Camera
----------

USB Cameras are supported thanks to OpenCV library.

In the :ref:`configuration file<camera:configuration file examples>`,
you have to specify the ``camera.type`` to ``USB``.

If your computer has multiple cameras connected, you may have to specify the ``camera.index``
that will be given to OpenCV's `VideoCapture() <https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html#aabce0d83aa0da9af802455e8cf5fd181>`__ function during the instantiation of the camera.
On Linux system, it corresponds to the number appending ``/dev/video`` device.

REST Camera
-----------

If you have a service providing pictures with a REST interface, you can use it
to use as a Camera object in Laser Studio.

In the :ref:`configuration file<camera:configuration file examples>`, you have to specify the ``camera.type`` to ``REST``.

You have also to specify the host, the port and the path of the URL
to get the image to be shown in Laser Studio, with the ``camera.host``, ``camera.port``,
and ``camera.api_command`` keys in the :doc:`conf_file`.

Note that the fetching of the image may take a certain time due to network latency.
This is why the refreshing time is set to higher that the default one.


Pixel Size
----------

In order to display the camera's image to the correct size in the :doc:`viewer`,
Laser Studio needs to have a hint on the size of a pixel, in micrometer.
You can give this information in the confiugration file, with the 
``camera.pixel_size_in_um`` key by giving an array of two decimal values (first one for the
horizontal ratio, and second one for the vertical ratio).

Negative values can be given if you need to flip the image of the camera.

Objective
---------

In the case where the camera is mounted on a optical column, the ``camera.objective`` key in the
:doc:`conf_file` can set which objective is used to magnify the image in the optical column.


Configuration file examples
---------------------------

Here are some examples for defining the configuration of the Cameras in the configuration file.
To get more information about it, see :doc:`conf_file`.

For a REST Camera
`````````````````

.. code-block:: yaml

    camera:
        enable: true
        type: REST
        refresh_interval: 1000
        api_command: "images/camera"
        pixel_size_in_um: [15.115, 15.115]
        objective: 5

For an USB Camera
`````````````````

.. code-block:: yaml

    camera:
        enable: true
        type: USB
        index: 0
        pixel_size_in_um: [120, 120]
