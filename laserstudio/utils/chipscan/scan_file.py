import yaml
import os
from typing import Optional


def get_filename(
    col: Optional[int] = None,
    row: Optional[int] = None,
    prefix: str = "scan",
    ext: str = ".png",
    dir: str = "tmp",
    suffix: str = "",
):
    """
    :param col: Tile col.
    :param row: Tile row.
    """
    return (
        os.path.join(
            dir,
            "_".join(
                ([prefix] if prefix else [])
                + (
                    [f"{col:03d}", f"{row:03d}"]
                    if col is not None and row is not None
                    else []
                )
                + ([suffix] if suffix else [])
            ),
        )
        + ext
    )


class ScanFile:
    """
    Store properties of a chip-scan and provide methods to save/load to/from
    XML files.

    Scan files are created when scanning a chip. They stand in the same
    directory as the images.
    """

    def __init__(self):
        """
        Initialize the ScanFile object.
        """
        self.num_x = 0
        self.num_y = 0
        self.img_width = 0.0
        self.img_height = 0.0
        self.img_overlap = 0.0
        self.file_prefix: str = ""

    def save(self, path: str):
        """
        Save data to an YAML file.

        :param path: Path to the YAML file.
        """
        with open(path, "w") as out_file:
            yaml.dump(
                {
                    "scan": {
                        "num-x": self.num_x,
                        "num-y": self.num_y,
                        "img-width": self.img_width,
                        "img-height": self.img_height,
                        "img-overlap": self.img_overlap,
                        "file-prefix": self.file_prefix,
                    }
                },
                out_file,
            )

    def load(self, path: str):
        """
        Load data from an YAML file.

        :path: Path to the YAML file.
        """
        with open(path, "r") as in_file:
            data = yaml.safe_load(in_file)
            scan_data = data.get("scan", {})
            self.num_x = scan_data.get("num-x", 0)
            self.num_y = scan_data.get("num-y", 0)
            self.img_width = scan_data.get("img-width", 0.0)
            self.img_height = scan_data.get("img-height", 0.0)
            self.img_overlap = scan_data.get("img-overlap", 0.0)
            self.file_prefix = scan_data.get("file-prefix", "")

    @property
    def num_images(self):
        """:return: Number of tile images."""
        return self.num_x * self.num_y
