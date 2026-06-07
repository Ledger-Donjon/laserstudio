# Client API library to interact with laserstudio via a REST API.
# Unlike laserstudio, this library does not require PyQt being installed
# (this is why it is separated from the laserstudio server code).
from __future__ import annotations

from typing import Any
from numpy.typing import NDArray
import requests
from PIL import Image
import io
import numpy

from .errors import LSAPIConnectionError, raise_for_response


class LSAPI:
    # Default server and client port that is used by the API.
    PORT = 4444

    """
    Class which may be used by clients to connect to laserstudio and send
    commands.
    """

    def __init__(self, host: str = "localhost", port: int | None = None):
        """
        Creates a new REST session to Laser Studio, through a TCP connection.

        :param host: Network host. Default is localhost.
        :param port: Network port. Default is 4444.
        """
        # Creates a session for the connection to the REST server.
        self.host = host
        self.port = port if port is not None else LSAPI.PORT
        self.session = requests.Session()

    def __del__(self):
        """
        Called when LSAPI object is deleted. Closes the connection to the
        server.
        """
        self.session.close()

    def send(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        is_put: bool = False,
        is_delete: bool = False,
    ) -> requests.Response:
        """
        Sends to the session a HTTP GET, POST or PUT command according to the dict given in params.

        :param command: The REST command to be executed (eg, the path part of the URL)
        :param params: The payload to be sent in the body of the request, as a JSON
        :param is_put: To force to send a PUT command instead of a POST, when params is not None
        :param is_delete: To force to send a DELETE command
        :return: The response from the server.
        :raises LSAPIConnectionError: If the server cannot be reached.
        :raises LSAPIError: If the server returns an HTTP error. The concrete
            subclass matches the server-reported error ``code`` (e.g.
            :class:`~laserstudio.lsapi.errors.InstrumentNotFound`).
        """
        url = f"http://{self.host}:{self.port}/{command}"
        try:
            if is_delete:
                response = self.session.delete(url, json=params)
            elif params is None:
                response = self.session.get(url)
            elif is_put:
                response = self.session.put(url, json=params)
            else:
                response = self.session.post(url, json=params)
        except requests.exceptions.RequestException as exc:
            raise LSAPIConnectionError(
                f"Could not reach LaserStudio at {url}: {exc}"
            ) from exc
        raise_for_response(response)
        return response

    def go_next(self) -> dict[str, Any]:
        """Jump to next scan position.

        :return: A dictionary giving the details about the go_next"""
        response = self.send("motion/go_next", {})
        result: dict[str, Any] = response.json()
        return result

    def autofocus(
        self,
        register: bool | tuple[float, float, float] = False,
        get_points: bool = False,
    ) -> list[float]:
        """
        Autofocus the camera.

        :return: The final stage position
        """
        self.send("motion/autofocus")
        return []
        # if get_points is True:
        #     # GET operation
        #     return self.send("motion/autofocus").json()

        # if register is True:
        #     #
        #     return self.send("motion/autofocus", params={}).json()
        # if type(register) is tuple:
        #     return self.send(
        #         "motion/autofocus", params={"new_point": list(register)}
        #     ).json()

    def magicfocus(self, parameters: dict[str, Any] | None = None):
        """
        Perform a magic focus, or get its state (if no parameters are given).
        """
        if parameters is not None:
            return self.send("motion/magicfocus", params=parameters).json()
        return self.send("motion/magicfocus").json()

    def markers(self) -> list[dict[str, int | tuple[float, float]]]:
        """
        Get the list of markers in the scene.

        :return: A list of dictionaries, each containing the marker's id, position and RGBA color.
        """
        markers: list[dict[str, int | tuple[float, float]]] = self.send(
            "annotation/markers"
        ).json()
        return markers

    def marker(
        self,
        color: tuple[float, float, float] | tuple[float, float, float, float] = (
            0.0,
            0.0,
            0.0,
        ),
        positions: list[tuple[float, float]] | tuple[float, float] | None = None,
        label: str | None = None,
        visible: bool = True,
    ):
        """
        Add colored marker(s) in the view at a specific position(s), with an optional label.

        :param color: (red, green, blue) or (red, green, blue, alpha) tuple or
            list. Each color channel is in [0, 1].
        :param label: the label of the marker(s), as a string.
        :param positions: the position of the marker(s), as a tuple or a list of tuples.
            If None, the position is retrieved from the stage's current position.
        :param visible: if False, the marker(s) are created but not displayed (setVisible(False)).
        """
        assert len(color) in (3, 4)

        params: dict[str, list[float] | str | list[list[float]] | bool] = {
            "color": list(color),
            "visible": visible,
        }
        if label is not None:
            params["label"] = label
        if positions is not None:
            if isinstance(positions, tuple):
                list_positions = [list(positions)]
            else:
                list_positions = [list(position) for position in positions]
            params["pos"] = list_positions
        return self.send("annotation/add_markers", params, is_put=True).json()

    def go_to(self, index: int) -> list[float]:
        """
        Jump to saved position, referenced by a memory point index.

        :param index: The index of the memory point, in the configuration file.
        :return: The final stage position
        """
        pos: list[float] = self.send(
            f"motion/go_to_memory_point/{index}", is_put=True
        ).json()
        return pos

    def camera(self, path: str | None = None) -> Image.Image | None:
        """
        Returns the raw image of the camera.

        :param path: If not None, laser studio will save the image at given path on *HOST*
            machine.
        :return: The PIL Image in PNG format if the request is about getting the image data.
            Otherwise, it returns None.
        """
        if path is None:
            response = self.send("images/camera")
            return Image.open(io.BytesIO(response.content))
        else:
            # In this case, the actual returned thing is a one-pixel image placeholder
            self.send("images/camera", {"path": path})
            return None

    def accumulated_image(self, path: str | None) -> NDArray[Any] | None:
        """
        Get the camera accumulator's data, as a numpy array.
        """

        if path is None:
            response = self.send("images/camera/accumulator")
            c = response.content
            if type(c) is bytes:
                frame: NDArray[Any] = numpy.load(c)
                return frame
            # This should not happen
            return None
        else:
            # We request for the data to be saved on the host machine at given path
            response = self.send("images/camera/accumulator", {"path": path})
            frame = numpy.load(response.text.strip().strip('"'))
            return frame

    def averaging(self, reset: bool = False) -> int:
        """
        Get the number of images accumulated in the camera's accumulator.

        :param reset: If True, reset the accumulator.
        :return: The number of images accumulated in the camera's accumulator.
        :raises DeviceUnavailable: If no camera is available.
        """
        response = self.send("images/camera/averaging", is_delete=reset)
        averaging: int = response.json()
        return averaging

    def reference_image(
        self, num: int | None = None, unset: bool = False, set: bool = False
    ) -> NDArray[Any] | None:
        """
        Get and/or set the reference image for the camera.
        """
        self.send(
            "images/camera/reference" + (f"/{num}" if num is not None else ""),
            {} if set else None,
            is_delete=unset,
        )
        return None

    def screenshot(self, path: str | None = None) -> Image.Image | None:
        """
        Takes a screenshot of the current view of laser studio's scene.

        :param path: If not None, laser studio will save the image at given path on *HOST*
            machine.
        :return: The PIL Image in PNG format if the request is about getting the image data.
            Otherwise, it returns nothing.
        """
        if path is None:
            response = self.send("images/screenshot")
            return Image.open(io.BytesIO(response.content))
        else:
            # In this case, the actual returned thing is a one-pixel image placeholder
            self.send("images/screenshot", {"path": path})
            return None

    def position(self) -> list[float]:
        res = self.send("motion/position")
        pos: list[float] = res.json()["pos"]
        return pos

    def go_to_position(self, pos: list[float] = []) -> list[float]:
        """
        Requests the main stage to move to position the current focused object to given coordinates.
        This waits for the stage to end of move, returns the final coordinates of the stage.
        Final coordinates may be different from the requested one.

        Note that position is a list of elements, that may be different from the number of axes of the stage.
        If the number of elements is less than the number of axes, the missing elements (axes) are not moved.
        If the number of elements is greater than the number of axes, the extra elements are ignored.

        :param pos: the position to reach.
        :return: the final coordinates of the stage.
        """
        params = {"pos": pos}
        res = self.send("motion/position", params, is_put=True)
        pos = res.json()
        return pos

    def instrument_settings(
        self, label: str, settings: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Retrieve or update the settings of a specific instrument.
        This method interacts with the API to either fetch the current settings
        of an instrument identified by its label or update its settings if a
        dictionary of settings is provided.

        :param label: The unique identifier for the instrument.
        :param settings: A dictionary containing the settings to update for the
                         instrument. If None, the current settings will be retrieved.
        :return: The response from the API containing the instrument's settings.
        :raises InstrumentNotFound: If no instrument matches ``label``.
        """
        settings = self.send(
            f"instruments/{label}/settings", settings, is_put=True
        ).json()
        return settings

    def set_instrument_settings(self, label: str, settings: dict[str, Any]):
        """
        Set the settings of a specific instrument.
        This method interacts with the API to update the settings of an instrument
        identified by its label.

        :param label: The unique identifier for the instrument.
        :param settings: A dictionary containing the settings to update for the
                         instrument.
        :return: The response from the API containing the instrument's updated settings.
        """
        return self.send(
            f"instruments/{label}/settings", {"settings": settings}, is_put=True
        ).json()

    def get_instrument_settings(self, label: str):
        """
        Get the settings of a specific instrument.
        This method interacts with the API to retrieve the settings of an instrument
        identified by its label.

        :param label: The unique identifier for the instrument.
        :return: The response from the API containing the instrument's settings.
        """
        return self.send(f"instruments/{label}/settings").json()["settings"]
