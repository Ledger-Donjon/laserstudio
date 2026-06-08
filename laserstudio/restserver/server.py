from __future__ import annotations

import functools
import io
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import numpy
import uvicorn
from fastapi import APIRouter, Body, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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
    Executes the REST requests (which originate from the uvicorn worker threads)
    in the same thread as Laser Studio (the GUI thread).

    A single generic slot (:meth:`_execute`) runs an arbitrary callable in the
    GUI thread and ships back either its return value or the exception it
    raised. This removes the need for one typed slot per action and lets domain
    exceptions propagate all the way to the HTTP layer.
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
        is shared by reference with the caller in the REST thread. A return
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

    def handle_camera(self, path: str | None) -> Any:
        return self.laser_studio.handle_camera(path)

    def handle_camera_accumulator(self, path: str | None) -> Any:
        return self.laser_studio.handle_camera_accumulator(path)

    def handle_camera_average(self, reset: bool) -> Any:
        return self.laser_studio.handle_camera_average(reset)

    def handle_camera_reference(
        self, dotake: bool | None = None, refname: str | None = None
    ) -> Any:
        return self.laser_studio.handle_camera_reference(dotake, refname)

    def handle_screenshot(self, path: str | None) -> Any:
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
    Subclass of QThread where to launch the REST (uvicorn) server.
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
        Launch the uvicorn server on the given host/port.

        uvicorn only installs OS signal handlers when running in the main
        thread, so it is safe to run it here from the REST :class:`QThread`.

        :param host: The network interface to listen on.
        :param port: The HTTP port to listen on.
        """
        config = uvicorn.Config(fastapi_app, host=host, port=port, log_level="warning")
        uvicorn.Server(config).run()

    @staticmethod
    def run(member: str, *args: Any) -> Any:
        """
        Invoke a handler of the proxy in the GUI thread and return its result.

        The call is blocking until execution is done. If the handler raises an
        exception (e.g. a :class:`~laserstudio.restserver.errors.LaserStudioError`),
        that exception is re-raised here, in the REST thread, so it can be
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


# --------------------------------------------------------------------------- #
# FastAPI application
# --------------------------------------------------------------------------- #

fastapi_app = FastAPI(
    title="LaserStudio REST API",
    version="2.0",
    description="REST API to control Laser Studio from external applications.",
    # Serve the Swagger UI at the root (as the previous flask-restx server did).
    docs_url="/",
    redoc_url="/redoc",
)


class ErrorDetail(BaseModel):
    code: str = Field(examples=["INSTRUMENT_NOT_FOUND"])
    message: str
    details: dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# Reusable OpenAPI documentation for the error responses.
_ERR = {"model": ErrorEnvelope}


@fastapi_app.exception_handler(LaserStudioError)
async def _laserstudio_error_handler(request: Request, exc: LaserStudioError):
    """Translate a domain error into a normalized HTTP error response."""
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


@fastapi_app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    """Return the normalized error body for request validation failures."""
    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST,
        content={
            "error": {
                "code": "INVALID_PARAMETER",
                "message": "Invalid request.",
                "details": {"errors": jsonable_encoder(exc.errors())},
            }
        },
    )


class PathBody(BaseModel):
    path: str | None = Field(default=None, examples=["/tmp/image.png"])


class PositionBody(BaseModel):
    pos: list[float] = Field(examples=[[42.5, 44.1, -10.22]])


class MarkerBody(BaseModel):
    pos: list[list[float]] | None = Field(default=None, examples=[[[42.5, 44.1]]])
    color: list[float] | None = Field(default=None, examples=[[0.0, 1.0, 0.0, 0.5]])
    label: str | None = None
    visible: bool = True


class InstrumentSettingsBody(BaseModel):
    settings: dict[str, Any]


# --- images ---------------------------------------------------------------- #

images_router = APIRouter(prefix="/images", tags=["images"])


@images_router.get("/screenshot", responses={200: {"content": {"image/png": {}}}})
def get_screenshot() -> Response:
    """Return the screenshot of the viewer as a PNG image."""
    im = RestServer.run("handle_screenshot", None)
    buffer = io.BytesIO()
    im.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


@images_router.post("/screenshot")
def post_screenshot(body: PathBody) -> str:
    """Save the screenshot to ``path`` on the serving machine."""
    RestServer.run("handle_screenshot", body.path)
    return ""


@images_router.get(
    "/camera",
    responses={200: {"content": {"image/png": {}}}, 503: _ERR},
)
def get_camera() -> Response:
    """Return the main camera image as a PNG image."""
    im = RestServer.run("handle_camera", None)
    buffer = io.BytesIO()
    im.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


@images_router.post("/camera", responses={503: _ERR})
def post_camera(body: PathBody) -> str:
    """Save the main camera image to ``path`` on the serving machine."""
    RestServer.run("handle_camera", body.path)
    return ""


@images_router.get("/camera/accumulator", responses={503: _ERR})
def get_accumulator() -> Response:
    """Return the camera accumulator data as a numpy ``.npy`` payload."""
    frame = RestServer.run("handle_camera_accumulator", None)
    buffer = io.BytesIO()
    numpy.save(buffer, frame)
    return Response(
        content=buffer.getvalue(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=accumulator.npy"},
    )


@images_router.post("/camera/accumulator", responses={503: _ERR})
def post_accumulator(body: PathBody) -> str | None:
    """Save the camera accumulator data to ``path`` on the serving machine."""
    RestServer.run("handle_camera_accumulator", body.path)
    return body.path


@images_router.get("/camera/averaging")
def get_averaging() -> int:
    """Return the current number of averaged images."""
    return int(RestServer.run("handle_camera_average", False))


@images_router.delete("/camera/averaging")
def delete_averaging() -> int:
    """Clear the current average and return the new count."""
    return int(RestServer.run("handle_camera_average", True))


@images_router.get("/camera/reference", responses={503: _ERR})
@images_router.get("/camera/reference/{refname}", responses={503: _ERR})
def get_reference(refname: str | None = None):
    """Select and return the current reference image name."""
    return RestServer.run("handle_camera_reference", None, refname)


@images_router.post("/camera/reference", responses={503: _ERR})
@images_router.post("/camera/reference/{refname}", responses={503: _ERR})
def post_reference(refname: str | None = None):
    """Take a new reference image and return its name."""
    return RestServer.run("handle_camera_reference", True, refname)


@images_router.delete("/camera/reference", responses={503: _ERR})
@images_router.delete("/camera/reference/{refname}", responses={503: _ERR})
def delete_reference(refname: str | None = None):
    """Unset the reference image and return the current name."""
    return RestServer.run("handle_camera_reference", False, refname)


# --- motion ---------------------------------------------------------------- #

motion_router = APIRouter(prefix="/motion", tags=["motion"])


@motion_router.post("/go_next", responses={409: _ERR})
def post_go_next():
    """Jump to the next scan position."""
    return RestServer.run("handle_go_next")


@motion_router.post("/autofocus", responses={503: _ERR})
def post_autofocus():
    """Perform autofocus."""
    return RestServer.run("handle_autofocus", False)


@motion_router.put("/autofocus", responses={503: _ERR})
def put_autofocus():
    """Register current position for autofocus."""
    return RestServer.run("handle_autofocus", True)


@motion_router.get("/autofocus", responses={503: _ERR})
def get_autofocus():
    """Get current registered points for autofocus."""
    return RestServer.run("handle_autofocus", None)


@motion_router.get("/magicfocus", responses={503: _ERR})
def get_magicfocus():
    """Get the status of magicfocus."""
    return RestServer.run("handle_magicfocus", None)


@motion_router.post("/magicfocus", responses={503: _ERR})
def post_magicfocus(parameters: dict[str, Any] = Body(default_factory=dict)):
    """Perform magicfocus with the given parameters."""
    RestServer.run("handle_magicfocus", parameters)
    return {"OK": True}


@motion_router.put("/go_to_memory_point/{index}", responses={404: _ERR, 503: _ERR})
def put_memory_point(index: int):
    """Move the stage to the memory point at ``index``."""
    return RestServer.run("handle_go_to_memory_point", index)


@motion_router.get("/position", responses={503: _ERR})
def get_position():
    """Return the current stage position."""
    return RestServer.run("handle_position", None)


@motion_router.put("/position", responses={400: _ERR, 503: _ERR})
def put_position(body: PositionBody):
    """Move the stage to the given position and return the final position."""
    return RestServer.run("handle_position", body.pos)


# --- annotation ------------------------------------------------------------ #

annotation_router = APIRouter(prefix="/annotation", tags=["annotation"])


@annotation_router.put("/add_markers", responses={400: _ERR})
@annotation_router.put("/add_marker", responses={400: _ERR})
@annotation_router.put("/add_measurement", responses={400: _ERR})
def add_markers(body: MarkerBody):
    """Add one or several markers and return their final position(s)/id(s)."""
    return RestServer.run(
        "handle_add_markers", body.pos, body.color, body.label, body.visible
    )


@annotation_router.get("/markers")
def get_markers():
    """Return the list of markers currently in the scene."""
    return RestServer.run("handle_markers")


# --- instruments ----------------------------------------------------------- #

instruments_router = APIRouter(prefix="/instruments", tags=["instruments"])


@instruments_router.get("/{label}/settings", responses={404: _ERR})
def get_instrument_settings(label: str):
    """Return the settings of the instrument identified by ``label``."""
    return RestServer.run("handle_instrument_settings", label, None)


@instruments_router.put("/{label}/settings", responses={404: _ERR, 400: _ERR})
def put_instrument_settings(label: str, body: InstrumentSettingsBody):
    """Update and return the settings of the instrument identified by ``label``."""
    return RestServer.run("handle_instrument_settings", label, body.settings)


for _router in (
    images_router,
    motion_router,
    annotation_router,
    instruments_router,
):
    fastapi_app.include_router(_router)
