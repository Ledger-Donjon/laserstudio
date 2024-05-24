# Client API library to interact with laserstudio via a REST API.
# Unlike laserstudio, this library does not require PyQt being installed
# (this is why it is separated from the laserstudio server code).
from typing import Optional, Union, Tuple, List, Dict
import requests
from PIL import Image
import io


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
        self, command: str, params: Optional[dict] = None, is_put=False
    ) -> requests.Response:
        """
        Sends to the session a HTTP GET, POST or PUT command according to the dict given in params.

        :param command: The REST command to be executed (eg, the path part of the URL)
        :param params: The payload to be sent in the body of the request, as a JSON
        :param is_put: To force to send a PUT command instead of a POST, when params is not None
        :return: The response from the server.
        """
        url = f"http://{self.host}:{self.port}/{command}"
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
        return self.send("annotation/add_marker", params).json()

    def go_to(self, name: str) -> List[float]:
        """
        Jump to saved position, referenced by a memory point name.

        :param name: The name of the memory point.
        :return: The final stage position
        """
        return self.send("motion/go_to_memory_point", {"name": name}).json()

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
        res = self.send("motion/go_to_position", params)
        return res.json()

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
