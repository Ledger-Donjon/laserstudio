#!/usr/bin/python3
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import QButtonGroup
from typing import Optional, Union
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
    QFormLayout,
    QTabWidget,
    QErrorMessage,
    QLineEdit,
    QGroupBox,
    QAbstractButton,
    QStackedWidget,
    QRadioButton,
)
import sys
import yaml

try:
    from .ref_resolve import set_base_url
    from .config_generator import ConfigGenerator, validate, ValidationError
    from ..utils.colors import LedgerPalette, LedgerStyle
except ImportError:
    from laserstudio.config_generator.ref_resolve import set_base_url
    from laserstudio.config_generator.config_generator import (
        ConfigGenerator,
        validate,
        ValidationError,
    )
    from laserstudio.utils.colors import LedgerPalette, LedgerStyle

from PyQt6.QtWidgets import QApplication


class ConfigGeneratorWizard(QWizard):
    def __init__(self, schema: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration File Generator")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Initiate the presentation/introduction page
        self.addPage(ConfigGeneratorIntroductionPage(self))

        self.schema = schema
        # To be more readable, we will create a page for each top-property of the schema
        self.config_generation_pages = list[ConfigPresentationPage]()
        top_properties = schema.get("properties", {})
        for key, subschema in top_properties.items():
            self.config_generation_pages.append(
                ConfigPresentationPage(self, key, subschema)
            )
        [self.addPage(p) for p in self.config_generation_pages]

        # Add the result page
        self.config_result_page = ConfigResultPage(self)
        self.addPage(self.config_result_page)


class AnyOf:
    """
    The AnyOf widget is compound on the given title of the option to select (via the checkbox) and the widget permitting to enter the value.
    """

    def __init__(self, schema, required_keys: list[str] = []) -> None:
        self.cb = QCheckBox(schema.get("title"))
        self.schema_widget = SchemaWidget(
            schema, make_flat=True, required_keys=required_keys
        )
        self.schema_widget.setEnabled(False)
        self.cb.checkStateChanged.connect(
            lambda state: setattr(self, "selected", state == Qt.CheckState.Checked)
        )

    @property
    def selected(self):
        """Indication to know if the element is selected, and thus must be included in the Configuration File"""
        return self.cb.isChecked()

    @selected.setter
    def selected(self, value: bool):
        self.cb.setChecked(value)
        self.schema_widget.setEnabled(value)


class KeyLabel(QWidget):
    def __init__(self, text: str, required=False):
        """
        The KeyLabel is the widget to display the property of an object.
        It includes label for the property name.
        It includes a checkbox for optional fields, that can be unchecked not to include it in the Configuration File.

        :param text: The name of the property, which is the 'key' in the schema.
        :param required: Indicates if the property is required in the schema or not, defaults to False.
            It the property is optional, a checkbox will be visible to permit the user not to include
            it in the Configuration File.
        """
        super().__init__()
        self.setLayout(hbox := QHBoxLayout())
        self.cb = QCheckBox()
        hbox.addWidget(self.cb)
        self.label_container = QWidget()
        hbox.addWidget(self.label_container)
        self.label_container_layout = QHBoxLayout()
        self.label_container_layout.setContentsMargins(0, 0, 0, 0)
        self.label_container_layout.setSpacing(5)
        self.label_container.setLayout(self.label_container_layout)
        self.label = QLabel(text)
        self.label_container_layout.addWidget(self.label)
        hbox.setContentsMargins(0, 0, 0, 0)
        # By default, we want to include the field in the Configuration File.
        self.cb.setChecked(True)
        self.cb.setToolTip(
            "Check this box to include this field in the Configuration File"
        )
        self.cb.setDisabled(required)
        self.cb.setHidden(required)
        # To make the widget to have the same size when the checkbox is hidden
        pol = self.cb.sizePolicy()
        pol.setRetainSizeWhenHidden(True)
        self.cb.setSizePolicy(pol)


class SchemaWidget(QGroupBox):
    """
    The SchemaWidget is the representation of an element in the schema.

    If the element is an object, it includes :
        - a list of SchemaWidget objects for its properties.
    If the element's schema includes a "oneOf" it includes a QStackedWidget to permit the selection of the different options.
    If the element's schema includes a "anyOf" it includes a QFormLayout with checkboxes to permit the selection of one (or more) different options.

    If the element is a simple value/property to configure (integer, string, boolean, etc.), it includes
        - A KeyLabel (checkbox + title of key)
        - A QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox or QLabel which is called a "value_widget" to permit the user to enter/see the value.

    If the element is an array of simple values/properties, there is also a +/- button to add/remove elements in the array.
    """

    def __init__(
        self,
        schema: dict,
        key: str = "",
        position: Optional[int] = None,
        parent=None,
        required_keys: list[str] = [],
        make_flat=False,
    ):
        super().__init__(parent)

        self._children = list[SchemaWidget]()
        self.keylabel_widget = None
        self.value_widget = None
        self.key = key
        self.hbox_plus_minus = None

        self.schema = schema
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(20)

        self.setLayout(self._layout)

        # Identify which type of element we are dealing with
        # If the schema does not have a 'type' key, treat it as an object
        self.element_type = schema.get("type", "object")

        if self.element_type == "array":
            name = schema.get("items", {}).get("title")
            if name is not None:
                name += "s"
        else:
            name = schema.get("title")

        name = name or key
        if position is not None:
            name += f" {position + 1}"

        self.required_keys = required_keys + schema.get("required", [])

        if make_flat:
            self.setChecked(True)
            self.setCheckable(False)
            self.setFlat(True)
            # self.setTitle(None)
        else:
            self.setCheckable(key not in required_keys)
            self.setTitle(name or key)

        self.name = name

        self.value_widget = self.create_value_widget()
        self.keylabel_widget = self.create_keylabel_widget()
        self.add_properties_widgets()
        self.add_anyOf_widget()
        self.add_oneOf_widget()

        self._layout.addStretch()

        if self.value_widget is not None and type(self.keylabel_widget) is KeyLabel:
            self.keylabel_widget.cb.clicked.connect(self.enable_property)
            self.enable_property(schema.get("included", key in required_keys))
            self.value_widget.setToolTip(self.keylabel_widget.toolTip())
        else:
            self.enable_property(True)

    def enable_property(self, state: bool = True):
        """
        Change the appearance of the SchemaWidget (KeyLabel and Value_Widget) when it is configuring an optional property.

        :param state: The selection state to be changed, defaults to True
        """
        if self.value_widget is not None:
            self.value_widget.setEnabled(state)
        if self.keylabel_widget is not None:
            self.keylabel_widget.label_container.setEnabled(state)
            self.keylabel_widget.cb.setChecked(state)

    def create_keylabel_widget(self):
        """
        Create a keylabel when the current element has a value of key.
        In case of the element is an object, the KeyLabel may not be included in the views, but it should still exist.

        :return: The KeyLabel of the element being configured.
        """
        if not self.key:
            # Having self.key to "" or None means that we do not want to have any key label
            return None

        name_or_key = self.name or self.key
        self.keylabel_widget = KeyLabel(
            name_or_key, required=self.key in self.required_keys
        )
        tooltip = self.schema.get("description", "")
        if self.schema.get("examples"):
            tooltip += "\nExamples: " + ", ".join(self.schema["examples"])
        self.keylabel_widget.setToolTip(tooltip)

        return self.keylabel_widget

    def create_value_widget(
        self,
    ) -> Union[QLabel, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit, QWidget, None]:
        schema = self.schema
        element_type = self.element_type

        if "const" in schema:
            value_widget = w = QLabel(str(schema["const"]))
        elif element_type == "integer" or element_type == "number":
            value_widget = w = (
                QSpinBox() if element_type == "integer" else QDoubleSpinBox()
            )
            w.setMinimum(
                schema.get("minimum", schema.get("exclusiveMinimum", -1000000))
            )
            w.setMaximum(schema.get("maximum", schema.get("exclusiveMaximum", 1000000)))
            if "multipleOf" in schema:
                w.setSingleStep(schema["multipleOf"])
            w.setSuffix(schema.get("suffix"))
            if "default" in schema:
                w.setValue(schema["default"])
        elif element_type == "boolean":
            value_widget = w = QCheckBox()
            if "default" in schema:
                w.setChecked(schema["default"])
        elif element_type == "string":
            value_widget = w = QLineEdit()
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
            items_type = schema.get("items", {}).get("type", "object")

            if items_type == "object":
                value_widget = QTabWidget()
                value_widget.setHidden(True)
            else:
                value_widget = QWidget()
                hbox = QHBoxLayout()
                value_widget.setLayout(hbox)
                hbox.setContentsMargins(0, 0, 0, 0)

            def add_child():
                """
                Action to perform if the user wants to add a new element in the array.
                """
                self._children.append(
                    c := SchemaWidget(
                        schema["items"],
                        "",
                        position=len(self._children),
                        required_keys=self.required_keys,
                        make_flat=(items_type == "object"),
                    )
                )

                if type(value_widget) is QTabWidget:
                    value_widget.addTab(c, c.name)
                    value_widget.setHidden(False)
                    value_widget.setCurrentIndex(value_widget.count() - 1)
                elif (
                    value_widget is not None
                    and (layout := value_widget.layout()) is not None
                ):
                    layout.addWidget(c.value_widget or c)

                if maxItems is not None:
                    plus_button.setEnabled(len(self._children) < maxItems)
                minus_button.setEnabled(len(self._children) > minItems)

            def remove_child():
                """
                Action to perform if the user wants to remove the last element of the array.
                """
                if not self._children:
                    return
                c = self._children.pop()
                if type(value_widget) is QTabWidget:
                    value_widget.removeTab(value_widget.indexOf(c))
                    if len(self._children) == 0:
                        value_widget.setHidden(True)
                elif (
                    value_widget is not None
                    and (layout := value_widget.layout()) is not None
                ):
                    layout.removeWidget(c.value_widget or c)
                (c.value_widget or c).deleteLater()
                if maxItems is not None:
                    plus_button.setEnabled(len(self._children) < maxItems)
                minus_button.setEnabled(len(self._children) > minItems)

            plus_button = QPushButton("+")
            plus_button.setFixedWidth(plus_button.sizeHint().height() - 8)
            plus_button.setFixedHeight(plus_button.width())

            minItems = schema.get("minItems", 0)
            maxItems = schema.get("maxItems", None)
            plus_button.clicked.connect(add_child)

            minus_button = QPushButton("-")
            minus_button.setFixedWidth(plus_button.width())
            minus_button.setFixedHeight(plus_button.height())
            minus_button.setEnabled(False)
            minus_button.clicked.connect(remove_child)

            if not (minItems is not None and minItems == maxItems):
                self.hbox_plus_minus = QHBoxLayout()
                self.hbox_plus_minus.setContentsMargins(0, 0, 0, 0)
                self.hbox_plus_minus.setSpacing(0)
                self.hbox_plus_minus.addWidget(plus_button)
                self.hbox_plus_minus.addWidget(minus_button)
                self.hbox_plus_minus.addStretch()

            if items_type == "object":
                hbox = QHBoxLayout()
                hbox.setContentsMargins(0, 0, 0, 0)
                hbox.addWidget(QLabel(f"Add/Remove {self.name}"))
                hbox.addLayout(self.hbox_plus_minus)
                self._layout.addLayout(hbox)
            self._layout.addWidget(value_widget)

            for _ in range(minItems):
                add_child()

        else:
            self.setToolTip(None)
            value_widget = None

        self.value_widget = value_widget

        return value_widget

    def add_oneOf_widget(self):
        """The schema includes a 'oneOf' section, which permits to select one of the multiple configuration schemas.
        A list of radio buttons is displayed to select the option, and the selected configuration option is displayed in the QStackedWidget."""
        self.oneOf_stacked_widget = None
        if one_of := self.schema.get("oneOf"):
            layout = QVBoxLayout()
            layout.setSpacing(0)
            self._layout.addLayout(layout)
            # Group of buttons to select the oneOf option
            self.oneOf_selection_group = QButtonGroup()
            self.oneOf_selection_group.setExclusive(True)
            # Layout that will have the buttons
            self.oneOf_selection_layout = QHBoxLayout()
            self.oneOf_selection_layout.setContentsMargins(0, 0, 0, 0)
            self.oneOf_selection_layout.setSpacing(2)
            layout.addLayout(self.oneOf_selection_layout)
            # The widget that will include options
            self.oneOf_stacked_widget = QStackedWidget()
            layout.addWidget(self.oneOf_stacked_widget)
            layout.addStretch()
            for i, subschema in enumerate(one_of):
                title = subschema.get("title", f"Option {i + 1}")
                button = QRadioButton(title)
                self.oneOf_selection_group.addButton(button, i)
                self.oneOf_selection_layout.addWidget(button)

                content = SchemaWidget(
                    subschema, make_flat=True, required_keys=self.required_keys
                )
                content.setFlat(False)
                # content_layout = content.layout()
                # if type(content_layout) is QVBoxLayout:
                #     content_layout.addStretch()
                self.oneOf_stacked_widget.addWidget(content)

            self.oneOf_selection_layout.addStretch()
            self.oneOf_selection_group.idClicked.connect(
                self.oneOf_stacked_widget.setCurrentIndex
            )
            b = self.oneOf_selection_group.button(0)
            if b is not None:
                b.setChecked(True)

    def add_anyOf_widget(self):
        """The schema includes a 'anyOf' section, which permits to select one or more of the multiple configuration schemas.
        Note that at least one must be selected.
        A list of checkboxes is displayed to select the option(s), and the selected configuration option(s) widgets are enabled if selected.
        The overall presentation is a QFormLayout like."""
        self.anyOfs: list[AnyOf] = []
        self.anyOf_buttonGroup = QButtonGroup()
        self.anyOf_buttonGroup.setExclusive(False)

        def anyOf_buttonToggled(button: QAbstractButton):
            """Take action to make sure that at least one option is selected"""
            checked: list[QAbstractButton] = []
            for b in self.anyOf_buttonGroup.buttons():
                b.setEnabled(True)
                if b.isChecked():
                    checked.append(b)
            if len(checked) == 1:
                checked[0].setEnabled(False)
            if len(checked) == 0:
                button.setChecked(True)
                button.setEnabled(False)

        self.anyOf_buttonGroup.buttonToggled.connect(anyOf_buttonToggled)

        if any_of := self.schema.get("anyOf"):
            vbox = QVBoxLayout()
            vbox.setSpacing(0)
            vbox.setContentsMargins(0, 0, 0, 0)
            anyOf_widget_selection = QHBoxLayout()
            anyOf_widget_selection.setSpacing(10)
            anyOf_widgets_layout = QVBoxLayout()
            anyOf_widgets_layout.setSpacing(0)
            anyOf_widgets_layout.setContentsMargins(0, 0, 0, 0)
            vbox.addLayout(anyOf_widget_selection)
            vbox.addLayout(anyOf_widgets_layout)
            self._layout.addLayout(vbox)

            for subschema in any_of:
                widget = AnyOf(subschema)
                self.anyOfs.append(widget)
                anyOf_widget_selection.addWidget(widget.cb)
                self.anyOf_buttonGroup.addButton(widget.cb)
                anyOf_widgets_layout.addWidget(widget.schema_widget)
            anyOf_widget_selection.addStretch()
            self.anyOfs[0].selected = True

    def add_properties_widgets(self):
        properties = self.schema.get("properties", {})
        if type(properties) is not dict or len(properties) == 0:
            return
        properties_form = QFormLayout()
        properties_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        properties_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        properties_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        properties_form.setContentsMargins(0, 0, 0, 0)
        properties_form.setVerticalSpacing(2)
        self._layout.addLayout(properties_form)
        for key in properties.keys():
            subschema = properties[key]
            child = SchemaWidget(
                subschema, key, required_keys=self.required_keys, make_flat=True
            )
            if child.value_widget is not None:
                if child.hbox_plus_minus and child.keylabel_widget:
                    child.keylabel_widget.label_container_layout.addLayout(
                        child.hbox_plus_minus
                    )
                properties_form.addRow(child.keylabel_widget, child.value_widget)
            else:
                self._layout.addWidget(child)
            self._children.append(child)

    @property
    def value(self):
        if not self.selected:
            return None

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

    @property
    def selected(self):
        if type(self.keylabel_widget) is KeyLabel:
            return self.keylabel_widget.cb.isChecked()
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

        if self.oneOf_stacked_widget is not None:
            current_widget = self.oneOf_stacked_widget.currentWidget()
            assert isinstance(current_widget, SchemaWidget)
            json_value = current_widget.json()
            assert type(json_value) is dict
            result.update(json_value)

        for current_widget in self.anyOfs:
            if not current_widget.selected:
                continue
            json_value = current_widget.schema_widget.json()
            assert type(json_value) is dict
            result.update(json_value)

        return result

    def validate(self):
        try:
            validate(self.json(), self.schema)
            for anyOf in self.anyOfs:
                anyOf.schema_widget.validate()
            return True
        except ValidationError as e:
            error = QErrorMessage()
            error.showMessage(f"Error on validation of {e.json_path[2:]}: {e.message}")
            return True


class ConfigGeneratorIntroductionPage(QWizardPage):
    def __init__(self, parent: "ConfigGeneratorWizard"):
        super().__init__(parent)
        self.setTitle("Introduction")
        self.setSubTitle(
            "This wizard will help you generate a Configuration File for Laser Studio"
        )
        layout = QVBoxLayout()
        self.setLayout(layout)
        label = QLabel(
            "<p>For each page of the generator, fill the properties of the instruments with the desired values.</p>"
            "<p>You can make optional properties not to be added in the file by unchecking the checkbox next to the field name.</p>"
            "<p>If you need an information about a property, hover the cursor over its name to see the description.</p>"
            "<p>At the end the Configuration File will be shown for you and you can save it.</p>"
            "<p>Get more details about the schema in <a href='https://laserstudio.readthedocs.io/en/latest/'>the documentation</a>.</p>"
        )
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        label.setOpenExternalLinks(True)
        label.linkActivated.connect(lambda url: print(url))
        layout.addWidget(label)


class ConfigResultPage(QWizardPage):
    def __init__(self, parent: "ConfigGeneratorWizard"):
        super().__init__(parent)
        self.setTitle("Configuration File Result")
        self.setSubTitle("This is the generated Configuration File")
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.result_label = QLabel()
        layout.addWidget(self.result_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

    def initializePage(self):
        wiz = self.wizard()
        assert isinstance(wiz, ConfigGeneratorWizard)
        configs = {}
        for config_page in wiz.config_generation_pages:
            configs[config_page.schema_widget.key] = config_page.schema_widget.json()
        self.config = configs
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
    def __init__(self, parent: "ConfigGeneratorWizard", key: str, schema: dict):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.schema_widget = SchemaWidget(schema, key, make_flat=True)
        scroll.setWidget(self.schema_widget)
        layout.addWidget(scroll)
        self.setTitle(schema.get("title"))
        self.setSubTitle(schema.get("description"))

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
    app.setStyle(LedgerStyle)
    app.setPalette(LedgerPalette)
    wizard = ConfigGeneratorWizard(config_generator.schema)
    wizard.show()
    sys.exit(app.exec())
