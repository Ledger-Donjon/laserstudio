# Rest interface

Laser Studio serves a REST API to be controlled by external applications.
By default, it runs by serving the api on the port 4444.

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
  "pos": [42.5, 44.1, -10.22],
  "moving": true
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
