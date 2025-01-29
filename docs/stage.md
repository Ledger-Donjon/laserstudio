# Stage

A stage is an actuator, that can be configured to get and set its position.

## Refreshing time

In order to retrieve the position of the stage regularly, a refreshing time is set to 200 milliseconds by default.
This value can be changed in the configuration file through the `stage.refresh_interval`.

## PyStage support

PyStage is a Python module developed by the Donjon.

The project is hosted in [this repository](https://github.com/Ledger-Donjon/pystages), and its documentation is available [here](https://pystages.readthedocs.io/en/latest/).

Laser Studio uses this module to support the following stages as the main stage:

- Corvus

## REST Stage

If you have a service providing stage control with a REST interface, you can use it
as a Stage object in Laser Studio.

In the configuration file, specify the type of the stage as `REST` and specify also
the host, the port and the path of the URL to get the position and motion state to be retrieved and the position to set by Laser Studio.

Note that the fetching of the position and motion state may take a certain time due to network latency.

## Unit factors

Laser Studio expects stages to give their position in **micrometers**. If your
positioning system gives data in another unit, you can specify unit
factors for each axis in the configuration file with the `stage.units_factors` key with the value that will be multiplied to any value given by your positioner.

For instance, if your 2-axis stage gives values in millimeters instead of micrometers, refer in your configuration file:

```yaml
stage:
  enable: true
  type: Corvus
  units_factors: [1000.0, 1000.0]
```
