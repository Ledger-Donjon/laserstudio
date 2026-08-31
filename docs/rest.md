# Rest interface

Laser Studio serves a REST API to be controlled by external applications.
By default, it runs by serving the api on the port 4444.

The API is built with [FastAPI]. Interactive, auto-generated documentation is
available while Laser Studio is running:

* Swagger UI: <http://localhost:4444/>
* ReDoc: <http://localhost:4444/redoc>
* OpenAPI schema: <http://localhost:4444/openapi.json>

[FastAPI]: https://fastapi.tiangolo.com/

## Error handling

On success, endpoints return a `2xx` status code. On error, they return an
appropriate HTTP status code together with a normalized JSON body:

```json
{
  "error": {
    "code": "INSTRUMENT_NOT_FOUND",
    "message": "No instrument matches the label 'laser2'.",
    "details": { "label": "laser2" }
  }
}
```

The `code` field is a stable, machine-readable identifier. The mapping between
error codes and HTTP statuses is:

| `code` | HTTP status | Meaning |
|---|---|---|
| `INVALID_PARAMETER` | `400 Bad Request` | A parameter is missing or invalid. |
| `INSTRUMENT_NOT_FOUND` | `404 Not Found` | No instrument matches the given label. |
| `MEMORY_POINT_NOT_FOUND` | `404 Not Found` | No memory point matches the given index. |
| `CONFLICT` | `409 Conflict` | The action cannot be performed in the current state (e.g. scanning not enabled). |
| `NOT_IMPLEMENTED` | `501 Not Implemented` | The action is not implemented yet. |
| `DEVICE_UNAVAILABLE` | `503 Service Unavailable` | A required device (camera, stage, focus helper...) is not available. |

A `404` denotes a *named* resource that does not exist (an instrument label, a
memory point index), whereas `503` denotes a *device type* that is not
configured or connected (no camera, no stage). The Python {doc}`lsapi` client
turns these errors into typed exceptions.

## `images` Endpoints

This group of endpoints permits to get images files.

### `/images/camera`

This endpoint returns the image of the main camera, in `PNG` format.

### `/images/screenshot`

This endpoint returns the screenshot of the Viewer as currently shown by Laser Studio. It includes the overlays (markers, camera with distortion, background image...), in `PNG` format.

```bash
curl -X 'GET' 'http://localhost:4444/images/screenshot' -H 'accept: image/png'
```

A `POST` alternative permits to get the screenshot to be stored at a specific path on the serving computer, instead of transfering the data to the client.

:::{admonition} Example with `curl`
:class: tip

```bash
curl -X 'POST' \
  'http://localhost:4444/images/screenshot' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{ "path": "/tmp/image.png" }'
```

:::

## Motion

This group of endpoints permits to control the main stage.

### `/motion/position`

This endpoint returns the current position of the main stage.

It returns a JSON object with the following structure:

```json
{
  "pos": [42.5, 44.1, -10.22]
}
```

A `PUT` version of the endpoint permit to set the position of the main stage.

The body of the request must be a JSON object.

```json
{
  "pos": [42.5, 44.1, -10.22]
}
```

## Annotation

This group of endpoints permits to add markers and rulers to be shown on the viewer.

### `/annotation/add_marker`

### `/annotation/markers`

A `GET` returns the list of markers currently in the scene.

A `DELETE` removes markers. With a `{"ids": [1, 2, 3]}` body, only the markers
with the given identifiers are removed; with no body (or `{"ids": null}`), all
markers are removed. The response lists the deleted identifiers:

```json
{
  "deleted": [1, 2, 3]
}
```

### `/annotation/add_ruler`

A `PUT` adds one or several rulers, each measuring the distance between two viewer
positions. Segments are given as `[x1, y1, x2, y2]`. The `color`, `label`,
`graduation` (tick interval in µm) and `visible` fields are optional:

```json
{
  "segments": [[0.0, 0.0, 300.0, 400.0]],
  "color": [0.87, 1.0, 0.0, 1.0],
  "label": "die pitch",
  "graduation": 100.0
}
```

`graduation_count` may be given instead of `graduation` to express the graduations as
a number of divisions: each ruler keeps that count and derives its interval from its own
length, so 10 graduations on a 150 µm ruler means an interval of 15 µm, and the count
stays 10 if the ruler is later resized. It may be fractional (7.5 graduations over
150 µm is a 20 µm interval) and must be strictly positive. The two forms are exclusive,
and a ruler reports only the one it was given; giving both is an error.

The response describes the created ruler, including its `id` and its `length`. When
several segments are given, the created rulers are listed under the `rulers` key.

### `/annotation/rulers`

A `GET` returns the list of rulers currently in the scene.

A `DELETE` removes rulers. With a `{"ids": [1, 2, 3]}` body, only the rulers with the
given identifiers are removed; with no body (or `{"ids": null}`), all rulers are
removed. The response lists the deleted identifiers.

### `/annotation/pixel_to_position`

A `POST` with a `{"pixels": [[px, py], ...]}` body converts camera-image pixel
coordinates (origin at the top-left of the image) into viewer coordinates. The
conversion uses the actual scene transform of the camera image, so it accounts
for the camera resolution, the objective, the stage position and any image
distortion:

```json
{
  "positions": [[30.0, 40.0], [-2850.0, 1660.0]]
}
```

## Instruments

This group of endpoints permits to list and configure the instruments.

### `/instruments/`

A `GET` on this endpoint returns the list of available instruments, each
described by its `type` (the instrument class name) and its `label`:

```json
[
  { "type": "StageInstrument", "label": "Main stage" },
  { "type": "PDMInstrument", "label": "PDM" }
]
```

### `/instruments/<label>/settings`

A `GET` returns the settings of the instrument identified by `<label>`, and a
`PUT` (with a `{"settings": {...}}` body) updates them. An unknown label returns
a `404` error.

## Scan geometry

This group of endpoints permits to read and update the scanning geometry shown
in the viewer.

### `/scangeometry`

A `GET` returns the current scan geometry settings (``geometry`` and
``density``):

```json
{
  "density": 100,
  "geometry": {
    "polygon": {
      "exterior": [
        {"x": 0.0, "y": 0.0},
        {"x": 100.0, "y": 0.0},
        {"x": 100.0, "y": 100.0},
        {"x": 0.0, "y": 100.0},
        {"x": 0.0, "y": 0.0}
      ],
      "interiors": []
    }
  }
}
```

A `PUT` (with a `{"settings": {...}}` body in the same format) updates them.

A `DELETE` clears the geometry by setting an empty polygon and returns the new
settings.
