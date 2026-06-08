# MCP server

Laser Studio ships an [MCP] (Model Context Protocol) server, so MCP-compatible
clients (LLM agents, IDEs, ...) can drive Laser Studio with tools.

The MCP server is a thin layer on top of the {doc}`lsapi` REST client: it runs
as a standalone process and talks to a **running** Laser Studio instance over
its {doc}`rest`. Errors are surfaced as explicit tool errors prefixed with a
machine-readable code (e.g. `INSTRUMENT_NOT_FOUND`, `DEVICE_UNAVAILABLE`,
`INVALID_PARAMETER`, `CONNECTION_ERROR`).

[MCP]: https://modelcontextprotocol.io/

## Installation

The MCP server requires the optional `mcp` dependency:

```bash
pip install "laserstudio[mcp]"
```

## Running

Start Laser Studio first (so its REST API is available), then launch the MCP
server:

```bash
# Talk to a Laser Studio running on localhost:4444, over stdio (default).
laserstudio_mcp

# Custom Laser Studio REST endpoint.
laserstudio_mcp --host 192.168.0.10 --port 4444

# Serve over HTTP instead of stdio.
laserstudio_mcp --transport streamable-http
```

The Laser Studio endpoint can also be set with the `LASERSTUDIO_HOST` and
`LASERSTUDIO_PORT` environment variables.

## Client configuration

Most MCP clients are configured with a command to spawn the server over stdio.
For example:

```json
{
  "mcpServers": {
    "laserstudio": {
      "command": "laserstudio_mcp",
      "env": {
        "LASERSTUDIO_HOST": "localhost",
        "LASERSTUDIO_PORT": "4444"
      }
    }
  }
}
```

## Available tools

| Tool | Description |
|---|---|
| `list_instruments` | List the available instruments (type and label). |
| `get_instrument_settings` | Get the settings of an instrument by label. |
| `set_instrument_settings` | Update the settings of an instrument by label. |
| `get_stage_position` | Get the current stage position. |
| `move_stage` | Move the stage to a position. |
| `go_to_memory_point` | Move the stage to a memory point. |
| `go_next` | Jump to the next scan position. |
| `autofocus` | Perform an autofocus. |
| `magic_focus` | Perform a magic focus or get its state. |
| `list_markers` | List the markers in the viewer. |
| `add_marker` | Add a marker in the viewer. |
| `get_camera_image` | Capture the main camera image (PNG). |
| `get_screenshot` | Capture a screenshot of the viewer (PNG). |
| `get_averaging` | Get the camera averaging count. |
| `reset_averaging` | Reset the camera averaging. |
