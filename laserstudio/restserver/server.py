from __future__ import annotations

import functools
import io
from typing import TYPE_CHECKING, Any

import flask
import numpy
from flask_restx import Api, Resource, fields
from flask_restx.api import HTTPStatus
from PIL.Image import Image
from PyQt6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    Q_ARG,
    pyqtSlot,
)

from ..lsapi.lsapi import LSAPI
from ..utils.yaml_types import Config
from .errors import (
    ActionNotImplementedError,
    ConflictError,
    DeviceUnavailableError,
    InvalidParameterError,
    LaserStudioError,
)

if TYPE_CHECKING:
    from ..laserstudio import LaserStudio


class RestProxy(QObject):
    """
    Executes the REST requests (which originate from the Flask thread) in the
    same thread as Laser Studio (the GUI thread).

    A single generic slot (:meth:`_execute`) runs an arbitrary callable in the
    GUI thread and ships back either its return value or the exception it
    raised. This removes the need for one typed ``QVariant`` slot per action and
    lets domain exceptions propagate all the way to the HTTP layer.
    """

    def __init__(self, laser_studio: LaserStudio, config: Config):
        super().__init__()
        self.laser_studio: LaserStudio = laser_studio
        self.rest_object = RestServer(self)
        self._thread = RestThread(config)
        self.rest_object.moveToThread(self._thread)
        self._thread.start()

    @pyqtSlot("PyQt_PyObject")
    def _execute(self, box: dict[str, Any]) -> None:
        """Run ``box['call']`` in the GUI thread, capturing result or exception.

        The result is written back into the (mutable) ``box`` dictionary, which
        is shared by reference with the caller in the Flask thread. A return
        value is intentionally *not* used: ``Q_RETURN_ARG('PyQt_PyObject')`` is
        unreliable across PyQt versions, whereas mutating a passed-by-reference
        object is robust.

        :param box: A dict containing the ``call`` to run. On return it also
            holds ``ok`` (bool) and either ``result`` or ``error``.
        """
        try:
            box["result"] = box["call"]()
            box["ok"] = True
        except Exception as exc:  # noqa: BLE001 - intentionally re-raised in caller
            box["error"] = exc
            box["ok"] = False

    # -- Handlers (run in the GUI thread through :meth:`_execute`) -----------

    def handle_go_next(self) -> Config:
        if not self.laser_studio.scanning_enabled:
            raise ConflictError("Scanning is not enabled.")
        return self.laser_studio.handle_go_next()

    def handle_magicfocus(self, parameters: dict[str, Any] | None) -> Any:
        if (f := self.laser_studio.instruments.focus_helper) is None:
            raise DeviceUnavailableError("No focus helper available.")
        if parameters is None:
            return f.magic_focus_state()
        f.magic_focus(parameters=parameters).start()
        return f.magic_focus_state()

    def handle_autofocus(self, do_register: bool | None) -> Any:
        if (f := self.laser_studio.instruments.focus_helper) is None:
            raise DeviceUnavailableError("No focus helper available.")
        return f.autofocus()

    def handle_go_to_memory_point(self, index: int) -> Any:
        return self.laser_studio.handle_go_to_memory_point(index)

    def handle_add_markers(
        self,
        pos: list[list[float]] | None,
        color: list[float] | None,
        label: str | None,
        visible: bool | None,
    ) -> Config:
        return self.laser_studio.handle_add_markers(pos, color, label, visible)

    def handle_markers(self) -> list[Config]:
        return self.laser_studio.handle_markers()

    def handle_position(self, pos: list[float] | None) -> dict[str, Any]:
        return self.laser_studio.handle_position(pos)

    def handle_camera(self, path: str | None) -> Image | None:
        return self.laser_studio.handle_camera(path)

    def handle_camera_accumulator(self, path: str | None) -> Any:
        return self.laser_studio.handle_camera_accumulator(path)

    def handle_camera_average(self, reset: bool) -> Any:
        return self.laser_studio.handle_camera_average(reset)

    def handle_camera_reference(
        self, dotake: bool | None = None, refname: str | None = None
    ) -> Any:
        return self.laser_studio.handle_camera_reference(dotake, refname)

    def handle_screenshot(self, path: str | None) -> Image:
        return self.laser_studio.handle_screenshot(path)

    def handle_laser(
        self,
        num: int,
        active: bool | None,
        power: float | None,
        offset_current: float | None,
    ) -> Any:
        raise ActionNotImplementedError("Laser control is not implemented yet.")

    def handle_instrument_settings(
        self, label: str, conf: dict[str, Any] | None
    ) -> Any:
        return self.laser_studio.handle_instrument_settings(label, conf)


class RestThread(QThread):
    """
    Subclass of QThread where to launch the Rest server.
    """

    def __init__(self, config: dict[str, Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", LSAPI.PORT)

    def run(self):
        RestServer.serve(self.host, self.port)
        super(RestThread, self).run()


class RestServer(QObject):
    """
    Object that is moved in the REST-dedicated thread.
    Follows the singleton pattern
    """

    _shared: "RestServer"

    @staticmethod
    def shared(proxy: RestProxy | None = None) -> "RestServer":
        return RestServer._shared

    def __init__(self, proxy: RestProxy | None, parent: QObject | None = None):
        super(RestServer, self).__init__(parent)
        self.proxy = proxy
        RestServer._shared = self

    @staticmethod
    def serve(host: str, port: int):
        """
        Launch flask's REST server on the given port

        :param port: The HTTP port to listen
        """
        flask_app.run(host=host, port=port)

    @staticmethod
    def run(member: str, *args: Any) -> Any:
        """
        Invoke a handler of the proxy in the GUI thread and return its result.

        The call is blocking until execution is done. If the handler raises an
        exception (e.g. a :class:`~laserstudio.restserver.errors.LaserStudioError`),
        that exception is re-raised here, in the Flask thread, so it can be
        translated into an HTTP error response.

        :param member: The name of the handler method on :class:`RestProxy`.
        :param args: The arguments to pass to the handler.
        :return: Whatever the handler returns (any Python object).
        """
        proxy = RestServer.shared().proxy
        assert proxy is not None
        box: dict[str, Any] = {"call": functools.partial(getattr(proxy, member), *args)}
        QMetaObject.invokeMethod(
            proxy,
            "_execute",
            Qt.ConnectionType.BlockingQueuedConnection,
            Q_ARG("PyQt_PyObject", box),
        )
        if not box.get("ok", False):
            raise box["error"]
        return box["result"]


flask_app = flask.Flask(__name__)
flask_api = Api(flask_app, version="1.2", title="LaserStudio REST API")


error_model = flask_api.model(
    "Error",
    {
        "code": fields.String(
            description="Machine-readable error code.",
            example="INSTRUMENT_NOT_FOUND",
        ),
        "message": fields.String(description="Human-readable error message."),
        "details": fields.Raw(description="Optional structured context."),
    },
)
error_envelope = flask_api.model("ErrorEnvelope", {"error": fields.Nested(error_model)})


@flask_api.errorhandler(LaserStudioError)
def handle_laserstudio_error(error: LaserStudioError):
    """Translate a domain error into a normalized HTTP error response."""
    return error.to_dict(), error.http_status


def _require_json() -> dict[str, Any]:
    """Return the request JSON body, raising on invalid input.

    :raises InvalidParameterError: If the body is not a JSON object.
    """
    if not flask.request.is_json:
        raise InvalidParameterError("Request body must be JSON.")
    json = flask.request.json
    if not isinstance(json, dict):
        raise InvalidParameterError("Request body must be a JSON object.")
    return json


image = flask_api.namespace("images", description="Get some images")
path_png = image.model("Image Path", {"path": fields.String(example="/tmp/image.png")})
path_file = image.model("File Path", {"path": fields.String(example="/tmp/file.bin")})


@image.route("/screenshot")
class Screenshot(Resource):
    @image.produces(["image/png"])
    def get(self):
        im = RestServer.run("handle_screenshot", None)
        buffer = io.BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        return flask.send_file(buffer, mimetype="image/png")

    @image.expect(path_png)
    def post(self):
        json = _require_json()
        RestServer.run("handle_screenshot", json.get("path"))
        return ""


@image.route("/camera")
class Camera(Resource):
    @image.produces(["image/png"])
    @image.response(
        HTTPStatus.SERVICE_UNAVAILABLE, "No camera is available", error_envelope
    )
    def get(self):
        im = RestServer.run("handle_camera", None)
        buffer = io.BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        return flask.send_file(buffer, mimetype="image/png")

    @image.expect(path_png)
    def post(self):
        json = _require_json()
        RestServer.run("handle_camera", json.get("path"))
        return ""


@image.route("/camera/accumulator")
class CameraAccumulator(Resource):
    @image.response(
        HTTPStatus.SERVICE_UNAVAILABLE,
        "No camera/data is available",
        error_envelope,
    )
    def get(self):
        frame = RestServer.run("handle_camera_accumulator", None)
        buffer = io.BytesIO()
        numpy.save(buffer, frame)
        buffer.seek(0)
        return flask.send_file(
            buffer, mimetype="application/octet-stream", download_name="accumulator.npy"
        )

    @image.expect(path_file)
    def post(self):
        json = _require_json()
        path = json.get("path")
        RestServer.run("handle_camera_accumulator", path)
        return path


count = image.model("Average Count", {"count": fields.Integer(example="50")})


@image.route("/camera/averaging")
class CameraAveraging(Resource):
    @image.response(200, "Get the current number of averaged images")
    def get(self):
        return RestServer.run("handle_camera_average", False)

    @image.response(200, "Clear the current average")
    def delete(self):
        return RestServer.run("handle_camera_average", True)


@image.route("/camera/reference/")
@image.route("/camera/reference/<refname>")
class CameraReference(Resource):
    @image.response(200, "Select the reference image")
    def get(self, refname: str | None = None):
        return RestServer.run("handle_camera_reference", None, refname)

    @image.response(200, "Set the reference image")
    def post(self, refname: str | None = None):
        return RestServer.run("handle_camera_reference", True, refname)

    @image.response(200, "Unset the reference image")
    def delete(self, refname: str | None = None):
        return RestServer.run("handle_camera_reference", False, refname)


motion = flask_api.namespace("motion", description="Control stage position")

viewer_pos = fields.List(fields.Float, example=[42.5, 44.1])
stage_pos = fields.List(fields.Float, example=[42.5, 44.1, -10.22])
laser_gonext = motion.model(
    "Laser GoNext parameters", {"current_percentage": fields.Float}
)
lasers_gonext = motion.model(
    "Lasers GoNext parameters",
    {
        "lasers": fields.List(fields.Nested(laser_gonext)),
    },
)
gonext_response = motion.model(
    "Go Next Response",
    {
        "next_point_geometry": stage_pos,
        "lasers": fields.List(fields.Nested(laser_gonext)),
        "next_point_applied": viewer_pos,
    },
)


@motion.route("/go_next")
class GoNext(Resource):
    @motion.response(HTTPStatus.CONFLICT, "Scanning is not enabled", error_envelope)
    def post(self):
        return RestServer.run("handle_go_next")


@motion.route("/autofocus")
class Autofocus(Resource):
    @motion.response(200, "Autofocus is done")
    @motion.response(
        HTTPStatus.SERVICE_UNAVAILABLE, "No focus helper available", error_envelope
    )
    def post(self):
        """Perform autofocus"""
        return RestServer.run("handle_autofocus", False)

    def put(self):
        """Register current position for autofocus"""
        return RestServer.run("handle_autofocus", True)

    def get(self):
        """Get current registered points for autofocus"""
        return RestServer.run("handle_autofocus", None)


@motion.route("/magicfocus")
class MagicFocus(Resource):
    @motion.response(200, "Get status of magicfocus")
    @motion.response(
        HTTPStatus.SERVICE_UNAVAILABLE, "No focus helper available", error_envelope
    )
    def get(self):
        return RestServer.run("handle_magicfocus", None)

    def post(self):
        """Perform magicfocus with given parameters"""
        json = _require_json()
        RestServer.run("handle_magicfocus", json)
        return {"OK": True}


@motion.route("/go_to_memory_point/<int:index>")
class GoToMemoryPoint(Resource):
    @motion.response(200, "Go to memory point is done", stage_pos)
    @motion.response(HTTPStatus.NOT_FOUND, "Unknown memory point", error_envelope)
    def put(self, index):
        return RestServer.run("handle_go_to_memory_point", index)


position_move = motion.model("Stage State", {"pos": stage_pos})


@motion.route("/position")
class Position(Resource):
    @motion.expect(motion.model("Stage Position", {"pos": stage_pos}))
    @motion.response(200, "Go to position is done", position_move)
    @motion.response(HTTPStatus.BAD_REQUEST, "Invalid position", error_envelope)
    def put(self):
        json = _require_json()
        return RestServer.run("handle_position", json.get("pos"))

    @motion.response(200, "Stage position and moving state", position_move)
    def get(self):
        return RestServer.run("handle_position", None)


annotation_ns = flask_api.namespace("annotation", description="Manage annotations")

marker = flask_api.model(
    "Marker",
    {
        "pos": fields.List(viewer_pos),
        "color": fields.List(fields.Float, example=[0.0, 1.0, 0.0, 0.5]),
        "visible": fields.Boolean(
            description="If False, marker(s) are created but not displayed."
        ),
    },
)


@annotation_ns.route("/add_markers")
@annotation_ns.route("/add_marker", doc={"description": "Alias for /add_markers"})
@annotation_ns.route("/add_measurement", doc={"description": "Alias for /add_markers"})
class AddMarker(Resource):
    @annotation_ns.expect(marker)
    @annotation_ns.response(HTTPStatus.BAD_REQUEST, "Invalid marker", error_envelope)
    def put(self):
        json = _require_json()
        return RestServer.run(
            "handle_add_markers",
            json.get("pos"),
            json.get("color"),
            json.get("label"),
            json.get("visible", True),
        )


@annotation_ns.route("/markers")
class Markers(Resource):
    def get(self):
        return RestServer.run("handle_markers")


instruments = flask_api.namespace("instruments", description="Control instruments")

instrument = instruments.model(
    "Instrument",
    {
        "settings": fields.Raw(description="The settings of the instrument"),
    },
)


@instruments.route("/<label>/settings")
@instruments.param("label", "Label of the instrument.")
@instruments.response(HTTPStatus.NOT_FOUND, "Unknown instrument", error_envelope)
class Instrument(Resource):
    @instruments.doc("get_instrument_settings")
    def get(self, label: str):
        return RestServer.run("handle_instrument_settings", label, None)

    @instruments.doc("put_instrument_settings")
    @instruments.expect(instrument)
    def put(self, label: str):
        json = _require_json()
        if "settings" not in json:
            raise InvalidParameterError("Missing 'settings' field in request body.")
        return RestServer.run("handle_instrument_settings", label, json["settings"])
