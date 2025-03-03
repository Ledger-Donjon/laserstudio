# Viewer

The Viewer is the zone in Laser Studio that permits to visual all graphical elements.
All elements are placed in corresponding to real-world positions, in micrometers.

## Coordinates

The Viewer is a 2D representation of the bench, where the X and Y coordinates are in micrometers. It represents the real-world position of the main stage.

When moving the cursor over the Viewer, the corresponding real-world coordinates are
displayed in the Viewer's toolbar.

The toolbar contains buttons to set up the zoom level (zoom in, zoom out, reset zoom and display all elements).

## Stage sight

When your setup is compound to a Stage and/or a Camera, the Viewer will present you
the live image of the camera, positioned at the actual position of the main stage.

## Background image

The Viewer permits to load an image, that will be displayed in the background of the Viewer.
This image is inteded to represent the device under test.

## Scan zone representation

The Viewer permits to define zones, that can be used to define areas for scan operations.
When zones are defined, the zones are represented as green areas and the scan points are
displayed as red dots. The 5 next points are displayed in the Viewer, such as the 5 last
points.

Go to the [Scan](scan.md) page to get more information on how to use the Zone definition
tool to create zones, configure the density of points in the zones, and trigger the move
of the main stage in your execution script.
