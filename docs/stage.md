# Stage

A stage is an actuator, that can be configured to get and set its position.

## PyStage support

PyStage is a Python module developed by the Donjon.

The project is hosted in [this repository](https://github.com/Ledger-Donjon/pystages), and its documentation is available [here](https://pystages.readthedocs.io/en/latest/).

Laser studio uses this module to support following stages as main stage:

- Corvus

## Unit factors

Laser studio expects stages to give their position in **micrometers**. If your
positioning system gives data to another unit, you can specify unit
factors for each axes in the configuration file with the "stage.units_factors" with the value that will be multiplied to any value given by your positioner.

For instance if you 2 axis-stage gives values in millimeters, refer in your configuration file:

```yaml
stage:
    ...
    units_factors: [1000.0, 1000.0]
    ...
```
