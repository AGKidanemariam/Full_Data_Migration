import pytest
# from macs_parser import Record
# from macs_parser.utils import _camel_case_to_snake_case
# from macs_parser.utils import normalize_column_names
from data_migration.macs_parser import Record
from data_migration.macs_parser.utils import _camel_case_to_snake_case
from data_migration.macs_parser.utils import normalize_column_names


@pytest.mark.parametrize(
    "sample, expected",
    [
        ("camelCase", "camel_case"),
        ("helloWorld", "hello_world"),
        ("myVariableName", "my_variable_name"),
        ("CamelCase", "camel_case"),
        ("SomeLongVariableName", "some_long_variable_name"),
        ("simple", "simple"),
        ("ABC", "abc"),
        ("hello123World", "hello123_world"),
        ("hello_world", "hello_world"),
        ("THRUSTPERCENT", "thrustpercent"),
        ("", ""),
        ("fms__vnav", "fms_vnav"),
    ],
)
def test_case_conversion(sample, expected):
    res = _camel_case_to_snake_case(sample)
    assert res == expected


@pytest.mark.parametrize(
    "sample, expected",
    [
        ("acOwnedByController", "ac_owned_by_controller"),
        ("acType", "ac_type"),
        ("eventTime", "event_time"),
        ("relEventTime", "rel_event_time"),
        ("afrAcControlledByPilot", "afr_ac_controlled_by_pilot"),
        ("ifrAcInGeoArea", "ifr_ac_in_geo_area"),
        ("mfEtaDisp", "mf_eta_disp"),
        ("mfEtaReprt", "mf_eta_reprt"),
        ("xPos", "x_pos"),
        ("yPos", "y_pos"),
        ("grndSpd", "grnd_spd"),
        ("airSpd", "air_spd"),
        ("nexWaypoint", "nex_waypoint"),
        ("freeFlightStat", "free_flight_stat"),
        ("selftSpacing", "selft_spacing"),
        ("THRUST_PERCENT", "thrust_percent"),
        ("self spacing status", "self_spacing_status"),
    ],
)
def test_column_name_normalization(sample, expected):
    rec = Record([sample])

    mapping = {}  # empty mapping for this particular test

    normalize_column_names(rec, mapping)

    # indexing 0 because there is only one field/column
    assert rec.fields[0] == expected
