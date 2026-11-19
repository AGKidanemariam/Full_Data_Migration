"""
Creating a mapping for flight_state_telemtry field names
"""

import json
from typing import List, Dict, Optional

NEW_FIELDS = [
    "time",
    "aircraft_id",
    "experiment_id",
    "relative_time_sec",
    "log_time",
    "processor_id",
    "callsign",
    "aircraft_type",
    "owner",
    "flight_rules",
    "cid",
    "latitude",
    "longitude",
    "x_coord",
    "y_coord",
    "altitude_ft",
    "indicated_airspeed_knots",
    "mach_number",
    "ground_speed_knots",
    "true_airspeed_knots",
    "true_heading_deg",
    "magnetic_heading_deg",
    "bank_angle_deg",
    "vertical_speed_ft_per_min",
    "weight_lbs",
    "fuel_rate_lb_per_hr",
    "thrust_percent",
    "altitude_target_ft",
    "heading_target_deg",
    "speed_target_knots",
    "cross_track_error",
    "flight_path_error",
    "wind_direction_deg",
    "wind_speed_knots",
    "vnav_active",
    "lnav_active",
    "auto_speed_active",
    "space_speed_active",
    "mach_active",
    "datablock_mode",
    "flaps_position",
    "gear_position",
    "flight_phase",
    "displayed_delay_ms",
    "delay_ms",
    "xy_distance_flown_nm",
    "time_flown_sec",
    "vertical_distance_flown_ft",
    "xy_along_track_distance_to_dest_nm",
    "eta_to_destination",
    "utm_state",
    "fp_type",
    "fp_gate_name",
    "fp_mfix_name",
    "fp_ofix_name",
    "fp_category",
    "fp_route",
    "fp_depart_fix",
    "fp_depart_time",
    "fp_assign_alt_ft",
    "fp_filed_speed",
    "fp_time_enroute_sec",
    "fp_appr_speed",
    "fp_land_speed",
    "fp_coord_frd",
    "fp_coord_fix",
    "fp_coord_x",
    "fp_coord_y",
    "fp_coord_time",
    "fp_dest_fix",
    "fp_dest_name",
    "fp_rw_name",
    "fp_config",
    "fp_beacon",
    "fp_atc_type",
    "fp_time_rcd",
    "fp_status",
    "fp_data_src",
    "fp_equip_avail",
    "fp_dlnk_equipd",
    "atc_code",
    "geo_sector",
    "is_overflow_flight",
    "is_arrival",
    "is_departure",
    "func_alloc_state",
    "thrust_state",
]

LOG_FILE_FIELDS = ['UTC_TIME', 'WEIGHT', 'FUEL_RATE', 'REL_TIME', 'LOG_TIME', 'PROC', 'CALLSIGN', 'CID', 'FLIGHT_RULES', 'STAMP_TIME', 'SIM_TIME', 'LAT', 'LONG', 'X', 'Y', 'ALT', 'IAS', 'MACH', 'TH', 'TGT', 'VS', 'GS', 'TAS', 'MH', 'BANK', 'ALT_T', 'HDG_T', 'SPD_T', 'CTE', 'FPE', 'WD', 'WS', 'THRUSTPERCENT', 'DISPLAYED_DELAY', 'DELAY', 'ATC', 'AC', 'GEO', 'IS_OVER_FLT', 'IS_ARR', 'IS_DEP', 'FLAPS', 'GEAR', 'FLIGHT_PHASE', 'THRUST', 'FuncAlloc-IH-AH-AFC-IATAC-DC-RSC-USR-RUC-UUR-RTFAT-RWC-UWR', 'DATABLOCK_MODE', 'IN_VNAV', 'IN_LNAV', 'IN_AUTO_SPD', 'IN_SPACE_SPD', 'IN_MACH', 'XY_DIST_FLOWN', 'TIME_FLOWN', 'VERT_FLOWN', 'XY_ALONG_TRACK_DIST_TO_DEST', 'ETA_TO_DEST', 'UTM_STATE', 'FP_TYPE', 'FP_GATE_NAME', 'FP_MFIX_NAME', 'FP_OFIX_NAME', 'FP_CATEGORY', 'FP_ROUTE', 'FP_DEPART_FIX', 'FP_DEPART_TIME', 'FP_ASSIGN_ALT', 'FP_FILED_SPEED', 'FP_TIME_ENROUTE', 'FP_APPR_SPEED', 'FP_LAND_SPEED', 'FP_COORD_FRD', 'FP_COORD_FIX', 'FP_COORD_X', 'FP_COORD_Y', 'FP_FAA_COORD_TIME', 'FP_COORD_TIME', 'FP_DEST_FIX', 'FP_DEST_NAME', 'FP_RW_NAME', 'FP_CONFIG', 'FP_BEACON', 'FP_ATC_TYPE', 'FP_TIME_RCD', 'FP_STATUS', 'FP_DATA_SRC', 'FP_EQUIP_AVAIL', 'FP_DLNK_EQUIPD']

# assert len(LOG_FILE_FIELDS) == len(NEW_FIELDS), f"{len(LOG_FILE_FIELDS)} != {len(NEW_FIELDS)}"

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein edit distance between two strings.
    """
    s1 = s1.lower()
    s2 = s2.lower()

    if len(s1) < len(s2):
        s1, s2 = s2, s1

    previous_row = list(range(len(s2) + 1))

    for i, c1 in enumerate(s1, start=1):
        current_row = [i]

        for j, c2 in enumerate(s2, start=1):
            insertions = current_row[j - 1] + 1
            deletions = previous_row[j] + 1
            substitutions = previous_row[j - 1] + (c1 != c2)

            current_row.append(
                min(insertions, deletions, substitutions)
            )

        previous_row = current_row

    return previous_row[-1]


def get_top_candidates(
    source: str,
    columns: List[str],
    top_n: int = 5
) -> List[tuple]:
    """
    Return the top N column candidates based on Levenshtein distance.
    """

    candidates = []

    for column in columns:
        distance = levenshtein_distance(source, column)
        candidates.append((column, distance))

    candidates.sort(key=lambda x: x[1])

    return candidates[:top_n]


def generate_mapping(
    par_1: List[str],
    par_2: List[str]
) -> Dict[str, str]:
    """
    Map each string in par_1 to a column in par_2.

    Exact matches are automatically mapped.

    For non-exact matches, the user is presented with the
    top 5 Levenshtein candidates and prompted to choose one.
    """

    mapping = {}

    # Case-insensitive lookup for exact matches
    column_lookup = {
        column.lower(): column
        for column in par_2
    }

    for source in par_1:

        # ---------------------------------------------------------
        # Exact match
        # ---------------------------------------------------------
        if source.lower() in column_lookup:
            matched_column = column_lookup[source.lower()]
            mapping[source] = matched_column

            print(
                f"[EXACT] {source} -> {matched_column}"
            )

            continue

        # ---------------------------------------------------------
        # No exact match -- find candidates
        # ---------------------------------------------------------
        candidates = get_top_candidates(
            source,
            par_2,
            top_n=5
        )

        print("\n" + "=" * 70)
        print(f"No exact match found for: {source}")
        print("=" * 70)

        print("\nTop candidates:")

        for i, (candidate, distance) in enumerate(
            candidates,
            start=1
        ):
            print(
                f"  {i}. {candidate:<40} "
                f"(Levenshtein distance: {distance})"
            )

        print("  0. Skip / do not map")
        print("  r. Enter a custom column name")

        # ---------------------------------------------------------
        # Prompt user
        # ---------------------------------------------------------
        while True:

            choice = input(
                "\nSelect an option: "
            ).strip()

            # Skip
            if choice == "0":
                print(f"[SKIP] {source}")
                break

            # Custom mapping
            if choice.lower() == "r":
                custom = input(
                    f"Enter column name for '{source}': "
                ).strip()

                if custom:
                    mapping[source] = custom
                    print(
                        f"[CUSTOM] {source} -> {custom}"
                    )
                    break

                print("Column name cannot be empty.")
                continue

            # Candidate selection
            try:
                index = int(choice)

                if 1 <= index <= len(candidates):
                    selected = candidates[index - 1][0]

                    mapping[source] = selected

                    print(
                        f"[MAPPED] {source} -> {selected}"
                    )

                    break

                print(
                    f"Please enter a number between "
                    f"0 and {len(candidates)}."
                )

            except ValueError:
                print(
                    "Invalid selection. "
                    "Enter a number or 'r'."
                )

    return mapping


if __name__ == "__main__":
    mapping = generate_mapping(LOG_FILE_FIELDS, NEW_FIELDS)

    print(mapping)

    print("\n" + "=" * 70)
    print("FINAL MAPPING")
    print("=" * 70)

    for source, destination in mapping.items():
        print(f"{source} -> {destination}")

    with open("mapping.json", "w") as file:
        try:
            file.write(json.dumps(mapping))
        except:
            file.write(str(mapping))
