# Rest interface

Laser Studio serves a REST API to be controlled by external applications.
By default, it runs by serving the api on the port 4444.

The API is built with [FastAPI]. Interactive, auto-generated documentation is
available while Laser Studio is running:

* Swagger UI: <http://localhost:4444/docs>
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

This group of endpoints permits to add markers to be shown on the viewer.

### `/annotation/add_marker`
