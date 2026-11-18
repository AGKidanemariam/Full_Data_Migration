"""Validate or load one staged FlightState bundle into PostgreSQL."""

from src.flightstate_pipeline import load_main


if __name__ == "__main__":
    raise SystemExit(load_main())