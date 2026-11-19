import re
from typing import Tuple
from datetime import datetime


def _standardize_log_type(raw_log_type: str) -> str:
    """
    Map a raw log type string to a standardized log type category.
    
    Args:
        raw_log_type: The raw log type extracted from the filename
        
    Returns:
        A standardized log type string
        
    Examples:
        >>> standardize_log_type("Macs_FlightState_view_1")
        'FlightState'
        
        >>> standardize_log_type("Wkload")
        'Workload'
        
        >>> standardize_log_type("Macs_Atc_ZOA_246_")
        'ATC'
    """
    # Convert to lowercase for case-insensitive matching
    log_type_lower = raw_log_type.lower()
    
    if 'flightstate' in log_type_lower:
        return 'FlightState'
    elif 'atcstate' in log_type_lower:
        return 'ATCState'
    elif 'atc' in log_type_lower:
        return 'ATC'
    elif 'traj' in log_type_lower:
        return 'Trajectory'
    elif 'wkload' in log_type_lower or 'workload' in log_type_lower:
        return 'Workload'
    elif 'pilot' in log_type_lower:
        return 'Pilot'
    elif 'compmet' in log_type_lower:
        return 'CompMet'
    elif 'custom' in log_type_lower:
        return 'Custom'
    else:
        raise ValueError(f"Could not determine the log type of `{raw_log_type}`")


def _normalize_timestamp(timestamp_str: str) -> datetime:
    """
    Normalize a timestamp string from log filename to a timezone-aware datetime object.
    
    Args:
        timestamp_str: Timestamp string in format 'YYYY-MM-DD_HH-MM-SS' or 'YYYY-MM-DD_HH-MM'
        timezone: Timezone string (default: 'UTC'). Examples: 'UTC', 'America/Los_Angeles', 'US/Pacific'
        
    Returns:
        A timezone-aware datetime object suitable for TIMESTAMPTZ columns
    """
    # Replace underscores and hyphens with appropriate separators for datetime parsing
    # Format: YYYY-MM-DD_HH-MM-SS or YYYY-MM-DD_HH-MM
    
    # Split by underscore to separate date and time
    parts = timestamp_str.split('_')
    
    if len(parts) != 2:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")
    
    date_part = parts[0]  # YYYY-MM-DD
    time_part = parts[1]  # HH-MM-SS or HH-MM
    
    # Replace hyphens in time part with colons
    time_part = time_part.replace('-', ':')
    
    # If seconds are missing, add :00
    time_components = time_part.split(':')
    if len(time_components) == 2:
        time_part += ':00'
    elif len(time_components) != 3:
        raise ValueError(f"Invalid time format in timestamp: {timestamp_str}")
    
    # Combine date and time with standard separator
    datetime_str = f"{date_part} {time_part}"
    
    # Parse the datetime string
    dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
    
    # Make it timezone-aware
    # tz = pytz.timezone(timezone)
    # dt_aware = tz.localize(dt)
    
    return dt


def parse_log_filename(file: str) -> Tuple[str, str, datetime]:
    """
    Parse a log filename into three components: computer name, log type, and timestamp.
    
    Args:
        file: The log filename to parse
        
    Returns:
        A tuple containing (computer_name, log_type, timestamp)
        
    Examples:
        >>> parse_log_filename("AOL-Blanka_Macs_Custom_zoa_246_mulford_and_grove_combined__2026-07-07_12-00-08.log")
        ('AOL-Blanka', 'Macs_Custom_zoa_246_mulford_and_grove_combined_', '2026-07-07_12-00-08')
        
        >>> parse_log_filename("AOL-Blanka_Wkload_2026-06-12_12-06-33.log")
        ('AOL-Blanka', 'Wkload', '2026-06-12_12-06-33')
    """
    # Remove the .log extension if present
    if file.endswith('.log'):
        file = file[:-4]
    
    # Pattern to match timestamp at the end: YYYY-MM-DD_HH-MM-SS or YYYY-MM-DD_HH-MM
    # The timestamp pattern matches dates from the end of the string
    timestamp_pattern = r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}(?:-\d{2})?)$'
    
    # Search for the timestamp at the end
    timestamp_match = re.search(timestamp_pattern, file)
    
    if not timestamp_match:
        raise ValueError(f"Could not find valid timestamp in filename: {file}")
    
    timestamp = _normalize_timestamp(timestamp_match.group(1))
    
    # Remove the timestamp from the end to get the remaining part
    remaining = file[:timestamp_match.start()]
    
    # Remove trailing underscore(s) before the timestamp
    remaining = remaining.rstrip('_')
    
    # Split by the first underscore to separate computer name from log type
    # Computer name is everything before the first underscore
    first_underscore = remaining.find('_')
    
    if first_underscore == -1:
        raise ValueError(f"Could not parse computer name from filename: {file}")
    
    computer_name = remaining[:first_underscore]
    log_type = _standardize_log_type(remaining[first_underscore + 1:])
    
    return (computer_name, log_type, timestamp)


# Test the function with your examples
if __name__ == "__main__":
    test_files = [
        "AOL-Blanka_Macs_Custom_zoa_246_mulford_and_grove_combined__2026-07-07_12-00-08.log",
        "AOL-Blanka_Macs_FlightState_zoa_246_mulford_and_grove_combined_1_2026-06-12_12-26-27.log",
        "AOL-Blanka_Macs_Pilot_zoa_246_mulford_and_grove_combined__2026-06-11_14-19-16.log",
        "AOL-Blanka_Macs_Traj_zoa_246_mulford_and_grove_combined_1_2026-06-12_13-42-07.log",
        "AOL-Blanka_Wkload_2026-06-12_12-06-33.log",
        "AOL-Carolina_Macs_AtcState_view__2026-06-18_10-54-53.log",
        "AOL-Carolina_Macs_Atc_ZOA_246__2026-06-18_10-54-53.log",
        "AOL-Carolina_Macs_CompMet_view__2026-06-11_14-05-36.log",
        "TH-Saho_Macs_Atc_ZOA_252__2026-06-26_16-28-34.log",
    ]
    
    print("Testing parse_and_standardize_log_filename function:\n")
    print(f"{'Computer':<20} {'Standardized Type':<20} {'Timestamp':<20}")
    print("=" * 60)
    
    for filename in test_files:
        try:
            computer, std_type, timestamp = parse_log_filename(filename)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            print(f"{computer:<20} {std_type:<20} {timestamp_str:<30}")
        except ValueError as e:
            print(f"Error parsing {filename}: {e}\n")
    
    print("\n" + "=" * 60)
    print("\nDetailed output for first few files:\n")
    
    for filename in test_files[:5]:
        try:
            computer, std_type, timestamp = parse_log_filename(filename)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            print(f"File: {filename}")
            print(f"  Computer: {computer}")
            print(f"  Standardized Type: {std_type}")
            print(f"  Timestamp: {timestamp_str}")
            print()
        except ValueError as e:
            print(f"Error parsing {filename}: {e}\n")
