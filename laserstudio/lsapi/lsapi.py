# Client API library to interact with laserstudio via a REST API.
# Unlike laserstudio, this library does not require PyQt being installed
# (this is why it is separated from the laserstudio server code).
from typing import Optional, Union, Tuple, List, Dict
import requests
from PIL import Image
import io
import numpy


class LSAPI:
    # Default server and client port that is used by the API.
    PORT = 4444

    """
    Class which may be used by clients to connect to laserstudio and send
    commands.
    """

    def __init__(self, host="localhost", port: Optional[int] = None):
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
        self, command: str, params: Optional[dict] = None, is_put=False, is_delete=False
    ) -> requests.Response:
        """
        Sends to the session a HTTP GET, POST or PUT command according to the dict given in params.

        :param command: The REST command to be executed (eg, the path part of the URL)
        :param params: The payload to be sent in the body of the request, as a JSON
        :param is_put: To force to send a PUT command instead of a POST, when params is not None
        :param is_put: To force to send a DELETE command
        :return: The response from the server.
        """
        url = f"http://{self.host}:{self.port}/{command}"
        if is_delete:
            return self.session.delete(url, json=params)
        if params is None:
            return self.session.get(url)
        else:
            if is_put:
                return self.session.put(url, json=params)
            else:
                return self.session.post(url, json=params)

    def go_next(self) -> dict:
        """Jump to next scan position.

        :return: A dictionary giving the details about the go_next"""
        return self.send("motion/go_next", {}).json()

    def autofocus(self) -> List[float]:
        """
        Autofocus the laser.

        :return: The final stage position
        """
        return self.send("motion/autofocus").json()

    def markers(self) -> List[Dict[str, Union[int, Tuple[float, float]]]]:
        """
        Get the list of markers in the scene.

        :return: A list of dictionaries, each containing the marker's id, position and RGBA color.
        """
        return self.send("annotation/markers").json()

    def marker(
        self,
        color: Union[Tuple[float, float, float], Tuple[float, float, float, float]] = (
            0.0,
            0.0,
            0.0,
        ),
        positions: Optional[
            Union[List[Tuple[float, float]], Tuple[float, float]]
        ] = None,
    ):
        """
        Add a colored marker in the view at a specific position.

        :param color: (red, green, blue) or (red, green, blue, alpha) tuple or
            list. Each color channel is in [0, 1].
        :param positions: the position of the marker, as a tuple. If None,
            the position is retrieved from the stage's current position.
        """
        assert len(color) in (3, 4)

        params: Dict[str, list] = {"color": list(color)}
        if positions is not None:
            if isinstance(positions, tuple):
                list_positions = [list(positions)]
            else:
                list_positions = [list(position) for position in positions]
            params["pos"] = list_positions
        return self.send("annotation/add_marker", params, is_put=True).json()

    def go_to(self, index: int) -> List[float]:
        """
        Jump to saved position, referenced by a memory point index.

        :param index: The index of the memory point, in the configuration file.
        :return: The final stage position
        """
        return self.send(f"motion/go_to_memory_point/{index}", is_put=True).json()

    def camera(self, path: Optional[str] = None) -> Optional[Image.Image]:
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

    def accumulated_image(self) -> Optional[numpy.ndarray]:
        """
        Get the camera accumulator's data.
        """
        response = self.send("images/camera/accumulator")
        c = response.content
        print(len(c))
        if type(c) is bytes:
            frame = numpy.frombuffer(c)
            print(frame)
            return frame

    def averaging(self, reset=False) -> Optional[int]:
        """
        Get the number of images accumulated in the camera's accumulator.

        :param reset: If True, reset the accumulator.
        :return: The number of images accumulated in the camera's accumulator.
        """
        return self.send("images/camera/averaging", is_delete=reset).json()

    def reference_image(
        self, num: Optional[int] = None, data: Optional[numpy.ndarray] = None
    ) -> Optional[numpy.ndarray]:
        """
        Get and/or set the reference image for the camera.
        """
        self.send("images/camera/reference" + (f"/{num}" if num is not None else ""))

    def screenshot(self, path: Optional[str] = None) -> Optional[Image.Image]:
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

    def position(self) -> List[float]:
        res = self.send("motion/position")
        return res.json()

    def go_to_position(self, pos: List[float] = []) -> List[float]:
        """
        Requests the main stage to move to position the current focused object to given coordinates.
        This waits for the stage to end of move, returns the final coordinates of the stage.
        These coordinates may be different from the requested one (if the focused element has a delta).

        :param pos: the position to reach.
        :return: the final coordinates of the stage.
        """
        params = {"pos": pos}
        res = self.send("motion/position", params, is_put=True)
        return res.json()

    def instrument_settings(
        self, label: str, settings: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Retrieve or update the settings of a specific instrument.
        This method interacts with the API to either fetch the current settings
        of an instrument identified by its label or update its settings if a
        dictionary of settings is provided.

        :param label: The unique identifier for the instrument.
        :param settings: A dictionary containing the settings to update for the
                         instrument. If None, the current settings will be retrieved.
        :return: The response from the API containing the instrument's settings,
                 or None if the operation fails.
        """
        return self.send(f"instruments/{label}/settings", settings, is_put=True).json()

    def laser(
        self,
        num: int = 1,
        active: Optional[bool] = None,
        power: Optional[float] = None,
        offset_current: Optional[float] = None,
    ) -> dict:
        """
        Controls the laser's state.

        :param num: The index of the laser to control (starting from 1).
        :param active: Sets the activation's state of the laser.
        :param power: Sets the current power (in %).
        :param offset_current: Sets the offset current of the laser (in mA).
        :return: The actual settings values read back from the laser instrument.
        """
        return self.send(
            f"instruments/laser/{num}",
            {
                "active": active,
                "power": power,
                "offset_current": offset_current,
            },
            is_put=True,
        ).json()
