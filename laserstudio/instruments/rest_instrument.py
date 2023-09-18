import requests
from typing import Optional


class RestInstrument:
    """Class to implement REST instrument"""

    SESSIONS = {}

    def __init__(self, config: dict):
        """
        :param config: YAML configuration object
        """
        # Creates a session for the connection to the REST server.
        self.session = requests.Session()
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 4444)
        self.api_command = config.get("api_command", "position")

    def get(self) -> requests.Response:
        """Convenience function for addressing a GET request on default API command.

        :return: The response of the server
        """
        return self.send(self.api_command)

    def put(self, params: dict) -> requests.Response:
        """Convenience function for addressing a PUT request on default API command
        with given parameter.

        :return: The response of the server
        """
        return self.send(self.api_command, params=params, is_put=True)

    def post(self, params: dict) -> requests.Response:
        """Convenience function for addressing a POST request on default API command
        with given parameter.

        :return: The response of the server
        """
        return self.send(self.api_command, params=params)

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

    def __del__(self):
        """
        Called when instrument is deleted. Closes the connection to the server.
        """
        self.session.close()
