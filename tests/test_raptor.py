from laserstudio.instruments.camera_raptor import RaptorManufacturersData
from datetime import date


def test_manufacturer_data():
    data = RaptorManufacturersData.from_bytes(
        b"\x12\x27\x11\x0a\x0c\x4c\x61\x72\x6e\x65\xca\x04\x14\x03\x8e\x06\xe4\x09\x50\xbe"
    )
    """
    Serial no. = 10002
    Build date = 17/10/12
    Build code = Larne
    ADC cal 0 °C = 1226
    ADC cal+40 °C = 788
    DAC cal 0 °C = 1678
    DAC cal+40 °C = 2532
    """
    assert data.serial_number == 10002
    assert data.build_date == date(2017, 10, 12)
    assert data.buildcode == "Larne"
    assert data.adc_cal_0_deg == 1226
    assert data.adc_cal_40_deg == 788
    assert data.dac_cal_0_deg == 1678
    assert data.dac_cal_40_deg == 2532
