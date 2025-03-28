import json
from pathlib import Path

import pytest

from akkudoktoreos.core.ems import get_ems
from akkudoktoreos.prediction.elecpriceimport import ElecPriceImport
from akkudoktoreos.utils.datetimeutil import compare_datetimes, to_datetime

DIR_TESTDATA = Path(__file__).absolute().parent.joinpath("testdata")

FILE_TESTDATA_ELECPRICEIMPORT_1_JSON = DIR_TESTDATA.joinpath("import_input_1.json")


@pytest.fixture
def elecprice_provider(sample_import_1_json, config_eos):
    """Fixture to create a ElecPriceProvider instance."""
    settings = {
        "elecprice_provider": "ElecPriceImport",
        "elecpriceimport_file_path": str(FILE_TESTDATA_ELECPRICEIMPORT_1_JSON),
        "elecpriceimport_json": json.dumps(sample_import_1_json),
    }
    config_eos.merge_settings_from_dict(settings)
    provider = ElecPriceImport()
    assert provider.enabled()
    return provider


@pytest.fixture
def sample_import_1_json():
    """Fixture that returns sample forecast data report."""
    with open(FILE_TESTDATA_ELECPRICEIMPORT_1_JSON, "r") as f_res:
        input_data = json.load(f_res)
    return input_data


# ------------------------------------------------
# General forecast
# ------------------------------------------------


def test_singleton_instance(elecprice_provider):
    """Test that ElecPriceForecast behaves as a singleton."""
    another_instance = ElecPriceImport()
    assert elecprice_provider is another_instance


def test_invalid_provider(elecprice_provider, config_eos):
    """Test requesting an unsupported elecprice_provider."""
    settings = {
        "elecprice_provider": "<invalid>",
        "elecpriceimport_file_path": str(FILE_TESTDATA_ELECPRICEIMPORT_1_JSON),
    }
    config_eos.merge_settings_from_dict(settings)
    assert not elecprice_provider.enabled()


# ------------------------------------------------
# Import
# ------------------------------------------------


@pytest.mark.parametrize(
    "start_datetime, from_file",
    [
        ("2024-11-10 00:00:00", True),  # No DST in Germany
        ("2024-08-10 00:00:00", True),  # DST in Germany
        ("2024-03-31 00:00:00", True),  # DST change in Germany (23 hours/ day)
        ("2024-10-27 00:00:00", True),  # DST change in Germany (25 hours/ day)
        ("2024-11-10 00:00:00", False),  # No DST in Germany
        ("2024-08-10 00:00:00", False),  # DST in Germany
        ("2024-03-31 00:00:00", False),  # DST change in Germany (23 hours/ day)
        ("2024-10-27 00:00:00", False),  # DST change in Germany (25 hours/ day)
    ],
)
def test_import(elecprice_provider, sample_import_1_json, start_datetime, from_file, config_eos):
    """Test fetching forecast from Import."""
    ems_eos = get_ems()
    ems_eos.set_start_datetime(to_datetime(start_datetime, in_timezone="Europe/Berlin"))
    if from_file:
        config_eos.elecpriceimport_json = None
        assert config_eos.elecpriceimport_json is None
    else:
        config_eos.elecpriceimport_file_path = None
        assert config_eos.elecpriceimport_file_path is None
    elecprice_provider.clear()

    # Call the method
    elecprice_provider.update_data()

    # Assert: Verify the result is as expected
    assert elecprice_provider.start_datetime is not None
    assert elecprice_provider.total_hours is not None
    assert compare_datetimes(elecprice_provider.start_datetime, ems_eos.start_datetime).equal
    values = sample_import_1_json["elecprice_marketprice_wh"]
    value_datetime_mapping = elecprice_provider.import_datetimes(
        ems_eos.start_datetime, len(values)
    )
    for i, mapping in enumerate(value_datetime_mapping):
        assert i < len(elecprice_provider.records)
        expected_datetime, expected_value_index = mapping
        expected_value = values[expected_value_index]
        result_datetime = elecprice_provider.records[i].date_time
        result_value = elecprice_provider.records[i]["elecprice_marketprice_wh"]

        # print(f"{i}: Expected: {expected_datetime}:{expected_value}")
        # print(f"{i}:   Result: {result_datetime}:{result_value}")
        assert compare_datetimes(result_datetime, expected_datetime).equal
        assert result_value == expected_value
