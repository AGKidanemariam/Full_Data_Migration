"""Parse, validate, and stage one MACS FlightState file."""

from src.flightstate_pipeline import transform_main


if __name__ == "__main__":
    raise SystemExit(transform_main())