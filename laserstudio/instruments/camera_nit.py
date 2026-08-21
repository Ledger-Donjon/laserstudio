from __future__ import annotations
from typing import cast, Any
from numpy import frombuffer, resize, uint8, zeros, float32
from numpy.typing import NDArray
from .camera import CameraInstrument
from ..utils.util import expand_path
from ..utils.yaml_types import Config


class CameraNITInstrument(CameraInstrument):
    """Class to implement the New Imaging Technologies cameras, using pyNit"""

    DEFAULT_OBJECTIVES: list[float] = [5.0, 10.0, 20.0, 50.0]

    def __init__(self, config: Config):
        super().__init__(config)
        try:
            from pynit import PyNIT  # Lazy load the module
        except ImportError:
            raise ImportError(
                "The pynit module is required to use the NIT."
                " Please install it using 'pip install git+https://github.com/Ledger-Donjon/pynit.git'."
                " Note that this repository is private to Ledger's Donjon organization."
            )

        nuc_filepath = config.get("nuc_filepath", "./nuc/25mhz/NUCFactory_2000us.yml")
        bpr_filepath = config.get("bpr_filepath", "./nuc/25mhz/BPM.yml")
        if not isinstance(nuc_filepath, str):
            raise ValueError("nuc_filepath must be a string")
        if not isinstance(bpr_filepath, str):
            raise ValueError("bpr_filepath must be a string")

        nuc_filepath = expand_path(nuc_filepath)
        bpr_filepath = expand_path(bpr_filepath)

        self.pynit = PyNIT(nuc_filepath, bpr_filepath)

        # Objective
        objective = cast(float, config.get("objective", 5.0))
        self.select_objective(objective)
        self.include_current_objective()

    def capture_image(self) -> NDArray[Any] | None:
        width, height, _, data = self.pynit.get_last_image()
        if data is None:
            return None
        if width != self.width or height != self.height:
            self.set_resolution(width, height)
        # get_last_image returns Tuple always 'L' for the 'mode'
        frame = frombuffer(data, dtype=uint8)
        frame = resize(frame, width * height)
        return frame

    @property
    def gain(self) -> tuple[float, float]:
        """
        Gets the current gain range of the camera.

        :return: A tuple containing the low and high bounds of the gain.
        :rtype: tuple[float, float]
        """
        return (
            float(self.pynit.gain_controller.get_low() * 64),
            float(self.pynit.gain_controller.get_high() * 64),
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
        self.pynit.gain_controller.set_range(low / 64.0, high / 64.0)

    def gain_autoset(self) -> tuple[float, float]:
        """
        Automatically sets the camera gain based on the current scene.

        :return: A tuple containing the low and high bounds of the calculated gain.
        :rtype: tuple[float, float]
        """
        low, high = self.pynit.gain_autoset()
        return float(low), float(high)

    @property
    def shade_correction(self) -> NDArray[float32]:
        """
        Retrieve the shade correction image.

        :return: The shade correction image.
        """
        data = self.pynit.get_shade_correction()
        if data is None:
            return zeros((self.width, self.height), dtype=float32)
        return data

    @shade_correction.setter
    def shade_correction(self, data: NDArray[float32]):
        """Set shade correction image."""
        self.pynit.set_shade_correction(data)

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
        return super().laplacian_std_dev

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

    @property
    def settings(self) -> Config:
        settings: Config = CameraInstrument.settings.__get__(self)
        settings["averaging"] = self.averaging
        settings["gain"] = list(self.gain)
        return settings

    @settings.setter
    def settings(self, data: Config):
        """Import and apply settings."""
        # Call the parent class settings setter
        CameraInstrument.settings.__set__(self, data)  # type: ignore[attr-defined]

        if "gain_autoset" in data:
            self.gain_autoset()
        if "reset_counter" in data:
            self.reset_counter()
            self.parameter_changed.emit("counter", self.counter)
        if "averaging_restart" in data:
            self.averaging_restart()
        if "averaging" in data and isinstance(averaging := data["averaging"], int):
            self.averaging = averaging
            self.parameter_changed.emit("averaging", averaging)
        if (
            "gain" in data
            and isinstance(gain := data["gain"], list)
            and len(gain) == 2
            and isinstance(gain[0], (int, float))
            and isinstance(gain[1], (int, float))
        ):
            self.gain = (float(gain[0]), float(gain[1]))
            self.parameter_changed.emit("gain", gain)
