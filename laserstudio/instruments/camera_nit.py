from .camera import CameraInstrument
from typing import Optional, Literal, cast


class CameraNITInstrument(CameraInstrument):
    """Class to implement the New Imaging Technologies cameras, using pyNit"""

    def __init__(self, config: dict):
        super().__init__(config)
        try:
            from pynit import PyNIT  # Lazy load the module # type: ignore
        except ImportError:
            raise ImportError(
                "The pynit module is required to use the NIT."
                " Please install it using 'pip install git+https://github.com/Ledger-Donjon/pynit.git'."
                " Note that this repository is private to Ledger's Donjon organization."
            )

        self.pynit = PyNIT(
            nuc_filepath=config.get(
                "nuc_filepath", "./nuc/25mhz/NUCFactory_2000us.yml"
            ),
            bpr_filepath=config.get("bpr_filepath", "./nuc/25mhz/BPM.yml"),
        )

        # Objective
        objective = cast(float, config.get("objective", 5.0))
        self.select_objective(objective)

    def get_last_image(self) -> tuple[int, int, Literal["L", "RGB"], Optional[bytes]]:
        """
        Retrieves the last image captured by the camera.

        :return: A tuple containing the width and height of the image, the format of the image as a string,
                and the image data as bytes. If the acquisition failed, the data will be None.
        :rtype: tuple[int, int, Literal["L", "RGB"], Optional[bytes]]
        """
        # pynit.get_last_image returns Tuple [width, height, fmt, data], with data being None if
        # acquisition failed.
        width, height, _, data = self.pynit.get_last_image()

        return width, height, "L", data

    @property
    def gain(self) -> tuple[float, float]:
        """
        Gets the current gain range of the camera.

        :return: A tuple containing the low and high bounds of the gain.
        :rtype: tuple[float, float]
        """
        return (
            self.pynit.gain_controller.get_low() * 64,
            self.pynit.gain_controller.get_high() * 64,
        )

    @gain.setter
    def gain(self, range: tuple[float, float]):
        """
        Sets the manual gain histogram bounds.

        :param range: A tuple containing the low and high bounds for the gain.
        :type range: tuple[float, float]

        :raises ValueError: If the high bound is lower than the low bound, or if any bound is out of the allowed range (0 to 0xFFFF).
        """
        low, high = range
        if low > high:
            raise ValueError("High bound is lower than low bound!")
        if (low < 0) or (low > 0xFFFF):
            raise ValueError("Low bound out of range!")
        if (high < 0) or (high > 0xFFFF):
            raise ValueError("High bound out of range!")
        self.pynit.gain_controller.set_range(low / 64, high / 64)

    def gain_autoset(self) -> tuple[int, int]:
        """
        Automatically sets the camera gain based on the current scene.

        :return: A tuple containing the low and high bounds of the calculated gain.
        :rtype: tuple[int, int]
        """
        return self.pynit.gain_autoset()

    @property
    def shade_correction(self) -> bytes:
        """
        Retrieve the shade correction image.

        :return: The shade correction image.
        :rtype: bytes
        """
        return self.pynit.get_shade_correction()

    @shade_correction.setter
    def shade_correction(self, data: bytes):
        """Set shade correction image."""
        return self.pynit.set_shade_correction(data)

    def shade_correct(self):
        """Use last captured image as base image for shading correction."""
        return self.pynit.shade_correct()

    def clear_shade_correction(self):
        """Clear shade correction."""
        return self.pynit.clear_shade_correction()

    @property
    def averaging(self) -> int:
        """
        Gets the current averaging setting.

        :return: The number of images over which averaging is performed.
        :rtype: int
        """
        return self.pynit.averaging.get_num()

    @averaging.setter
    def averaging(self, value: int):
        """
        Sets the number of images to average over.

        :param value: The number of images to average. Must be greater than or equal to 1.
        :type value: int

        :raises ValueError: If the provided value is less than 1.
        """
        if value < 1:
            raise ValueError("Averaging must be greater or equal to 1.")
        self.pynit.averaging.set_num(value)

    @property
    def laplacian_std_dev(self) -> float:
        """
        Return the standard deviation of the Laplacian operator on the last image.

        :return: The standard deviation of the Laplacian operator on the last image.
        :rtype: float
        """
        return self.pynit.get_laplacian_std_dev()

    @property
    def averaged_count(self):
        return self.pynit.get_averaged_count()

    def averaging_restart(self):
        self.pynit.averaging_restart()

    @property
    def counter(self):
        """Number of capture frames since last counter reset."""
        return self.pynit.counter

    def reset_counter(self):
        """Resets frame counter."""
        self.pynit.reset_counter()
