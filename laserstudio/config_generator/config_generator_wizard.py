#!/usr/bin/python3
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWizardPage,
    QWizard,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QFileDialog,
)
import sys
import yaml

try:
    from .ref_resolve import set_base_url
    from .config_generator import ConfigGenerator, validate, ValidationError
    from .config_generator_widgets import SchemaWidget
    from ..utils.colors import LedgerPalette, LedgerStyle
except ImportError:
    from laserstudio.config_generator.ref_resolve import set_base_url
    from laserstudio.config_generator.config_generator import (
        ConfigGenerator,
        validate,
        ValidationError,
    )
    from laserstudio.config_generator.config_generator_widgets import SchemaWidget
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
        self.setSubTitle(
            "This is the generated Configuration File. Click Finish to use it in Laser Studio."
        )
        layout = QVBoxLayout()
        save = QPushButton("Save Configuration File")
        save.clicked.connect(self.save_config)

        self.setLayout(layout)
        self.result_label = QLabel()
        layout.addWidget(self.result_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        layout.addWidget(save)

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

    def save_config(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration File",
            "config.yaml",
            "YAML Files (*.yaml);;All Files (*)",
        )
        if filename:
            with open(filename, "w") as f:
                f.write(yaml.dump(self.config, indent=2))


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


def main():
    config_generator = ConfigGenerator()
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


if __name__ == "__main__":
    main()
