#!/usr/bin/python3
from scan_file import ScanFile, get_filename
import numpy as np
from PIL import Image
from enum import Enum


def get_image(
    col: int, row: int, prefix: str = "scan", ext: str = ".png", dir: str = "tmp"
):
    """
    Load a tile.
    :param col: Tile col.
    :param row: Tile row.
    """
    return Image.open(get_filename(col, row, prefix, ext, dir))


class StitchPhase(Enum):
    SHADING = 1
    STITCHING = 2
    SAVING = 3
    DONE = 4


def progress_callback(phase, done, total):
    print(phase, done, total)


def stitch(scan: ScanFile, progress_callback=progress_callback, shade_correction=True):
    """
    Stitch images.
    :scan: ScanFile object with the scan properties.
    :param progress_callback: A function called during stitching process.
        Indicates current step and progress in current state.
    """
    assert scan.num_x is not None
    assert scan.num_y is not None
    assert scan.img_width is not None
    assert scan.img_height is not None
    assert scan.img_overlap is not None
    assert scan.num_images is not None

    correction = None
    if shade_correction:
        progress_callback(StitchPhase.SHADING, 0, scan.num_images)
        # Calculate median image for shading correction.
        all_images = []
        for y in range(scan.num_y):
            for x in range(scan.num_x):
                progress_callback(
                    StitchPhase.SHADING, y * scan.num_y + x, scan.num_images
                )
                all_images.append(np.array(get_image(x, y, prefix=scan.file_prefix)))
        shade = np.median(all_images, axis=0)
        # np.median returns an array with np.float64 datatype, even if input
        # arrays are uint8, so we need to cast back to uint8 for PIL.Image.
        filename = get_filename(prefix="shade")
        Image.fromarray(shade.clip(0, 255).astype("uint8")).save(filename)
        del all_images

        # Calculate mean pixel value in the shade image (we want to center the
        # data arround zero to make a correction image)
        mean_pixel = np.mean(shade, axis=(0, 1))
        # Calculate correction image
        correction = shade - mean_pixel

    # Stitch the image
    width = int(scan.num_x * scan.img_width - (scan.img_overlap * (scan.num_x - 1)))
    height = int(scan.num_y * scan.img_height - (scan.img_overlap * (scan.num_y - 1)))

    stitched = Image.new("RGB", (width, height))

    for y in range(scan.num_y):
        for x in range(scan.num_x):
            progress_callback(
                StitchPhase.STITCHING, y * scan.num_y + x, scan.num_images
            )
            im = np.array(get_image(x, y, scan.file_prefix))
            if shade_correction and correction is not None:
                im = im - correction
            im = Image.fromarray(im.clip(0, 255).astype("uint8"))
            filename = get_filename(x, y, scan.file_prefix, suffix="c")
            im.save(filename)
            paste_x = int(x * (scan.img_width - scan.img_overlap))
            paste_y = int(
                height - scan.img_height - (y * (scan.img_height - scan.img_overlap))
            )
            stitched.paste(im, (paste_x, paste_y))

    # Save result image. This may be very long depending on image size.
    progress_callback(StitchPhase.SAVING, 0, 1)
    filename = get_filename(prefix="stitched")
    stitched.save(filename)
    progress_callback(StitchPhase.DONE, 1, 1)


if __name__ == "__main__":
    scan_file = ScanFile()
    scan_file.load(get_filename(prefix="scan", ext=".yaml"))
    stitch(scan_file, progress_callback, shade_correction=True)
