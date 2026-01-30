import os
from typing import TYPE_CHECKING, Callable
import logging
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QWidget,
    QMessageBox,
    QDockWidget,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QSizePolicy,
    QMenu,
)
from PyQt6.QtGui import QGuiApplication, QFont, QAction, QIcon
from ..coloredbutton import ColoredPushButton
from ..keyboardbox import KeyboardBox, Direction
from ...instruments.stage import (
    MoveFor,
    StageInstrument,
    CNCRouter,
    SMC100,
    Corvus,
    Vector,
)
from ...instruments.joysticks import JoystickInstrument
from ...instruments.joysticksHID import JoystickHIDInstrument, HIDGAMEPAD
from ..marker import IdMarker
from ...utils.util import create_color_qicon


if TYPE_CHECKING:
    from ...laserstudio import LaserStudio


class PositioningOffsetDialog(QDialog):
    def __init__(self, stage: StageInstrument):
        super().__init__()
        self.stage = stage

        self.original_offset_origin = self.stage.offset_origin
        self.stage.offset_origin = [0.0] * self.stage.num_axis
        self.current_position = self.stage.position.data

        self.setWindowTitle("Set Positioning Offset")

        vbox = QVBoxLayout()
        self.setLayout(vbox)
        # Explanations of what to do in the dialog
        vbox.addWidget(
            QLabel(
                "Enter the coordinates of current position as you would like them to be, determining an offset to be applied to all positions."
            )
        )

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Actual Current Position:"))
        for p in self.current_position:
            label = QLabel(f"{p:+.02f}\xa0µm")
            hbox.addWidget(label)
        vbox.addLayout(hbox)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("After Positioning Offset:"))
        self.pos_entries: list[QDoubleSpinBox] = []
        for i in range(self.stage.num_axis):
            sb = QDoubleSpinBox()
            sb.setMinimum(-1000000.0)
            sb.setMaximum(1000000.0)
            sb.setDecimals(1)
            sb.setSuffix("\xa0µm")
            sb.valueChanged.connect(lambda: self._pos_entries_value_changed())
            self.pos_entries.append(sb)
            hbox.addWidget(sb)
        vbox.addLayout(hbox)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel("Positioning Offset:"))
        self.offset_entries: list[QDoubleSpinBox] = []
        for i in range(self.stage.num_axis):
            sb = QDoubleSpinBox()
            sb.setMinimum(-1000000.0)
            sb.setMaximum(1000000.0)
            sb.setDecimals(1)
            sb.setSuffix("\xa0µm")
            sb.setValue(self.original_offset_origin[i])
            sb.valueChanged.connect(lambda: self._offset_entries_value_changed())
            self.offset_entries.append(sb)
            hbox.addWidget(sb)
        vbox.addLayout(hbox)
        self._offset_entries_value_changed()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self.accept())
        buttons.rejected.connect(lambda: self.reject())
        vbox.addWidget(buttons)
        self.apply_offsets()

    def _pos_entries_value_changed(self):
        offsets = [
            self.pos_entries[i].value() - self.current_position[i]
            for i in range(len(self.current_position))
        ]
        for i in range(len(offsets)):
            sb = self.offset_entries[i]
            sb.blockSignals(True)
            sb.setValue(offsets[i])
            sb.blockSignals(False)
        self.apply_offsets()

    def _offset_entries_value_changed(self):
        for i in range(len(self.stage.offset_origin)):
            sb = self.pos_entries[i]
            sb.blockSignals(True)
            sb.setValue(self.current_position[i] + self.offset_entries[i].value())
            sb.blockSignals(False)
        self.apply_offsets()

    @property
    def new_offset_origin(self) -> list[float]:
        return [
            self.offset_entries[i].value() for i in range(len(self.stage.offset_origin))
        ]

    def apply_offsets(self):
        self.stage.offset_origin = self.new_offset_origin


class StageDockWidget(QDockWidget):
    def __init__(self, laser_studio: "LaserStudio"):
        assert laser_studio.instruments.stage is not None
        self.stage = laser_studio.instruments.stage
        self.viewer = laser_studio.viewer
        super().__init__("Stage Control", laser_studio)

        if self.stage.label:
            self.setWindowTitle(self.windowTitle() + " - " + self.stage.label)

        self.setObjectName("toolbar-stage")  # For settings save and restore
        group = laser_studio.viewer_buttons_group
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        w = QWidget()
        vbox = QVBoxLayout()
        w.setLayout(vbox)
        self.setWidget(w)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        vbox.addLayout(grid)

        # Activate stage-move mode
        w = ColoredPushButton(
            ":/icons/fontawesome-free/directions-solid.svg", parent=self
        )
        # Use '&&' to display '&' in text labels in Qt
        w.setText("Click && Move")
        w.setToolTip(
            "Move the stage to a new position, by clicking on the camera view."
        )
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        grid.addWidget(w, 0, 0)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.STAGE)

        hbox2 = QHBoxLayout()
        hbox2.setSpacing(2)
        grid.addLayout(hbox2, 0, 1)
        self.mem_point_selector = QPushButton(self)
        self.mem_point_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.mem_point_menu = QMenu(self)
        self.mem_point_selector.setMenu(self.mem_point_menu)
        self.mem_point_menu.aboutToShow.connect(self.refresh_mem_point_menu)
        hbox2.addWidget(self.mem_point_selector)

        origin = [0.0] * self.stage.num_axis
        origin_details = self._format_position_details("Origin", origin)
        self._select_mem_point("Origin", Vector(*origin), origin_details)

        hbox2.addWidget(w := QPushButton(self))
        w.setText("Go")
        w.setContentsMargins(0, 0, 0, 0)
        w.clicked.connect(self.go_to_mem_point_clicked)
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        hbox2.setStretch(0, 1)
        hbox2.setStretch(1, 0)
        w = QPushButton(self)
        w.setText("Home")
        w.clicked.connect(self.home)
        grid.addWidget(w, 1, 0)

        w = QPushButton(self)
        w.setText("Get Position")
        w.setToolTip("Get current stage position and copy in clipboard")

        def copy_position_to_clipboard():
            pos = self.stage.position.data
            logging.getLogger("laserstudio").info(f"{pos} (copied in clipboard)...")
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(str(pos))

        w.clicked.connect(copy_position_to_clipboard)
        grid.addWidget(w, 1, 1)

        hbox2 = QHBoxLayout()
        w = QPushButton(self)
        w.setText("Set Positioning Offset...")
        w.setToolTip("Set the positioning offset by entering coordinates values.")
        w.clicked.connect(self.set_positioning_offset)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hbox2.addWidget(w)
        w = ColoredPushButton(":/icons/origin-offset-drag.svg", parent=self)
        w.setToolTip(
            "Reposition an element visible on the camera where it should be, according to other elements (zones, markers...)."
        )
        w.setIconSize(QSize(24, 24))
        w.setCheckable(True)
        # make the button to stretch horizontally with the minimum size.
        w.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        hbox2.addWidget(w)
        group.addButton(w)
        group.setId(w, laser_studio.viewer.Mode.OFFSET_ORIGIN)
        grid.addLayout(hbox2, 2, 0)

        if isinstance(stage := self.stage.stage, CNCRouter):
            w = QPushButton(self)
            w.setText("Set Device Origin")
            w.setToolTip(
                "Set the current position as the origin of the device. This is permanent so will impact other projects."
            )
            w.clicked.connect(self.stage.set_device_origin)
            grid.addWidget(w, 3, 0)
            w = QPushButton(self)
            w.setText("Reset GRBL")
            w.clicked.connect(stage.reset_grbl)
            grid.addWidget(w, 3, 1)

        elif isinstance(stage := self.stage.stage, SMC100):
            w = QPushButton(self)
            w.setText("Reset")
            w.clicked.connect(stage.reset)
            grid.addWidget(w, 3, 0)

            w = QPushButton(self)
            w.setText("Stop")
            w.clicked.connect(stage.stop)
            grid.addWidget(w, 3, 1)

        elif isinstance(stage := self.stage.stage, Corvus):
            w = QPushButton(self)
            w.setText("Set Device Origin")
            w.setToolTip(
                "Set the current position as the origin of the device. This is permanent so will impact other projects."
            )
            w.clicked.connect(self.stage.set_device_origin)
            grid.addWidget(w, 3, 0)
            w = QPushButton(self)
            w.setText("Enable Joystick")
            w.clicked.connect(stage.enable_joystick)
            grid.addWidget(w, 3, 1)

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        vbox.addLayout(hbox)
        # Move for
        self.move_for_selector = box = QComboBox()
        box.addItem("Camera's center", userData=MoveFor(MoveFor.Type.CAMERA_CENTER))
        for i in range(len(laser_studio.instruments.lasers)):
            box.addItem(f"Laser {i + 1}", userData=MoveFor(MoveFor.Type.LASER, i))
        for i in range(len(laser_studio.instruments.probes)):
            box.addItem(f"Probe {i + 1}", userData=MoveFor(MoveFor.Type.PROBE, i))
        box.activated.connect(self.move_for_selection)
        hbox.addWidget(QLabel("Focused item:"))
        hbox.addWidget(box)
        box.setToolTip(
            "The item to focus on\nThe stage will move in order to place the focused item at the desired position."
        )
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Keyboard box
        self.keyboardbox = w = KeyboardBox(self.stage)
        vbox.addWidget(w)

        # Joysticks
        self.joystick: None | JoystickInstrument | JoystickHIDInstrument = None
        input_dir = os.path.join(os.sep, "dev", "input")
        if os.path.exists(input_dir):
            joysticks = [
                fn
                for fn in os.listdir(os.path.join(os.sep, "dev", "input"))
                if fn.startswith("js")
            ]
        else:
            joysticks = ["JoyConL", "JoyConR", "PS4"]

        if len(joysticks):
            hbox = QHBoxLayout()
            w = QComboBox()
            w.addItem("Disabled")
            for joystick in joysticks:
                w.addItem(joystick)
            w.currentTextChanged.connect(self.activate_joystick)
            hbox.addWidget(QLabel("Joystick:"))
            hbox.addWidget(w)
            vbox.addLayout(hbox)

        # Position tracking label
        self.position = QLabel("")
        self.position.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position.setStyleSheet("padding-left: 10px;padding-right: 10px")
        self.stage.position_changed.connect(self.update_position)
        self.position.setToolTip("The stage position")
        vbox.addWidget(self.position)

        vbox.addStretch(1000)

    def go_to_mem_point_clicked(self):
        """
        Called when the go to memory point button is clicked.
        """
        data = getattr(self, "_mem_point_selection", None)
        if isinstance(data, IdMarker):
            data = self._vector_from_marker(data)
        if not isinstance(data, Vector):
            logging.getLogger("laserstudio").error(f"Invalid memory point: {data}")
            return
        if len(data.data) != self.stage.num_axis:
            logging.getLogger("laserstudio").error(
                f"Invalid memory point: {data}. Dimension of point {len(data.data)} is different from stage's number of axes {self.stage.num_axis}). Please correct your configuration file."
            )
            return
        self.stage.move_to(data, wait=True)

    def _format_position_details(self, label: str, coords: list[float]) -> str:
        coords_text = ", ".join([f"{c:+.02f}" + "\xa0µm" for c in coords])
        return f"{label}: [{coords_text}]"

    def _marker_menu_label(self, marker: IdMarker) -> str:
        if marker.label:
            return f"{marker.label} (#{marker.id})"
        return f"Marker {marker.id}"

    def _select_mem_point(
        self,
        label: str,
        data: Vector | IdMarker,
        tooltip: str | None = None,
        icon: QIcon | None = None,
    ) -> None:
        self._mem_point_selection = data
        self.mem_point_selector.setText(label)
        if icon is not None:
            self.mem_point_selector.setIcon(icon)
        if tooltip is not None:
            self.mem_point_selector.setToolTip(tooltip)

    def _make_mem_point_handler(
        self,
        label: str,
        data: Vector | IdMarker,
        tooltip: str,
        icon: QIcon | None = None,
    ) -> Callable[[bool], None]:
        def handler(_checked: bool = False) -> None:
            self._select_mem_point(label, data, tooltip, icon)

        return handler

    def _vector_from_marker(self, marker: IdMarker) -> Vector:
        pos = marker.pos()
        coords = list(self.stage.position.data)
        if len(coords) >= 1:
            coords[0] = pos.x()
        if len(coords) >= 2:
            coords[1] = pos.y()
        return Vector(*coords)

    def refresh_mem_point_menu(self) -> None:
        self.mem_point_menu.clear()
        origin = [0.0] * self.stage.num_axis
        origin_details = self._format_position_details("Origin", origin)
        origin_action = QAction("Origin", self.mem_point_menu)
        origin_action.setToolTip(origin_details)
        origin_action.triggered.connect(
            self._make_mem_point_handler("Origin", Vector(*origin), origin_details)
        )
        self.mem_point_menu.addAction(origin_action)

        memory_menu = QMenu("Memory points", self.mem_point_menu)
        self.mem_point_menu.addMenu(memory_menu)
        if self.stage.mem_points:
            for i, mem_point in enumerate(self.stage.mem_points):
                short_label = f"M{i}"
                details = self._format_position_details(
                    short_label, list(mem_point.data)
                )
                action = QAction(details, memory_menu)
                action.triggered.connect(
                    self._make_mem_point_handler(short_label, mem_point, details)
                )
                memory_menu.addAction(action)
        else:
            no_memory = QAction("No memory points", memory_menu)
            no_memory.setEnabled(False)
            memory_menu.addAction(no_memory)

        markers_menu = QMenu("Markers", self.mem_point_menu)
        self.mem_point_menu.addMenu(markers_menu)
        markers_by_label_by_color = self.viewer.markers_by_label_by_color

        labels = sorted(markers_by_label_by_color.keys(), key=lambda l: l or "")
        for label in labels:
            markers_by_color = markers_by_label_by_color[label]
            label_menu = QMenu(label or "Unlabeled", markers_menu)
            markers_menu.addMenu(label_menu)
            if not markers_by_color:
                no_markers = QAction("No markers", label_menu)
                no_markers.setEnabled(False)
                label_menu.addAction(no_markers)
                continue

            for color in sorted(markers_by_color.keys()):
                markers = markers_by_color[color]
                color_menu = QMenu(
                    f"{len(markers)} marker" + ("" if len(markers) == 1 else "s"),
                    label_menu,
                )
                label_menu.addMenu(color_menu)
                color_icon = None
                for marker in markers:
                    pos = marker.pos()
                    details = self._format_position_details(
                        f"#{marker.id}", [pos.x(), pos.y()]
                    )
                    action = QAction(details, color_menu)
                    color_icon = color_icon or create_color_qicon(marker.qcolor)
                    action.setIcon(color_icon)
                    action.triggered.connect(
                        self._make_mem_point_handler(
                            f"#{marker.id}", marker, details, color_icon
                        )
                    )
                    color_menu.addAction(action)
                if color_icon is not None:
                    color_menu.setIcon(color_icon)

    def update_position(self, position: Vector):
        self.position.setText(", ".join([f"{c:+.02f}\xa0µm" for c in position.data]))
        f = QFont("monospace", 10)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.position.setFont(f)
        self.position.setMinimumWidth(self.position.sizeHint().width())

    def home(self):
        """
        Called when the home button is clicked.
        """
        # Request a confirmation from the user
        if QMessageBox.StandardButton.Apply == QMessageBox.warning(
            None,
            "Homing",
            "Caution: Homing can make some collision and break your setup."
            " Make sure that your setup is ready to perform this operation.",
            buttons=QMessageBox.StandardButton.Abort | QMessageBox.StandardButton.Apply,
            defaultButton=QMessageBox.StandardButton.Abort,
        ):
            self.stage.stage.home(wait=True)

    def move_for_selection(self, index: int):
        """
        Called when the move for selection is changed.

        :param index: The index of the selected item.
        """
        move_for = self.move_for_selector.itemData(index, Qt.ItemDataRole.UserRole)
        if not isinstance(move_for, MoveFor):
            return
        self.stage.move_for = move_for

    def activate_joystick(self, name: str):
        """
        Creates a JoystickInstrument associated with the given device name

        :param name: the name of the device associated to the JoystickInstrument (in `/dev/input/`),
            starting by `js`.
        """
        if self.joystick is not None:
            self.joystick.stop()
            self.joystick = None
        if name.startswith("js"):
            self.joystick = JoystickInstrument(
                os.path.join(os.sep, "dev", "input", name)
            )
        if name == "JoyConR":
            self.joystick = JoystickHIDInstrument(HIDGAMEPAD.JOYCON_R)
        if name == "JoyConL":
            self.joystick = JoystickHIDInstrument(HIDGAMEPAD.JOYCON_L)
        if name == "PS4":
            self.joystick = JoystickHIDInstrument(HIDGAMEPAD.PS4)
        if self.joystick is not None:
            self.joystick.axis_changed.connect(self.joystick_axis)
            self.joystick.button_pressed.connect(self.joystick_button)

    def joystick_button(self, button: int, pressed: bool):
        """
        Called to handle the Joystick's pressure of a button

        :param button: the button's number
        :param pressed: True if the button has been pressed, False if it has been released
        """
        if not pressed:
            return
        axe = button // 2
        if axe == 2:
            coefficient = (button % 2) * 2.0 - 1.0
            self.joystick_axis(axe, coefficient)
        elif axe == 0 and self.keyboardbox.displacement_z_spinbox is not None:
            # First pair of number of buttons (0 and 1) is for changing the step of Z
            self.keyboardbox.displacement_z_spinbox.setValue(
                self.keyboardbox.displacement_z * (2.0 if button % 2 else 0.5)
            )
        elif axe == 1 and self.keyboardbox.displacement_xy_spinbox is not None:
            # Second pair of number of buttons (7 and 8) is for changing the step of XY
            self.keyboardbox.displacement_xy_spinbox.setValue(
                self.keyboardbox.displacement_xy * (2.0 if button % 2 else 0.5)
            )

    def joystick_axis(self, axe: int, coefficient: float):
        """
        Called to handle the Joystick's change of value of an axe

        :param axe: the axe of the joystick which has changed
        :param coefficient: The new value of the axe (from 0 to 1)
        """
        if axe >= self.stage.stage.num_axis:
            return
        if abs(coefficient) < 0.001:
            return

        if axe == 0:
            self.keyboardbox.move_stage(
                direction=Direction.right if coefficient > 0 else Direction.left
            )
        elif axe == 1:
            self.keyboardbox.move_stage(
                direction=Direction.up if coefficient > 0 else Direction.down
            )
        elif axe == 2:
            self.keyboardbox.move_stage(
                direction=Direction.zup if coefficient > 0 else Direction.zdown
            )

    def set_positioning_offset(self):
        """
        Called when the set positioning offset button is clicked.
        """
        dialog = PositioningOffsetDialog(self.stage)

        result = dialog.exec()
        logging.getLogger("laserstudio").debug(f"Dialog returned {result}...")
        if result == QDialog.DialogCode.Accepted:
            self.stage.offset_origin = dialog.new_offset_origin
        else:
            self.stage.offset_origin = dialog.original_offset_origin
