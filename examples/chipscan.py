from lsapi import LSAPI
from time import sleep
import quicklog
import datetime
import os
api = LSAPI()
# Full chip
n_steps = 15, 15, 1
bottom_left = [-11_540.58,-26_480.31,-14_594.67]
top_right = [-9_361.81,-24_803.59,-14_583.17]
step = [(top_right[i] - bottom_left[i]) / n_steps[i] for i in range(len(top_right))]
ir_settings = {
    "raptor": {
        "alc_enabled": True,
        "black_level": 0,
        "fan_enabled": True,
        "high_gain": False,
        "image_averaging": 1,
        "objective": 20,
        "tec_enabled": True,
        "temperature_setpoint": -15.0,
        "white_level": 1,
        "windowed_averaging": True,
    },
    "lms": {"intensity": 0.7, "light": True, "open": False},
}

date_str = datetime.datetime.now().strftime("%Y%m%d%H%M")
imagespath = os.path.abspath(os.path.join(os.curdir, "images", date_str))
os.makedirs(imagespath, exist_ok=True)

def take_images(name):
    name_ir = os.path.join(imagespath, "ir_image" + name)
    api.set_instrument_settings("raptor", ir_settings["raptor"])
    sleep(1)
    api.set_instrument_settings("lms", ir_settings["lms"])
    # Put a large sleep to let the ALC to stabilize
    sleep(5)
    # unset reference to be sure
    api.reference_image(unset=True)
    # wait for accumulated images to reach the desired number
    api.averaging(reset=True)
    while api.averaging() != ir_settings["raptor"]["image_averaging"]:
        sleep(0.1)
    sleep(1)
    api.magicfocus({})
    while not api.magicfocus()["finished"]:
        sleep(5)
    sleep(1)
    pos = api.position()["pos"]
    rec["automagicfocus_pos"] = str(pos)

    # store the image(s)
    api.accumulated_image(path=name_ir + ".npy")
    api.camera(path=name_ir + ".png")

z = api.position()["pos"][2]

log = quicklog.Log("photoemission.quicklog")

begin_x = 0
end_x = n_steps[0] + 1

for x_step in range(begin_x, min(end_x, n_steps[0] + 1)):
    # let's first move vertically
    # we have to deal with backlash so we first take a step back down in y
    position = api.go_to_position(
        [bottom_left[0] + x_step * step[0], bottom_left[1] - 50, z]
    )

    for y_step in range(0, n_steps[1] + 1):
        rec = quicklog.new_record()
        rec["pos"] = str(position)
        rec["step"] = step

        # debug prints
        print(f"{x_step=}, {y_step=}")

        # go to the desired position
        api.go_to_position(
            [bottom_left[0] + x_step * step[0], bottom_left[1] + y_step * step[1], z]
        )
        sleep(1)

        # take images for both firmwares
        take_images(
            name=f"_{x_step}_{y_step}_",
        )
        log.append(rec)
