# Cameras

## Refreshing time

In order to display the camera live, a refreshing time is set to 200 milliseconds by default.
This value can be changed in the configuration file through the "camera.refresh_interval".

## USB Camera

USB Cameras are supported thanks to OpenCV library.

In the configuration file, you have to specify the "camera.type" to "USB".
If your computer has multiple cameras connected, you may have to specify the "camera.index"
that will be given to OpenCV's VideoCapture()
<https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html>.

## REST Camera

If you have a service providing pictures with a REST interface, you can use it
to use as a Camera object in Laser Studio

In the configuration file, specify the type of the camera as "REST" and specify also
the host, the port and the path of the URL to get the image to be shown in Laser Studio.

Note that the fetching of the image may take a certain time due to network latency. This is why the refreshing time is set to 1second by default.
