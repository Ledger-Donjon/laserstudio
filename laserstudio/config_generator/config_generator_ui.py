#!/usr/bin/python3
from PyQt6.QtCore import Qt, QKeyCombination, QSettings, QRegularExpression
from PyQt6.QtGui import (
    QColor,
    QShortcut,
    QKeySequence,
    QRegularExpressionValidator,
    QIntValidator,
    QDoubleValidator,
)
from PyQt6.QtWidgets import QMainWindow, QButtonGroup, QFileDialog
from typing import Optional, Any
from PyQt6.QtWidgets import (
    QWizardPage,
    QWizard,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QLabel,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QRadioButton,
    QFormLayout,
    QTabWidget,
    QErrorMessage,
    QLineEdit,
    QGroupBox,
)
import sys
import os
import json
import yaml

try:
    from .ref_resolve import set_base_url, resolve_references
    from .config_generator import ConfigGenerator, validate, ValidationError
except ImportError:
    from ref_resolve import set_base_url, resolve_references
    from config_generator import ConfigGenerator, validate, ValidationError

from PyQt6.QtWidgets import QApplication


class AnyOfWidget(QWidget):
    def __init__(self, schema, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.cb = QCheckBox()
        self.schema_widget = SchemaWidget(schema)
        self.schema_widget.setEnabled(False)
        self.cb.checkStateChanged.connect(
            lambda state: setattr(self, "selected", state == Qt.CheckState.Checked)
        )

    @property
    def selected(self):
        return self.cb.isChecked()

    @selected.setter
    def selected(self, value: bool):
        self.cb.setChecked(value)
        self.schema_widget.setEnabled(value)


class ConfigGeneratorWizard(QWizard):
    def __init__(self, schema: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration File Generator")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.schema = schema
        self.config_generation_page = ConfigPresentationPage(self, schema)
        self.addPage(self.config_generation_page)
        self.addPage(ConfigResultPage(self))


class KeyLabel(QPushButton):
    def __init__(self, text: str, color: Optional[str], parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("font-weight: bold; font-size: 20px;")
        if color is not None:
            self.setStyleSheet(f"color: {color}")
        self.setChecked(True)
        self.setCheckable(True)


class SchemaWidget(QGroupBox):
    def __init__(
        self, schema: dict, key: str = "", position: Optional[int] = None, parent=None
    ):
        super().__init__(parent)

        # schema_str = json.dumps(schema, indent=4)
        # self.setToolTip(schema.get("description"))

        self._children = list[SchemaWidget]()
        self.label_widget = None
        self.value_widget = None
        self.key = key

        self.schema = schema
        self._layout = QVBoxLayout()

        self.setLayout(self._layout)

        # Identify which type of element we are dealing with
        element_type = schema.get("type")

        # If the schema does not have a 'type' key, assume it is an object
        if element_type is None:
            element_type = "object"
        if element_type == "array":
            name = schema.get("items", {}).get("title")
            if name is not None:
                name += "s"
        else:
            name = schema.get("title")

        name = name or key
        if position is not None:
            name += f" {position + 1}"

        if "const" in schema:
            self.value_widget = w = QLabel(str(schema["const"]))
            color = "black"
        elif element_type == "integer":
            self.value_widget = w = QSpinBox()
            color = "orange"
            w.setMinimum(schema.get("minimum", -1000000))
            w.setMaximum(schema.get("maximum", 1000000))
            if "multipleOf" in schema:
                w.setSingleStep(schema["multipleOf"])
            w.setSuffix(schema.get("suffix"))
            if "default" in schema:
                w.setValue(schema["default"])

        elif element_type == "number":
            self.value_widget = w = QDoubleSpinBox()
            w.setMinimum(schema.get("minimum", -1000000.0))
            w.setMaximum(schema.get("maximum", 1000000.0))
            if "multipleOf" in schema:
                w.setSingleStep(schema["multipleOf"])
            color = "purple"
            w.setSuffix(schema.get("suffix"))
            if "default" in schema:
                w.setValue(schema["default"])
        elif element_type == "boolean":
            self.value_widget = w = QCheckBox()
            color = "green"
        elif element_type == "string":
            self.value_widget = w = QLineEdit()
            color = "red"
            if "pattern" in schema:
                w.setValidator(
                    QRegularExpressionValidator(QRegularExpression(schema["pattern"]))
                )
            if "default" in schema:
                w.setText(schema["default"])
            if "examples" in schema:
                w.setPlaceholderText(
                    " or ".join(str(example) for example in schema["examples"])
                )

        elif element_type == "array":
            w = QWidget()
            vbox = QVBoxLayout()
            w.setLayout(vbox)
            hbox = QHBoxLayout()
            vbox.addLayout(hbox)
            self.plus_button = QPushButton("+")
            hbox.addWidget(self.plus_button)
            minItems = schema.get("minItems", 0)
            maxItems = schema.get("maxItems", None)

            def add_child():
                self._children.append(
                    c := SchemaWidget(schema["items"], "", position=len(self._children))
                )
                vbox.addWidget(c.value_widget or c)
                if maxItems is not None:
                    self.plus_button.setEnabled(len(self._children) < maxItems)
                self.minus_button.setEnabled(len(self._children) > minItems)

            self.plus_button.clicked.connect(add_child)

            self.minus_button = QPushButton("-")
            self.minus_button.setEnabled(False)
            hbox.addWidget(self.minus_button)

            def remove_child():
                if not self._children:
                    return
                c = self._children.pop()
                vbox.removeWidget(c.value_widget or c)
                c.deleteLater()
                if maxItems is not None:
                    self.plus_button.setEnabled(len(self._children) < maxItems)
                self.minus_button.setEnabled(len(self._children) > minItems)

            self.minus_button.clicked.connect(remove_child)
            color = "blue"
            self._layout.addWidget(w)

            for _ in range(minItems):
                add_child()

        else:
            # self.setStyleSheet("background-color: red")
            self.setToolTip(None)
            color = None

        self.setCheckable(True)

        if name or key:
            self.label_widget = KeyLabel(name or key, color)
            self.label_widget.setToolTip(schema.get("description"))
            self.setTitle(name or key)

        self.add_properties_widgets()

        self.oneOf_tabWidget = None
        if one_of := schema.get("oneOf"):
            self.oneOf_tabWidget = QTabWidget()
            for i, subschema in enumerate(one_of):
                self.oneOf_tabWidget.addTab(
                    SchemaWidget(subschema, ""),
                    subschema.get("description", f"Option {i+1}"),
                )
            self._layout.addWidget(self.oneOf_tabWidget)

        self.anyOf_widgets: list[AnyOfWidget] = []
        if any_of := schema.get("anyOf"):
            anyOf_widget = QWidget()
            anyOf_form = QFormLayout()
            anyOf_widget.setLayout(anyOf_form)
            self._layout.addWidget(anyOf_widget)

            for subschema in any_of:
                widget = AnyOfWidget(subschema)
                anyOf_form.addRow(widget.cb, widget.schema_widget)
                self.anyOf_widgets.append(widget)
            self.anyOf_widgets[0].selected = True

        if self.label_widget and self.value_widget:
            self.label_widget.clicked.connect(self.value_widget.setEnabled)

    @property
    def value(self):
        if type(self.value_widget) is QCheckBox:
            return self.value_widget.isChecked()
        elif type(self.value_widget) is QLineEdit:
            return self.value_widget.text()
        elif type(self.value_widget) is QSpinBox:
            return self.value_widget.value()
        elif type(self.value_widget) is QDoubleSpinBox:
            return self.value_widget.value()
        elif type(self.value_widget) is QLabel:
            return self.value_widget.text()
        elif self.schema.get("type") == "array":
            return [child.json() for child in self._children]
        else:
            return None

    def add_properties_widgets(self):
        properties_widget = QWidget()
        properties_form = QFormLayout()
        properties_widget.setLayout(properties_form)
        self._layout.addWidget(properties_widget)
        for key, subschema in self.schema.get("properties", {}).items():
            child = SchemaWidget(subschema, key)
            if child.value_widget is not None:
                properties_form.addRow(child.label_widget, child.value_widget)
            else:
                self._layout.addWidget(child)
            self._children.append(child)

    @property
    def selected(self):
        return self.isChecked()

    def json(self):
        if self.schema.get("type") == "array":
            return [child.json() for child in self._children if child.selected]

        if (v := self.value) is not None:
            return v

        result = {}
        for child in self._children:
            if not child.selected:
                continue
            result[child.key] = child.json()

        if self.oneOf_tabWidget:
            current_widget = self.oneOf_tabWidget.currentWidget()
            assert isinstance(current_widget, SchemaWidget)
            json_value = current_widget.json()
            assert type(json_value) is dict
            result.update(json_value)

        for current_widget in self.anyOf_widgets:
            if not current_widget.selected:
                continue
            json_value = current_widget.schema_widget.json()
            assert type(json_value) is dict
            result.update(json_value)

        return result

    def validate(self):
        try:
            validate(self.json(), self.schema)
            return True
        except ValidationError as e:
            error = QErrorMessage()
            error.showMessage(f"Error on validation of {e.json_path[2:]}: {e.message}")

            return False


class ConfigResultPage(QWizardPage):
    def __init__(self, parent: "ConfigGeneratorWizard"):
        super().__init__(parent)
        self.setTitle("Config Result")
        self.setSubTitle("This is the generated config")

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.result_label = QLabel()
        layout.addWidget(self.result_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

    def initializePage(self):
        wiz = self.wizard()
        assert isinstance(wiz, ConfigGeneratorWizard)
        self.config = wiz.config_generation_page.schema_widget.json()
        self.result_label.setText(yaml.dump(self.config, indent=2))

    def validatePage(self) -> bool:
        try:
            wizard = self.wizard()
            assert isinstance(wizard, ConfigGeneratorWizard)
            validate(self.config, wizard.schema)
            print("Validation successful", self.config)
            return True
        except ValidationError as e:
            self.setSubTitle(
                f"Generated JSON is <strong>invalid</strong> for '{'.'.join([str(k) for k in e.path])}'\n"
                + e.message
            )
            return False


class ConfigPresentationPage(QWizardPage):
    def __init__(self, parent: "ConfigGeneratorWizard", schema):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.schema_widget = SchemaWidget(schema)
        scroll.setWidget(self.schema_widget)
        layout.addWidget(scroll)

    def validatePage(self) -> bool:
        return self.schema_widget.validate()


if __name__ == "__main__":
    config_generator = ConfigGenerator()
    sys.argv.append("-L")
    config_generator.get_flags()
    set_base_url(config_generator.base_url)
    # Load all schemas
    config_generator.load_schema()
    SCHEMA = config_generator.schema
    assert type(SCHEMA) is dict

    app = QApplication(sys.argv)
    wizard = ConfigGeneratorWizard(config_generator.schema)
    wizard.show()
    sys.exit(app.exec())
