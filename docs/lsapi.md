# LSAPI

Laser Studio can be controlled using a {doc}`rest` API.

A Python package is provided to support external control of laserstudio with a python script.

## File example

```python
from laserstudio.lsapi import LSAPI
from random import randint, choice

# Create an instance of the LSAPI
lsapi = LSAPI()

# Activation of laser
lsapi.laser(1, active=True)

for iteration in range(100):
    # Setup a random power for the laser
    lsapi.laser(1, power=randint(40, 50))
    # Move the stage to next scan point
    lsapi.go_next()

    # Do a specific action
    result = choice(["fault_passed", "time_out", "nothing"])

    # Add a marker according to a specific result
    if result == "fault_passed":
        lsapi.add_marker(color='green')
    elif result == "time_out":
        lsapi.add_marker(color='orange')
    else:
        # Nothing happened, no marker
        pass

# Deactivation of laser
lsapi.laser(1, active=False)
```

## API documentation

```{eval-rst}
.. autoclass:: laserstudio.lsapi::LSAPI
    :members:
    :undoc-members:
    :show-inheritance:
```
