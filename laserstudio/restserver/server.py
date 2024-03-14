import flask
from flask_restx import Api, Resource, fields
from flask_restx.api import HTTPStatus
from typing import List, Optional, TYPE_CHECKING, cast
from PyQt6.QtCore import (
    QObject,
    QThread,
    Qt,
    QMetaObject,
    Q_RETURN_ARG,
    Q_ARG,
    pyqtSlot,
    QVariant,
)
from ..lsapi.lsapi import LSAPI
import io
from PIL.Image import Image

if TYPE_CHECKING:
    from ..laserstudio import LaserStudio


class RestProxy(QObject):
    """
    Class to execute the requests from REST object lying the RestThread, in the same thread that
    laser studio.
    """

    def __init__(self, laser_studio: "LaserStudio"):
        super().__init__()
        self.laser_studio: LaserStudio = laser_studio
        self.rest_object = RestServer(self)
        self._thread = RestThread()
        self.rest_object.moveToThread(self._thread)
        self._thread.start()

    @pyqtSlot(result="QVariant")
    def handle_go_next(self):
        response = self.laser_studio.handle_go_next()
        return QVariant(response)

    @pyqtSlot(result="QVariant")
    def handle_autofocus(self):
        return QVariant({"error": "Not implemented"})
        try:
            return QVariant(self.laser_studio.autofocus(no_warning=True))
        except RuntimeError as e:
            return {"error": str(e)}

    @pyqtSlot(result="QVariant")
    def handle_go_to_memory_point(self, name: str):
        return QVariant({"error": "Not implemented"})
        return QVariant(self.laser_studio.handle_go_to_memory_point(name))

    @pyqtSlot(QVariant, QVariant, result="QVariant")
    def handle_add_measurements(
        self, pos: Optional[List[List[float]]], color: Optional[List[float]]
    ):
        return QVariant(self.laser_studio.handle_add_measurements(pos, color))

    @pyqtSlot(QVariant, result="QVariant")
    def handle_position(self, pos: Optional[List[float]]):
        return QVariant({"error": "Not implemented"})
        return QVariant(self.laser_studio.handle_position(pos))

    @pyqtSlot(QVariant, result="QVariant")
    def handle_camera(self, path: Optional[str]):
        return QVariant(self.laser_studio.handle_camera(path))

    @pyqtSlot(QVariant, result="QVariant")
    def handle_screenshot(self, path: Optional[str]):
        return QVariant(self.laser_studio.handle_screenshot(path))

    @pyqtSlot(QVariant, QVariant, QVariant, QVariant, result="QVariant")
    def handle_laser(
        self,
        num: int,
        active: Optional[bool],
        power: Optional[float],
        offset_current: Optional[float],
    ):
        return QVariant({"error": "Not implemented"})
        return QVariant(
            self.laser_studio.handle_laser(num, active, power, offset_current)
        )


class RestThread(QThread):
    """
    Subclass of QThread where to launch the Rest server.
    """

    def run(self):
        RestServer.serve(LSAPI.PORT)
        super(RestThread, self).run()


class RestServer(QObject):
    """
    Object that is moved in the REST-dedicated thread.
    Follows the singleton pattern
    """

    _shared: Optional["RestServer"] = None

    @staticmethod
    def shared(proxy: Optional[RestProxy] = None) -> "RestServer":
        if RestServer._shared is None:
            RestServer._shared = RestServer(proxy)
        return RestServer._shared

    def __init__(self, proxy: Optional[RestProxy], parent: Optional[QObject] = None):
        super(RestServer, self).__init__(parent)
        self.proxy = proxy
        RestServer._shared = self

    @staticmethod
    def serve(port: int):
        """
        Launch flask's REST server on the given port

        :param port: The HTTP port to listen
        """
        flask_app.run(host="localhost", port=port)

    @staticmethod
    def invoke(member: str, *args) -> QVariant:
        """
        Invoke a given method name to the Proxy, with given arguments.
        The Proxy lies in the same thread that the main application.
        The method call is blocking until execution is done.

        :param member: The string value of the method to call
        :param args: The list of arguments to pass to the method invoked.
        :return: a QVariant (which can be None) returned by the invoked method.
        """
        proxy = RestServer.shared().proxy
        assert proxy is not None
        l_args = [Q_ARG(type(arg), arg) for arg in args]
        retval = cast(
            QVariant,
            QMetaObject.invokeMethod(
                proxy,
                member,
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_RETURN_ARG(QVariant),
                *l_args,
            ),
        )
        return retval


flask_app = flask.Flask(__name__)
flask_api = Api(flask_app, version="1.1", title="LaserStudio REST API")

image = flask_api.namespace("images", description="Get some images")
path_png = image.model("Image Path", {"path": fields.String(example="/tmp/image.png")})


@image.route("/screenshot")
class Screenshot(Resource):
    @image.produces(["image/png"])
    def get(self):
        im = cast(Image, RestServer.invoke("handle_screenshot", QVariant(None)))
        buffer = io.BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        return flask.send_file(buffer, mimetype="image/png")

    @image.expect(path_png)
    def post(self):
        if not flask.request.is_json:
            return "Given value is not a JSON", 415
        json = flask.request.json
        if not isinstance(json, dict):
            return "Given value is not a dictionary", 415
        path = json.get("path")
        RestServer.invoke("handle_screenshot", QVariant(path))
        return ""


@image.route("/camera")
class Camera(Resource):
    @image.produces(["image/png"])
    @image.response(
        HTTPStatus.NOT_FOUND, "No image can be produced (there may be no camera)"
    )
    def get(self):
        im = cast(Optional[Image], RestServer.invoke("handle_camera", QVariant(None)))
        if im is None:
            flask_api.abort(
                HTTPStatus.NOT_FOUND,
                "No image can be produced (there may be no camera)",
            )
            return
        buffer = io.BytesIO()
        im.save(buffer, format="PNG")
        buffer.seek(0)
        return flask.send_file(buffer, mimetype="image/png")

    @image.expect(path_png)
    def post(self):
        if not flask.request.is_json:
            return "Given value is not a JSON", 415
        json = flask.request.json
        if not isinstance(json, dict):
            return "Given value is not a dictionary", 415
        path = json.get("path")
        RestServer.invoke("handle_camera", QVariant(path))
        return ""


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
    #@motion.marshal_with(gonext_response)
    def post(self):
        return RestServer.invoke("handle_go_next")


@motion.route("/autofocus")
class Autofocus(Resource):
    @motion.response(200, "Autofocus is done", stage_pos)
    def get(self):
        return RestServer.invoke("handle_autofocus")


memory_point = motion.model("MemoryPoint", {"name": fields.String(example="M1")})


@motion.route("/go_to_memory_point")
class GoToMemoryPoint(Resource):
    @motion.expect(memory_point)
    @motion.response(200, "Go to memory point is done", stage_pos)
    def put(self):
        if not flask.request.is_json:
            return "Given value is not a JSON", 415
        json = flask.request.json
        if not isinstance(json, dict):
            return "Given value is not a dictionary", 415
        name = json.get("name")
        return RestServer.invoke("handle_go_to_memory_point", name)


position_move = motion.model(
    "Stage State", {"pos": stage_pos, "moving": fields.Boolean}
)


@motion.route("/position")
class Position(Resource):
    @motion.expect(motion.model("Stage Position", {"pos": stage_pos}))
    @motion.response(200, "Go to position is done", position_move)
    def put(self):
        if not flask.request.is_json:
            return "Given value is not a JSON", 415
        json = flask.request.json
        if not isinstance(json, dict):
            return "Given value is not a dictionary", 415
        pos = json.get("pos")
        return RestServer.invoke("handle_position", QVariant(pos))

    @motion.response(200, "Stage position and moving state", position_move)
    def get(self):
        return RestServer.invoke("handle_position", QVariant(None))


annotations = flask_api.namespace("annotation", description="Manage annotations")

measurement = flask_api.model(
    "Measurement",
    {
        "pos": fields.List(viewer_pos),
        "color": fields.List(fields.Float, example=[0.0, 1.0, 0.0, 0.5]),
    },
)


@annotations.route("/add_measurement")
class AddMeasurement(Resource):
    @annotations.expect(measurement)
    def post(self):
        if not flask.request.is_json:
            return "Given value is not a JSON", 415
        json = flask.request.json
        if not isinstance(json, dict):
            return "Given value is not a dictionary", 415
        pos = json.get("pos")
        color = json.get("color")
        qvar = RestServer.invoke(
            "handle_add_measurements", QVariant(pos), QVariant(color)
        )
        return cast(dict, qvar)


instruments = flask_api.namespace("instruments", description="Control instruments")

laser = instruments.model(
    "Laser",
    {
        "active": fields.Boolean(description="The activation state of the laser"),
        "power": fields.Float(description="The power level of the current, in percent"),
        "offset_current": fields.Float(description="The offset current, in mA"),
    },
)


@instruments.route("/laser/<int:num>")
@instruments.param("num", "Index of the laser, starting from 1")
class Laser(Resource):
    @instruments.doc("get_laser")
    @instruments.marshal_with(laser)
    def get(self, num: int):
        qvar = RestServer.invoke(
            "handle_laser",
            QVariant(num),
            QVariant(None),
            QVariant(None),
            QVariant(None),
        )
        return cast(dict, qvar)

    @instruments.doc("put_laser")
    @instruments.expect(laser)
    @instruments.marshal_with(laser)
    def put(self, num: int):
        if not flask.request.is_json:
            return "Given value is not a JSON", 415
        json = flask.request.json
        if not isinstance(json, dict):
            return "Given value is not a dictionary", 415
        active = json.get("active")
        power = json.get("power")
        offset_current = json.get("offset_current")
        qvar = RestServer.invoke(
            "handle_laser",
            QVariant(num),
            QVariant(active),
            QVariant(power),
            QVariant(offset_current),
        )
        return cast(dict, qvar)
