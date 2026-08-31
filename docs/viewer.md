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

## Rulers

The Viewer permits to measure distances with rulers. Activate the ruler mode (the
`Ruler` button of the *Rulers* toolbar in the classic interface, the *Measurements*
section of the *Analyze* workspace in the new one, or the `L` shortcut), then drag in
the Viewer from the first point to the second one. Leave the mode with `Esc`.

A ruler is a straight segment showing its length next to it. Move the cursor close to
one of its ends to reveal a handle and drag it to adjust the measurement. Right-click a
ruler, in the Viewer or in the rulers list, to change its label, its color, or its
graduation interval, or to remove it.

The graduation interval, given in micrometers, adds tick marks along the ruler (every
fifth one is drawn longer, so ticks can be counted). It is set per ruler and is disabled
by default. Graduations that would be too dense to be readable on screen are not drawn.

Graduations can also be given as a number of divisions instead of an interval, which is
often more natural on a distance you have just measured: asking for 10 graduations on a
150 µm ruler graduates it every 15 µm. The number of graduations does not have to be a
whole number — 7.5 graduations over 150 µm is an interval of 20 µm.

The two forms are exclusive: a ruler stores one or the other, and they behave differently
when an endpoint is moved. A fixed interval stays put and the number of graduations
changes; a fixed number of graduations stays put and the interval follows the new length.

The rulers list shows both values in two columns, *Graduation* and *Nb graduations*, and
writes the fixed one in bold — the other is derived from it and moves when the ruler is
resized.

Rulers are saved in the settings file, so they are restored with the session. They can
also be created and removed through the [REST API](rest.md) and the
[MCP server](mcp.md).

## Scan zone representation

The Viewer permits to define zones, that can be used to define areas for scan operations.
When zones are defined, the zones are represented as green areas and the scan points are
displayed as red dots. The 5 next points are displayed in the Viewer, such as the 5 last
points.

Go to the [Scan](scan.md) page to get more information on how to use the Zone definition
tool to create zones, configure the density of points in the zones, and trigger the move
of the main stage in your execution script.
