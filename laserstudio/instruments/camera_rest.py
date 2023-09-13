from .camera import CameraInstrument
import requests
from typing import Optional, Literal
import io
from PIL import Image


class CameraRESTInstrument(CameraInstrument):
    """Class to implement REST cameras"""

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        super().__init__(config=config)
        # Creates a session for the connection to the REST server.
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 4444)
        self.api_command = config.get("api_command", "camera")
        self.session = requests.Session()

    def __del__(self):
        """
        Called camera object is deleted. Closes the connection to the server.
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

    def get_last_image(self) -> tuple[int, int, Literal["L", "RGB"], Optional[bytes]]:
        url = f"http://{self.host}:{self.port}/{self.api_command}"
        response = self.session.get(url)
        im = Image.open(io.BytesIO(response.content))
        im_rgb = im.convert("RGB")
        return *im_rgb.size, "RGB", im.tobytes()
