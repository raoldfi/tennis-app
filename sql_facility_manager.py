"""
Facility Management Helper for SQLite Tennis Database

Handles all facility-related database operations including CRUD operations,
facility schedules, availability, and utilization tracking.

Updated to work without Line class - uses match scheduled_times instead.
Added get_available_dates API for finding available dates for matches.
"""

from math import log
import sqlite3
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from panel import state
from tennis_db_interface import TennisDBInterface
from usta import (
    Facility,
    WeeklySchedule,
    DaySchedule,
    TimeSlot,
    FacilityAvailabilityInfo,
    TimeSlotAvailability,
    Team,
    League,
)

# Logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


class SQLFacilityManager:
    """Helper class for managing facility operations in SQLite database"""

    def __init__(self, cursor: sqlite3.Cursor, db_instance: TennisDBInterface):
        """
        Initialize SQLFacilityManager

        Args:
            cursor: SQLite cursor for database operations
            db_instance: Reference to main database instance for accessing other managers
        """
        self.cursor = cursor
        self.db = db_instance

    def _dictify(self, row) -> dict:
        """Convert sqlite Row object to dictionary"""
        return dict(row) if row else {}

    def add_facility(self, facility: Facility) -> bool:
        """Add a new facility to the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")

        try:
            # Check if facility ID already exists
            existing = self.get_facility(facility.id)
            if existing:
                raise ValueError(f"Facility with ID {facility.id} already exists")

            # Insert basic facility info (including short_name)
            self.cursor.execute(
                """
                INSERT INTO facilities (id, name, short_name, location, total_courts)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    facility.id,
                    facility.name,
                    facility.short_name,
                    facility.location,
                    facility.total_courts,
                ),
            )

            # Insert schedule data
            self._insert_facility_schedule(facility, facility.schedule)

            # Insert unavailable dates
            self._insert_facility_unavailable_dates(
                facility, facility.unavailable_dates
            )

        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding facility: {e}")
        return True

    def get_facility(self, facility_id: int) -> Optional[Facility]:
        """Get a facility by ID"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(
                f"Facility ID must be a positive integer, got: {facility_id}"
            )

        try:
            # Get basic facility info
            self.cursor.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,))
            row = self.cursor.fetchone()
            if not row:
                return None

            facility_data = self._dictify(row)

            # Create basic facility (including short_name)
            facility = Facility(
                id=facility_data["id"],
                name=facility_data["name"],
                short_name=facility_data["short_name"],
                location=facility_data["location"],
                total_courts=facility_data["total_courts"],
            )

            # Load schedule data
            facility.schedule = self._load_facility_schedule(facility)

            # Load unavailable dates
            facility.unavailable_dates = self._load_facility_unavailable_dates(facility)

            return facility
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving facility {facility_id}: {e}")

    def update_facility(self, facility: Facility) -> bool:
        """Update an existing facility in the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")

        try:
            # Check if facility exists
            existing_facility = self.get_facility(facility.id)
            if not existing_facility:
                raise ValueError(f"Facility with ID {facility.id} does not exist")

            # Update basic facility info (including short_name)
            self.cursor.execute(
                """
                UPDATE facilities 
                SET name = ?, short_name = ?, location = ?, total_courts = ?
                WHERE id = ?
            """,
                (
                    facility.name,
                    facility.short_name,
                    facility.location,
                    facility.total_courts,
                    facility.id,
                ),
            )

            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update facility {facility.id}")

            # Update schedule data (clear and re-insert)
            self._insert_facility_schedule(facility, facility.schedule)

            # Update unavailable dates (clear and re-insert)
            self._insert_facility_unavailable_dates(
                facility, facility.unavailable_dates
            )

        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating facility: {e}")
        return True

    def delete_facility(self, facility: Facility) -> bool:
        """Delete a facility from the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")

        try:
            # Check if facility_id exists in the database
            facility_id = facility.id
            existing_facility = self.get_facility(facility_id)
            if not existing_facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")

            # Check if facility is referenced by teams
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM team_preferred_facilities WHERE facility_id = ?",
                (facility_id,),
            )
            team_count = self.cursor.fetchone()["count"]
            if team_count > 0:
                raise ValueError(
                    f"Cannot delete facility {facility_id}: it is referenced by {team_count} team(s)"
                )

            # Check if facility is referenced by matches
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM matches WHERE facility_id = ?",
                (facility_id,),
            )
            match_count = self.cursor.fetchone()["count"]
            if match_count > 0:
                raise ValueError(
                    f"Cannot delete facility {facility_id}: it is referenced by {match_count} match(es)"
                )

            # Delete the facility (CASCADE will delete schedule and unavailable_dates)
            self.cursor.execute("DELETE FROM facilities WHERE id = ?", (facility_id,))

            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete facility {facility_id}")

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting facility {facility_id}: {e}")
        return True

    def list_facilities(self) -> List[Facility]:
        """List all facilities - with enhanced error handling and debugging"""

        logger.setLevel(logging.INFO)
        logger.debug("Starting list_facilities")
        try:
            # Query database
            query = (
                "SELECT id, name, short_name, location, total_courts "
                "FROM facilities ORDER BY name"
            )
            logger.debug("Executing query: %s", query)
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            logger.info("Fetched %d facility rows from database", len(rows))

            facilities: List[Facility] = []
            for row in rows:
                try:
                    # Convert Row to dictionary to enable .get() method
                    row_data = self._dictify(row)

                    logger.debug(
                        "Processing row id=%s name=%s short_name=%s location=%s total_courts=%s",
                        row_data["id"],
                        row_data["name"],
                        row_data.get("short_name"),
                        row_data["location"],
                        row_data["total_courts"],
                    )

                    # Create facility with basic info and default schedule
                    facility = Facility(
                        id=row_data["id"],
                        name=row_data["name"],
                        short_name=row_data.get("short_name"),
                        location=row_data["location"],
                        total_courts=row_data["total_courts"],
                        schedule=WeeklySchedule(),  # Ensure we have a valid schedule
                        unavailable_dates=[],  # Initialize with empty list
                    )

                    # Load schedule data separately with error handling
                    logger.debug("Loading schedule for facility id=%s", facility.id)
                    try:
                        loaded_schedule = self._load_facility_schedule(facility)
                        if loaded_schedule and isinstance(
                            loaded_schedule, WeeklySchedule
                        ):
                            facility.schedule = loaded_schedule
                            logger.debug(
                                "Schedule loaded successfully for facility id=%s",
                                facility.id,
                            )
                        else:
                            logger.warning(
                                "Invalid schedule returned for facility id=%s, using default",
                                facility.id,
                            )
                            facility.schedule = WeeklySchedule()
                    except Exception as schedule_error:
                        logger.error(
                            "Error loading schedule for facility id=%s: %s",
                            facility.id,
                            schedule_error,
                        )
                        facility.schedule = (
                            WeeklySchedule()
                        )  # Use default empty schedule

                    # Load unavailable dates with error handling
                    logger.debug(
                        "Loading unavailable dates for facility id=%s", facility.id
                    )
                    try:
                        unavailable_dates = self._load_facility_unavailable_dates(
                            facility
                        )
                        if unavailable_dates and isinstance(unavailable_dates, list):
                            facility.unavailable_dates = unavailable_dates
                            logger.debug(
                                "Unavailable dates loaded for facility id=%s: %s",
                                facility.id,
                                facility.unavailable_dates,
                            )
                        else:
                            # Empty list just means its always available
                            facility.unavailable_dates = []
                    except Exception as dates_error:
                        logger.error(
                            "Error loading unavailable dates for facility id=%s: %s",
                            facility.id,
                            dates_error,
                        )
                        facility.unavailable_dates = []  # Use empty list

                    # Validate the facility object before adding to list
                    if not isinstance(facility.schedule, WeeklySchedule):
                        logger.error(
                            "Facility id=%s has invalid schedule type: %s",
                            facility.id,
                            type(facility.schedule),
                        )
                        facility.schedule = WeeklySchedule()

                    # Test that the schedule has the expected methods
                    try:
                        test_days = facility.schedule.get_all_days()
                        if not isinstance(test_days, dict):
                            logger.error(
                                "Facility id=%s schedule.get_all_days() returned invalid type: %s",
                                facility.id,
                                type(test_days),
                            )
                            facility.schedule = WeeklySchedule()
                    except AttributeError as attr_error:
                        logger.error(
                            "Facility id=%s schedule missing get_all_days method: %s",
                            facility.id,
                            attr_error,
                        )
                        facility.schedule = WeeklySchedule()
                    except Exception as test_error:
                        logger.error(
                            "Facility id=%s schedule test failed: %s",
                            facility.id,
                            test_error,
                        )
                        facility.schedule = WeeklySchedule()

                    facilities.append(facility)
                    logger.debug(
                        "Successfully appended facility id=%s to result list",
                        facility.id,
                    )

                except Exception as facility_error:
                    logger.error(
                        "Error processing facility row %s: %s",
                        row_data.get("id", "unknown"),
                        facility_error,
                    )
                    # Skip this facility and continue with others
                    continue

            logger.info(
                "Completed list_facilities, returning %d facilities", len(facilities)
            )
            return facilities

        except Exception as e:
            logger.exception("Error in list_facilities")
            raise

    def get_facilities_by_name(
        self, name: str, exact_match: bool = True
    ) -> List[Facility]:
        """Get facilities by name or partial name match"""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Name must be a non-empty string")

        try:
            if exact_match:
                # Check both name and short_name for exact matches
                self.cursor.execute(
                    """
                    SELECT * FROM facilities 
                    WHERE name = ? OR short_name = ? 
                    ORDER BY name
                """,
                    (name, name),
                )
            else:
                # Partial match on both name and short_name
                self.cursor.execute(
                    """
                    SELECT * FROM facilities 
                    WHERE name LIKE ? OR short_name LIKE ? 
                    ORDER BY name
                """,
                    (f"%{name}%", f"%{name}%"),
                )

            facilities = []
            for row in self.cursor.fetchall():
                facility_data = self._dictify(row)

                facility = Facility(
                    id=facility_data["id"],
                    name=facility_data["name"],
                    short_name=facility_data.get("short_name"),
                    location=facility_data["location"],
                    total_courts=facility_data.get("total_courts", 0),
                )

                # Load schedule and unavailable dates
                facility.schedule = self._load_facility_schedule(facility)
                facility.unavailable_dates = self._load_facility_unavailable_dates(
                    facility
                )

                facilities.append(facility)

            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting facilities by name: {e}")

    # ======= Facility Schedule Methods ========

    def _insert_facility_schedule(
        self, facility: Facility, schedule: WeeklySchedule
    ) -> None:
        """Insert facility schedule data into the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")

        facility_id = facility.id
        try:
            # Clear existing schedule data for this facility
            self.cursor.execute(
                "DELETE FROM facility_schedules WHERE facility_id = ?", (facility_id,)
            )

            # Insert schedule for each day
            for day_name, day_schedule in schedule.get_all_days().items():
                for time_slot in day_schedule.start_times:
                    self.cursor.execute(
                        """
                        INSERT INTO facility_schedules (facility_id, day, time, available_courts)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            facility_id,
                            day_name,
                            time_slot.time,
                            time_slot.available_courts,
                        ),
                    )
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error inserting facility schedule: {e}")

    def _load_facility_schedule(self, facility: Facility) -> WeeklySchedule:
        """Load facility schedule from the database with enhanced error handling"""

        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id
            self.cursor.execute(
                """
                SELECT day, time, available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? 
                ORDER BY day, time
            """,
                (facility_id,),
            )

            # Create a new WeeklySchedule with proper initialization
            schedule = WeeklySchedule()

            rows = self.cursor.fetchall()

            for row in rows:
                try:
                    day_name = row["day"]
                    time_slot = TimeSlot(
                        time=row["time"], available_courts=row["available_courts"]
                    )

                    # Get the day schedule and add the time slot
                    day_schedule = schedule.get_day_schedule(day_name)
                    day_schedule.start_times.append(time_slot)

                except Exception as slot_error:
                    logger.error(
                        "Error processing schedule row for facility_id=%s: %s",
                        facility_id,
                        slot_error,
                    )
                    continue  # Skip this time slot and continue

            # Verify the schedule object is valid
            try:
                test_days = schedule.get_all_days()
                if not isinstance(test_days, dict):
                    logger.error(
                        "Created schedule has invalid get_all_days() result for facility_id=%s",
                        facility_id,
                    )
                    return WeeklySchedule()  # Return empty schedule
            except Exception as validation_error:
                logger.error(
                    "Schedule validation failed for facility_id=%s: %s",
                    facility_id,
                    validation_error,
                )
                return WeeklySchedule()  # Return empty schedule

            # logger.debug("Successfully loaded schedule for facility_id=%s", facility_id)
            return schedule

        except sqlite3.Error as e:
            logger.error(
                "Database error loading facility schedule for facility_id=%s: %s",
                facility_id,
                e,
            )
            return WeeklySchedule()  # Return empty schedule instead of raising
        except Exception as e:
            logger.error(
                "Unexpected error loading facility schedule for facility_id=%s: %s",
                facility_id,
                e,
            )
            return WeeklySchedule()  # Return empty schedule instead of raising

    # ======== Facility Unavailable Dates Methods ========

    def add_unavailable_date(self, facility: Facility, date: str) -> bool:
        """Add an unavailable date to a facility"""

        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id

            self.cursor.execute(
                """
                INSERT OR IGNORE INTO facility_unavailable_dates (facility_id, date)
                VALUES (?, ?)
            """,
                (facility_id, date),
            )
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding unavailable date: {e}")

        return True

    def remove_unavailable_date(self, facility: Facility, date: str) -> bool:
        """Remove an unavailable date from a facility"""

        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id
            # Delete the unavailable date
            self.cursor.execute(
                """
                DELETE FROM facility_unavailable_dates 
                WHERE facility_id = ? AND date = ?
            """,
                (facility_id, date),
            )
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error removing unavailable date: {e}")
        return True

    def _insert_facility_unavailable_dates(
        self, facility: Facility, unavailable_dates: List[str]
    ) -> None:
        """Insert facility unavailable dates into the database"""
        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id

            # Clear existing unavailable dates for this facility
            self.cursor.execute(
                "DELETE FROM facility_unavailable_dates WHERE facility_id = ?",
                (facility_id,),
            )

            # Insert unavailable dates
            for date_str in unavailable_dates:
                self.cursor.execute(
                    """
                    INSERT INTO facility_unavailable_dates (facility_id, date)
                    VALUES (?, ?)
                """,
                    (facility_id, date_str),
                )
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Database error inserting facility unavailable dates: {e}"
            )

    def _load_facility_unavailable_dates(self, facility: Facility) -> List[str]:
        """Load facility unavailable dates from the database"""
        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id

            self.cursor.execute(
                """
                SELECT date 
                FROM facility_unavailable_dates 
                WHERE facility_id = ? 
                ORDER BY date
            """,
                (facility_id,),
            )

            return [row["date"] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(
                f"Database error loading facility unavailable dates: {e}"
            )

    # ======== Facility Availability Methods ========

    def get_facility_availability(
        self, facility: Facility, dates: List[str], max_days: int = 50
    ) -> List["FacilityAvailabilityInfo"]:
        """
        Get availability information for a facility over a list of dates.

        Args:
            facility: Facility object to check availability for
            dates: List of dates in YYYY-MM-DD format to check
            max_days: Maximum number of days to return

        Returns:
            List of FacilityAvailabilityInfo objects containing availability details for each date where
            the facility is available.
        Raises:
            TypeError: If facility is not a Facility object
            ValueError: If dates is invalid
            RuntimeError: If there is a database error
        """
        try:
            # Validate inputs
            self._validate_facility_availability_inputs(facility, dates, max_days)

            # Filter dates by facility availability first to minimize database queries
            # This removes all the blackout dates and checks if the facility has a schedule for each date
            available_dates, unavailable_dates_info = (
                self._filter_dates_by_facility_availability(facility, dates)
            )

            facility_availability_info = []

            # Add unavailable date info first
            facility_availability_info.extend(unavailable_dates_info)

            # Only query database for dates when facility is actually available
            if available_dates:
                # Single database query to get scheduled times for available dates only
                # This function handles dry run state if enabled
                scheduled_times_by_date = self._get_scheduled_times_batch(
                    facility, available_dates
                )

                for date in available_dates:
                    # Get scheduled times for this specific date (from batch query)
                    scheduled_times = scheduled_times_by_date.get(date, [])

                    # Get availability for this date using cached scheduled times
                    availability_info = self._get_facility_availability_for_date(
                        facility, date, scheduled_times
                    )

                    if availability_info:
                        facility_availability_info.append(availability_info)

            return facility_availability_info

        except Exception as e:
            if isinstance(e, (TypeError, ValueError)):
                raise  # Re-raise validation errors as-is
            raise RuntimeError(f"Error getting facility availability: {e}")

    def _filter_dates_by_facility_availability(
        self, facility: Facility, dates: List[str]
    ) -> Tuple[List[str], List["FacilityAvailabilityInfo"]]:
        """
        Filter dates based on facility availability, splitting into available and unavailable dates.
        This reduces the database query size by filtering out dates that don't need database checks.

        Args:
            facility: Facility object to check
            dates: List of date strings to filter

        Returns:
            Tuple of (available_dates, unavailable_dates_info) where:
            - available_dates: List of dates where facility is available (need DB query)
            - unavailable_dates_info: List of FacilityAvailabilityInfo for unavailable dates
        """
        available_dates = []
        unavailable_dates_info = []

        for date in dates:
            day_name = self._get_day_name_safe(date)

            # Check facility unavailable dates first (fastest check)
            if not facility.is_available_on_date(date):
                unavailable_info = FacilityAvailabilityInfo.create_unavailable(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    date=date,
                    day_of_week=day_name,
                    reason="Facility marked as unavailable",
                )
                unavailable_dates_info.append(unavailable_info)
                continue

            # Check if facility has schedule for this day of week
            try:
                day_schedule = facility.schedule.get_day_schedule(day_name)
                if not day_schedule.start_times:
                    unavailable_info = FacilityAvailabilityInfo.create_unavailable(
                        facility_id=facility.id,
                        facility_name=facility.name,
                        date=date,
                        day_of_week=day_name,
                        reason=f"No time slots available on {day_name}",
                    )
                    unavailable_dates_info.append(unavailable_info)
                    continue
            except ValueError:
                unavailable_info = FacilityAvailabilityInfo.create_unavailable(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    date=date,
                    day_of_week=day_name,
                    reason=f"No schedule available for {day_name}",
                )
                unavailable_dates_info.append(unavailable_info)
                continue

            # If we get here, facility is available and has schedule - needs DB query
            available_dates.append(date)

        return available_dates, unavailable_dates_info

    def _validate_facility_availability_inputs(
        self, facility: Facility, dates: List[str], max_days: int
    ) -> None:
        """
        Validate inputs for facility availability methods

        Args:
            facility: Facility object to validate
            dates: List of date strings to validate
            max_days: Maximum days limit to validate

        Raises:
            TypeError: If facility is wrong type or dates is invalid
            ValueError: If dates format is invalid or too many dates
        """
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")

        if not isinstance(dates, list) or not all(
            isinstance(date, str) for date in dates
        ):
            raise TypeError("dates must be a list of date strings in YYYY-MM-DD format")

        if not dates:
            raise ValueError("dates list cannot be empty")

        # if len(dates) > max_days:
        #     raise ValueError(f"Cannot check more than {max_days} dates at once")

        # Validate all date formats in one pass
        for date in dates:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD")

    def _get_scheduled_times_batch(
        self, facility: Facility, dates: List[str]
    ) -> Dict[str, List[str]]:
        """
        Get scheduled times for multiple dates in a single database query. This method also 
        handles dry run state if enabled, allowing for more efficient batch processing.

        Args:
            facility: Facility object
            dates: List of date strings in YYYY-MM-DD format

        Returns:
            Dictionary mapping date -> list of scheduled times for that date

        Raises:
            RuntimeError: If there is a database error
        """
        try:
            if not dates:
                return {}

            # Build parameterized query for multiple dates
            placeholders = ",".join("?" for _ in dates)
            query = f"""
                SELECT date, scheduled_times 
                FROM matches 
                WHERE facility_id = ? AND date IN ({placeholders}) AND status = 'scheduled'
            """

            # Execute single query with facility_id + all dates
            params = [facility.id] + dates
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()

            # Parse results and group by date
            scheduled_times_by_date = {date: [] for date in dates}

            # Rows is postive only if there are matches in the database
            for row in rows:
                date = row["date"]
                times_json = row["scheduled_times"]

                if times_json:
                    try:
                        import json

                        times = json.loads(times_json)
                        if isinstance(times, list):
                            scheduled_times_by_date[date].extend(times)

                    except (json.JSONDecodeError, TypeError):
                        # Skip invalid JSON, log warning if needed
                        logger.warning(
                            f"Invalid scheduled_times JSON for match on {date}: {times_json}"
                        )
                        continue

            # Extract scheduled times from scheduling_state
            state = self.db.scheduling_state if hasattr(self.db, "scheduling_state") else None

            if state:
                for date in dates:
                    state_dates = state.get_facility_usage(facility.id, date)

                    # add state_dates to the scheduled_times_by_date
                    if state_dates:
                        scheduled_times_by_date[date].extend(state_dates)

            logger.debug(
                f"Retrieved scheduled times for {len(scheduled_times_by_date)} dates for facility {facility.id}"
            )
            # Ensure we only return dates that were requested
            return scheduled_times_by_date

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting scheduled times batch: {e}")
        except Exception as e:
            raise RuntimeError(
                f"Error getting scheduled times for facility {facility.id}: {e}"
            )

    def _get_facility_availability_for_date(
        self, facility: Facility, date: str, scheduled_times: List[str]
    ) -> Optional["FacilityAvailabilityInfo"]:
        """
        Get availability information for a facility on a specific date using pre-fetched scheduled times.

        This method assumes the date has already been pre-filtered for basic facility availability,
        so it focuses on building detailed time slot information.

        Args:
            facility: Facility object to check availability for
            date: Date string in YYYY-MM-DD format (pre-validated as available)
            scheduled_times: Pre-fetched list of scheduled times for this date

        Returns:
            FacilityAvailabilityInfo object (should not be None for pre-filtered dates)

        Raises:
            RuntimeError: If there is an error processing the data
        """
        try:
            # Get day of week and schedule (these should be valid since date was pre-filtered)
            day_name = self._get_day_name_safe(date)
            day_schedule = facility.schedule.get_day_schedule(day_name)

            # Create TimeSlotAvailability objects for each time slot
            time_slot_availabilities = self._build_time_slot_availabilities(
                day_schedule, scheduled_times
            )

            # Create and return the comprehensive availability info
            return FacilityAvailabilityInfo.from_time_slots(
                facility_id=facility.id,
                facility_name=facility.name,
                date=date,
                day_of_week=day_name,
                time_slots=time_slot_availabilities,
            )

        except Exception as e:
            raise RuntimeError(
                f"Error processing facility availability for {date}: {e}"
            )

    def _get_day_name_safe(self, date: str) -> str:
        """
        Safely get day name from date string

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Day name (Monday, Tuesday, etc.) or "Unknown" if parsing fails
        """
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            return date_obj.strftime("%A")
        except ValueError:
            return "Unknown"

    def _build_time_slot_availabilities(
        self, day_schedule: "DaySchedule", scheduled_times: List[str]
    ) -> List["TimeSlotAvailability"]:
        """
        Build TimeSlotAvailability objects for all time slots in a day schedule

        Args:
            day_schedule: DaySchedule object containing time slots
            scheduled_times: List of scheduled times (HH:MM format) for this date

        Returns:
            List of TimeSlotAvailability objects
        """
        time_slot_availabilities = []

        for time_slot in day_schedule.start_times:
            time = time_slot.time
            total_courts = time_slot.available_courts
            used_courts = scheduled_times.count(time)
            
            # Ensure used_courts doesn't exceed total_courts (defensive programming)
            # This can happen if there are data inconsistencies or overbooking
            if used_courts > total_courts:
                logger.warning(
                    f"Over-booking detected: {used_courts} courts used > {total_courts} total courts "
                    f"at time {time}. Capping used_courts to total_courts."
                )
                used_courts = total_courts
            
            available_courts = max(0, total_courts - used_courts)
            utilization_percentage = (
                (used_courts / total_courts * 100) if total_courts > 0 else 0
            )

            slot_availability = TimeSlotAvailability(
                time=time,
                total_courts=total_courts,
                used_courts=used_courts,
                available_courts=available_courts,
                utilization_percentage=round(utilization_percentage, 1),
            )
            time_slot_availabilities.append(slot_availability)

        return time_slot_availabilities

    def calculate_league_facility_requirements(
        self, 
        league: League, 
        include_utilization: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate facility availability requirements for an entire league
        
        Args:
            league_id: ID of the league to analyze
            include_utilization: Whether to include current utilization data
            
        Returns:
            Dictionary containing facility requirement analysis including:
            - total_matches: Total number of matches in the league
            - total_court_hours: Total court-hours needed
            - facilities_used: List of facilities used by teams
            - peak_demand: Peak demand analysis by day/time
            - utilization_analysis: Current utilization if requested
            
        Raises:
            ValueError: If league_id is invalid
            RuntimeError: If there's a database error
        """
        try:
            league = self.db.league_manager.get_league(league.id)
            if not league:
                raise ValueError(f"League with ID {league.id} does not exist")
            
            # Get all teams in the league
            teams = self.db.team_manager.list_teams(league)
            if not teams:
                return {
                    "league_id": league.id,
                    "league_name": league.name,
                    "total_teams": 0,
                    "total_matches": 0,
                    "total_court_hours": 0,
                    "facilities_used": [],
                    "peak_demand": {},
                    "utilization_analysis": {} if include_utilization else None,
                    "recommendations": ["No teams found in league"]
                }
            
            # Calculate match requirements
            total_teams = len(teams)
            matches_per_team = league.num_matches
            total_matches = (total_teams * matches_per_team) // 2  # Each match involves 2 teams
            
            # Calculate court-hour requirements
            lines_per_match = league.num_lines_per_match
            hours_per_match = 2.5  # Standard tennis match duration
            total_court_hours = total_matches * lines_per_match * hours_per_match
            
            # Analyze facilities used by teams
            facilities_analysis = self._analyze_league_facilities(teams, league)
            
            # Calculate peak demand patterns
            peak_demand_analysis = self._calculate_peak_demand(
                league, teams, total_matches, lines_per_match
            )
            
            # Include utilization analysis if requested
            utilization_analysis = None
            if include_utilization:
                utilization_analysis = self._calculate_current_utilization(
                    league, facilities_analysis["facilities_used"]
                )
            
            # Generate recommendations
            recommendations = self._generate_facility_recommendations(
                league, facilities_analysis, peak_demand_analysis, utilization_analysis
            )
            
            return {
                "league_id": league.id,
                "league_name": league.name,
                "total_teams": total_teams,
                "total_matches": total_matches,
                "total_court_hours": total_court_hours,
                "lines_per_match": lines_per_match,
                "matches_per_team": matches_per_team,
                "league_duration_weeks": self._calculate_league_duration_weeks(league),
                "facilities_analysis": facilities_analysis,
                "peak_demand": peak_demand_analysis,
                "utilization_analysis": utilization_analysis,
                "recommendations": recommendations,
                "allow_split_lines": league.allow_split_lines,
                "preferred_days": league.preferred_days,
                "backup_days": league.backup_days
            }
            
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise RuntimeError(f"Error calculating league facility requirements: {e}")
    
    def _analyze_league_facilities(self, teams: List[Team], league: League) -> Dict[str, Any]:
        """Analyze facilities used by teams in the league"""
        facilities_used = {}
        facility_team_count = {}
        geographic_distribution = {}
        
        for team in teams:
            if not team.preferred_facilities:
                continue
            primary_facility = team.get_primary_facility()
            facility_id = primary_facility.id
            facility_name = primary_facility.name
            facility_location = primary_facility.location or "Unknown"
            
            if facility_id not in facilities_used:
                facilities_used[facility_id] = {
                    "facility_id": facility_id,
                    "facility_name": facility_name,
                    "facility_location": facility_location,
                    "total_courts": primary_facility.total_courts,
                    "teams_count": 0,
                    "teams": []
                }
                facility_team_count[facility_id] = 0
            
            facilities_used[facility_id]["teams_count"] += 1
            facilities_used[facility_id]["teams"].append({
                "team_id": team.id,
                "team_name": team.name,
                "preferred_days": team.preferred_days
            })
            facility_team_count[facility_id] += 1
            
            # Track geographic distribution
            if facility_location not in geographic_distribution:
                geographic_distribution[facility_location] = []
            geographic_distribution[facility_location].append(facility_name)
        
        return {
            "facilities_used": list(facilities_used.values()),
            "total_facilities": len(facilities_used),
            "facility_team_count": facility_team_count,
            "geographic_distribution": geographic_distribution,
            "most_used_facility": max(facility_team_count.items(), key=lambda x: x[1])[0] if facility_team_count else None
        }
    
    def _calculate_peak_demand(
        self, 
        league: League, 
        teams: List[Team], 
        total_matches: int, 
        lines_per_match: int
    ) -> Dict[str, Any]:
        """Calculate peak demand patterns for the league"""
        # Analyze preferred days across all teams
        day_preferences = {}
        for team in teams:
            for day in team.preferred_days:
                day_preferences[day] = day_preferences.get(day, 0) + 1
        
        # Consider league preferred days
        league_preferred_days = league.preferred_days or []
        league_backup_days = league.backup_days or []
        
        # Calculate demand distribution
        available_days = league_preferred_days + league_backup_days
        if not available_days:
            available_days = ["Saturday", "Sunday"]  # Default weekend play
        
        # Estimate matches per week based on league duration
        league_duration_weeks = self._calculate_league_duration_weeks(league)
        matches_per_week = total_matches / max(league_duration_weeks, 1)
        
        # Calculate courts needed per day
        courts_needed_per_day = {}
        for day in available_days:
            # Weight by team preferences
            preference_weight = day_preferences.get(day, 0) / len(teams) if teams else 0
            base_demand = matches_per_week * lines_per_match / len(available_days)
            adjusted_demand = base_demand * (1 + preference_weight)
            courts_needed_per_day[day] = round(adjusted_demand, 1)
        
        return {
            "matches_per_week": round(matches_per_week, 1),
            "courts_needed_per_day": courts_needed_per_day,
            "peak_day": max(courts_needed_per_day.items(), key=lambda x: x[1])[0] if courts_needed_per_day else None,
            "team_day_preferences": day_preferences,
            "league_preferred_days": league_preferred_days,
            "league_backup_days": league_backup_days
        }
    
    def _calculate_current_utilization(
        self, 
        league: League, 
        facilities_used: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate current utilization of facilities used by the league based on court-time slots"""
        utilization_data = {}
        
        try:
            # Get scheduled matches for this league
            self.cursor.execute(
                "SELECT facility_id, date, scheduled_times FROM matches WHERE league_id = ? AND status = 'scheduled'",
                (league.id,)
            )
            matches = self.cursor.fetchall()
            
            # Count usage by facility
            facility_usage = {}
            for match in matches:
                facility_id = match["facility_id"]
                if facility_id:
                    if facility_id not in facility_usage:
                        facility_usage[facility_id] = 0
                    
                    # Count scheduled times (each scheduled time represents one court-time slot used)
                    if match["scheduled_times"]:
                        try:
                            times = json.loads(match["scheduled_times"])
                            if isinstance(times, list):
                                facility_usage[facility_id] += len(times)
                            else:
                                facility_usage[facility_id] += 1
                        except (json.JSONDecodeError, TypeError):
                            facility_usage[facility_id] += 1
            
            # Calculate utilization for each facility
            for facility_info in facilities_used:
                facility_id = facility_info["facility_id"]
                current_usage = facility_usage.get(facility_id, 0)
                
                # Get the facility to calculate total available court-time slots
                facility = self.get_facility(facility_id)
                if not facility:
                    continue
                
                # Calculate total available court-time slots
                total_court_time_slots = self._calculate_total_court_time_slots(facility, league)
                
                utilization_data[str(facility_id)] = {
                    "facility_name": facility_info["facility_name"],
                    "total_court_time_slots": total_court_time_slots,
                    "current_usage": current_usage,
                    "utilization_percentage": (current_usage / max(total_court_time_slots, 1) * 100) if total_court_time_slots > 0 else 0
                }
        
        except sqlite3.Error as e:
            logger.warning(f"Error calculating utilization: {e}")
            utilization_data = {"error": str(e)}
        
        return utilization_data
    
    def calculate_total_facility_utilization(self, facility: Facility) -> Dict[str, Any]:
        """
        Calculate total facility utilization across all leagues.
        
        Args:
            facility: The facility to calculate utilization for
            
        Returns:
            Dictionary containing total utilization data including:
            - total_court_time_slots: Total slots available across all leagues
            - current_usage: Total slots used across all leagues
            - utilization_percentage: Overall utilization percentage
            - league_breakdown: Per-league utilization data
        """
        try:
            # Get all leagues that have teams using this facility
            all_leagues = self.db.list_leagues()
            leagues_using_facility = []
            total_usage = 0
            total_slots = 0
            league_breakdown = {}
            
            for league in all_leagues:
                teams = self.db.list_teams(league)
                facility_teams = [team for team in teams if team.preferred_facilities and any(f.id == facility.id for f in team.preferred_facilities)]
                
                if facility_teams:
                    leagues_using_facility.append(league)
                    
                    # Calculate slots for this league
                    league_slots = self._calculate_total_court_time_slots(facility, league)
                    total_slots += league_slots
                    
                    # Calculate usage for this league
                    self.cursor.execute(
                        "SELECT scheduled_times FROM matches WHERE league_id = ? AND facility_id = ? AND status = 'scheduled'",
                        (league.id, facility.id)
                    )
                    matches = self.cursor.fetchall()
                    
                    league_usage = 0
                    for match in matches:
                        if match["scheduled_times"]:
                            try:
                                times = json.loads(match["scheduled_times"])
                                if isinstance(times, list):
                                    league_usage += len(times)
                                else:
                                    league_usage += 1
                            except (json.JSONDecodeError, TypeError):
                                league_usage += 1
                    
                    total_usage += league_usage
                    league_breakdown[league.id] = {
                        "league_name": league.name,
                        "total_slots": league_slots,
                        "usage": league_usage,
                        "utilization_percentage": (league_usage / max(league_slots, 1) * 100) if league_slots > 0 else 0
                    }
            
            # Calculate overall utilization
            overall_utilization = (total_usage / max(total_slots, 1) * 100) if total_slots > 0 else 0
            
            return {
                "total_court_time_slots": total_slots,
                "current_usage": total_usage,
                "utilization_percentage": overall_utilization,
                "active_leagues": len(leagues_using_facility),
                "league_breakdown": league_breakdown
            }
            
        except Exception as e:
            logger.warning(f"Error calculating total facility utilization: {e}")
            return {
                "total_court_time_slots": 0,
                "current_usage": 0,
                "utilization_percentage": 0,
                "active_leagues": 0,
                "league_breakdown": {},
                "error": str(e)
            }
    
    def _calculate_total_court_time_slots(self, facility: Facility, league: League) -> int:
        """
        Calculate the total number of court-time slots available at a facility during the league timeframe.
        
        This considers:
        - The facility's weekly schedule (days and times with available courts)
        - The league's duration
        - The league's preferred/backup days
        - The facility's unavailable dates
        
        Args:
            facility: The facility to calculate slots for
            league: The league to calculate slots within
            
        Returns:
            Total number of court-time slots available
        """
        try:
            # Get league duration in weeks
            league_duration_weeks = self._calculate_league_duration_weeks(league)
            
            # Get days that this league can use
            league_days = league.preferred_days or []
            if league.backup_days:
                league_days.extend(league.backup_days)
            
            # If no specific days, assume all days are available
            if not league_days:
                league_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            # Calculate total court-time slots per week
            weekly_slots = 0
            for day_name in league_days:
                try:
                    day_schedule = facility.schedule.get_day_schedule(day_name)
                    for time_slot in day_schedule.start_times:
                        weekly_slots += time_slot.available_courts
                except ValueError:
                    # No schedule for this day, skip
                    continue
            
            # Calculate total slots for the league duration
            total_slots = weekly_slots * league_duration_weeks
            
            # Account for unavailable dates (rough estimate)
            # This is a simplified calculation - in reality you'd need to check specific dates
            unavailable_days = len(facility.unavailable_dates or [])
            if unavailable_days > 0:
                # Estimate how many slots would be lost due to unavailable dates
                # Assume unavailable dates are distributed across the league timeframe
                avg_daily_slots = weekly_slots / 7 if weekly_slots > 0 else 0
                lost_slots = unavailable_days * avg_daily_slots
                total_slots = max(0, total_slots - lost_slots)
            
            return int(total_slots)
            
        except Exception as e:
            logger.warning(f"Error calculating total court-time slots for facility {facility.id}: {e}")
            return 0
    
    def _calculate_league_duration_weeks(self, league: League) -> int:
        """Calculate the duration of the league in weeks"""
        if league.start_date and league.end_date:
            try:
                start = datetime.strptime(league.start_date, "%Y-%m-%d")
                end = datetime.strptime(league.end_date, "%Y-%m-%d")
                duration_days = (end - start).days
                return max(duration_days // 7, 1)
            except ValueError:
                pass
        
        # Default assumption: 12 weeks for a typical league season
        return 12
    
    def _generate_facility_recommendations(
        self, 
        league: League, 
        facilities_analysis: Dict[str, Any], 
        peak_demand_analysis: Dict[str, Any],
        utilization_analysis: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations for facility requirements"""
        recommendations = []
        
        # Check facility distribution
        total_facilities = facilities_analysis["total_facilities"]
        total_teams = len(facilities_analysis["facilities_used"])
        
        if total_facilities < 2:
            recommendations.append("Consider adding more facilities to reduce travel and scheduling conflicts")
        
        # Check peak demand
        peak_courts_needed = max(peak_demand_analysis["courts_needed_per_day"].values()) if peak_demand_analysis["courts_needed_per_day"] else 0
        
        if peak_courts_needed > 10:
            recommendations.append(f"Peak demand of {peak_courts_needed} courts may require careful scheduling coordination")
        
        # Check geographic distribution
        geographic_dist = facilities_analysis["geographic_distribution"]
        if len(geographic_dist) == 1:
            recommendations.append("All facilities are in the same location - consider geographic diversity")
        
        # Check utilization if available
        if utilization_analysis and "error" not in utilization_analysis:
            high_utilization_facilities = [
                f["facility_name"] for f in utilization_analysis.values() 
                if isinstance(f, dict) and f.get("utilization_percentage", 0) > 80
            ]
            if high_utilization_facilities:
                recommendations.append(f"High utilization facilities may need additional capacity: {', '.join(high_utilization_facilities)}")
        
        # Check split lines capability
        if not league.allow_split_lines and peak_courts_needed > 5:
            recommendations.append("Consider enabling split lines to improve scheduling flexibility")
        
        # Day distribution recommendations
        preferred_days = league.preferred_days or []
        if len(preferred_days) < 2:
            recommendations.append("Consider adding more preferred days to distribute scheduling load")
        
        return recommendations if recommendations else ["Facility requirements appear adequate for current league configuration"]
    
    def calculate_per_day_utilization(self, 
                                      facility: Facility, 
                                      start_date: Optional[datetime]=None, 
                                      end_date: Optional[datetime]=None) -> Dict[str, float]:
        """
        Calculate the per-day facility utilization for a specific facility.

        Args:
            facility: The facility to analyze.
            start_date: Optional start date for the analysis period (default is first match date).
            end_date: Optional end date for the analysis period (default is last match date).

        Returns:
            A dictionary mapping each day of the week to its utilization percentage.
        """
        # Initialize utilization dictionary with zero values
        utilization = {day: 0.0 for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}

        try:
            # Query the database to get the first match scheduled to the facility
            if not start_date:
                start_date = self._get_first_scheduled_match_date(facility)

            if not end_date:
                end_date = self._get_last_scheduled_match_date(facility)

            if not start_date or not end_date:
                logger.info(f"No matches found for facility {facility.id}.")
                return utilization
            
            # Generate list of dates between start_date and end_date
            date_list = []
            current_date = start_date
            while current_date <= end_date:
                date_list.append(current_date.strftime("%Y-%m-%d"))
                current_date += timedelta(days=1)
            
            # Use get_facility_availability to get all available dates with utilization info
            facility_availability = self.get_facility_availability(
                facility=facility,
                dates=date_list,
                max_days=365  # Limit to one year for performance
            )

            # Aggregate utilization data by day of week
            day_totals = {day: {'total_slots': 0, 'used_slots': 0} for day in utilization.keys()}
            
            for availability_info in facility_availability:
                if availability_info.available and availability_info.total_court_slots > 0:
                    day_name = availability_info.day_of_week
                    day_totals[day_name]['total_slots'] += availability_info.total_court_slots
                    day_totals[day_name]['used_slots'] += availability_info.used_court_slots
            
            # Calculate utilization percentage for each day
            for day in utilization.keys():
                total = day_totals[day]['total_slots']
                used = day_totals[day]['used_slots']
                if total > 0:
                    utilization[day] = (used / total) * 100
                else:
                    utilization[day] = 0.0

            return utilization
            
        except Exception as e:
            logger.error(f"Error calculating per-day utilization for facility {facility.id}: {e}")
            return utilization
    
    def _get_first_scheduled_match_date(self, facility: Facility) -> Optional[datetime]:
        """Get the date of the first scheduled match at this facility"""
        try:
            self.cursor.execute(
                "SELECT MIN(date) as first_date FROM matches WHERE facility_id = ? AND status = 'scheduled'",
                (facility.id,)
            )
            row = self.cursor.fetchone()
            if row and row['first_date']:
                return datetime.strptime(row['first_date'], "%Y-%m-%d")
            return None
        except Exception as e:
            logger.error(f"Error getting first scheduled match date for facility {facility.id}: {e}")
            return None
    
    def _get_last_scheduled_match_date(self, facility: Facility) -> Optional[datetime]:
        """Get the date of the last scheduled match at this facility"""
        try:
            self.cursor.execute(
                "SELECT MAX(date) as last_date FROM matches WHERE facility_id = ? AND status = 'scheduled'",
                (facility.id,)
            )
            row = self.cursor.fetchone()
            if row and row['last_date']:
                return datetime.strptime(row['last_date'], "%Y-%m-%d")
            return None
        except Exception as e:
            logger.error(f"Error getting last scheduled match date for facility {facility.id}: {e}")
            return None
