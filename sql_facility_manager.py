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
from datetime import datetime, timedelta, date

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
        self, facility: Facility, dates: List[date], max_days: int = 50
    ) -> List["FacilityAvailabilityInfo"]:
        """
        Get availability information for a facility over a list of dates.

        Args:
            facility: Facility object to check availability for
            dates: List of date objects to check
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

                for date_obj in available_dates:
                    # Get scheduled times for this specific date (from batch query)
                    scheduled_times = scheduled_times_by_date.get(date_obj, [])

                    # Get availability for this date using cached scheduled times
                    availability_info = self._get_facility_availability_for_date(
                        facility, date_obj, scheduled_times
                    )

                    if availability_info:
                        facility_availability_info.append(availability_info)

            return facility_availability_info

        except Exception as e:
            if isinstance(e, (TypeError, ValueError)):
                raise  # Re-raise validation errors as-is
            raise RuntimeError(f"Error getting facility availability: {e}")

    def _filter_dates_by_facility_availability(
        self, facility: Facility, dates: List[date]
    ) -> Tuple[List[date], List["FacilityAvailabilityInfo"]]:
        """
        Filter dates based on facility availability, splitting into available and unavailable dates.
        This reduces the database query size by filtering out dates that don't need database checks.

        Args:
            facility: Facility object to check
            dates: List of date objects to filter

        Returns:
            Tuple of (available_dates, unavailable_dates_info) where:
            - available_dates: List of date objects where facility is available (need DB query)
            - unavailable_dates_info: List of FacilityAvailabilityInfo for unavailable dates
        """
        available_dates = []
        unavailable_dates_info = []

        for date_obj in dates:
            # Convert date object to string for day name calculation and FacilityAvailabilityInfo
            date_str = date_obj.strftime('%Y-%m-%d')
            day_name = date_obj.strftime("%A")

            # Check facility unavailable dates first (fastest check)
            if not facility.is_available_on_date(date_obj):
                unavailable_info = FacilityAvailabilityInfo.create_unavailable(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    match_date=date_obj,
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
                        match_date=date_obj,
                        day_of_week=day_name,
                        reason=f"No time slots available on {day_name}",
                    )
                    unavailable_dates_info.append(unavailable_info)
                    continue
            except ValueError:
                unavailable_info = FacilityAvailabilityInfo.create_unavailable(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    match_date=date_obj,
                    day_of_week=day_name,
                    reason=f"No schedule available for {day_name}",
                )
                unavailable_dates_info.append(unavailable_info)
                continue

            # If we get here, facility is available and has schedule - needs DB query
            available_dates.append(date_obj)

        return available_dates, unavailable_dates_info

    def _validate_facility_availability_inputs(
        self, facility: Facility, dates: List[date], max_days: int
    ) -> None:
        """
        Validate inputs for facility availability methods

        Args:
            facility: Facility object to validate
            dates: List of date objects to validate
            max_days: Maximum days limit to validate

        Raises:
            TypeError: If facility is wrong type or dates is invalid
            ValueError: If dates list is empty or too many dates
        """
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")

        if not isinstance(dates, list) or not all(
            isinstance(date_obj, date) for date_obj in dates
        ):
            raise TypeError("dates must be a list of date objects")

        if not dates:
            raise ValueError("dates list cannot be empty")

        # if len(dates) > max_days:
        #     raise ValueError(f"Cannot check more than {max_days} dates at once")

        # Date objects are already validated by their type, no need for format validation

    def _get_scheduled_times_batch(
        self, facility: Facility, dates: List[date]
    ) -> Dict[date, List[str]]:
        """
        Get scheduled times for multiple dates in a single database query. This method also 
        handles dry run state if enabled, allowing for more efficient batch processing.

        Args:
            facility: Facility object
            dates: List of date objects

        Returns:
            Dictionary mapping date -> list of scheduled times for that date

        Raises:
            RuntimeError: If there is a database error
        """
        try:
            if not dates:
                return {}

            # Convert date objects to strings for database query
            date_strings = [date_obj.strftime('%Y-%m-%d') for date_obj in dates]
            
            # Build parameterized query for multiple dates
            placeholders = ",".join("?" for _ in date_strings)
            query = f"""
                SELECT date, scheduled_times 
                FROM matches 
                WHERE facility_id = ? AND date IN ({placeholders}) AND status = 'scheduled'
            """

            # Execute single query with facility_id + all date strings
            params = [facility.id] + date_strings
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()

            # Parse results and group by date (using original date objects as keys)
            scheduled_times_by_date = {date_obj: [] for date_obj in dates}

            # Rows is positive only if there are matches in the database
            for row in rows:
                date_str = row["date"]
                times_json = row["scheduled_times"]
                
                # Find the corresponding date object for this date string
                date_obj = next((d for d in dates if d.strftime('%Y-%m-%d') == date_str), None)
                if not date_obj:
                    continue

                if times_json:
                    try:
                        import json

                        times = json.loads(times_json)
                        if isinstance(times, list):
                            scheduled_times_by_date[date_obj].extend(times)

                    except (json.JSONDecodeError, TypeError):
                        # Skip invalid JSON, log warning if needed
                        logger.warning(
                            f"Invalid scheduled_times JSON for match on {date}: {times_json}"
                        )
                        continue

            # In dry run mode, use scheduling state instead of database to avoid double-counting
            # The scheduling state is initialized from database and then updated with new bookings
            if hasattr(self.db, "dry_run_active") and self.db.dry_run_active and self.db.scheduling_state:
                # In dry run mode, replace database results with scheduling state
                for date_obj in dates:
                    date_str = date_obj.strftime('%Y-%m-%d')
                    state_dates = self.db.scheduling_state.get_facility_usage(facility.id, date_str)
                    scheduled_times_by_date[date_obj] = state_dates  # Replace, don't extend

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
        self, facility: Facility, date_obj: date, scheduled_times: List[str]
    ) -> Optional["FacilityAvailabilityInfo"]:
        """
        Get availability information for a facility on a specific date using pre-fetched scheduled times.

        This method assumes the date has already been pre-filtered for basic facility availability,
        so it focuses on building detailed time slot information.

        Args:
            facility: Facility object to check availability for
            date_obj: Date object (pre-validated as available)
            scheduled_times: Pre-fetched list of scheduled times for this date

        Returns:
            FacilityAvailabilityInfo object (should not be None for pre-filtered dates)

        Raises:
            RuntimeError: If there is an error processing the data
        """
        try:
            # Convert date object to string for FacilityAvailabilityInfo
            date_str = date_obj.strftime('%Y-%m-%d')
            day_name = date_obj.strftime("%A")
            
            # Get day schedule (should be valid since date was pre-filtered)
            day_schedule = facility.schedule.get_day_schedule(day_name)

            # Create TimeSlotAvailability objects for each time slot
            time_slot_availabilities = self._build_time_slot_availabilities(
                day_schedule, scheduled_times
            )

            # Create and return the comprehensive availability info
            return FacilityAvailabilityInfo.from_time_slots(
                facility_id=facility.id,
                facility_name=facility.name,
                match_date=date_obj,
                day_of_week=day_name,
                time_slots=time_slot_availabilities,
            )

        except Exception as e:
            raise RuntimeError(
                f"Error processing facility availability for {date_obj}: {e}"
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

    def facility_statistics(self, 
                          facility: Facility, 
                          league: Optional[League] = None,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None,
                          include_league_breakdown: bool = True,
                          include_per_day_utilization: bool = True,
                          include_peak_demand: bool = True,
                          include_requirements: bool = True) -> Dict[str, Any]:
        """
        Unified method for calculating comprehensive facility statistics.
        
        This method consolidates all facility statistics calculations to eliminate
        redundancy and provide a single source of truth for facility metrics.
        
        Args:
            facility: The facility to analyze
            league: Optional specific league to analyze (if None, analyzes all leagues)
            start_date: Optional start date for analysis period
            end_date: Optional end date for analysis period
            include_league_breakdown: Whether to include per-league utilization data
            include_per_day_utilization: Whether to include day-of-week utilization
            include_peak_demand: Whether to include peak demand analysis
            include_requirements: Whether to include facility requirements analysis
            
        Returns:
            Comprehensive dictionary containing all requested facility statistics
        """
        try:
            # Core facility info
            stats = {
                "facility_id": facility.id,
                "facility_name": facility.name,
                "total_courts": facility.total_courts,
                "analysis_period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }
            
            # Determine date range if not provided
            if not start_date:
                start_date = self._get_first_scheduled_match_date(facility)
            if not end_date:
                end_date = self._get_last_scheduled_match_date(facility)
                
            if not start_date or not end_date:
                # No matches scheduled, return basic stats with consistent structure
                stats.update({
                    "total_utilization": 0.0,
                    "total_scheduled_matches": 0,
                    "total_court_hours_used": 0,
                    "total_time_slots_used": 0,
                    "total_available_slots": self._calculate_total_available_slots_basic(facility),
                    "unique_dates_with_matches": 0,
                    "active_leagues": 0,
                    "message": "No scheduled matches found for this facility"
                })
                
                # Add empty structures for requested sections
                if include_league_breakdown:
                    stats["league_breakdown"] = {}
                if include_per_day_utilization:
                    stats["per_day_utilization"] = {day: 0.0 for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
                if include_peak_demand:
                    stats["peak_demand"] = {}
                if include_requirements:
                    stats["facility_requirements"] = {}
                    
                return stats
            
            # Update analysis period in stats
            stats["analysis_period"].update({
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "duration_days": (end_date - start_date).days + 1
            })
            
            # Calculate core utilization metrics
            core_metrics = self._calculate_core_utilization_metrics(
                facility, league, start_date, end_date
            )
            stats.update(core_metrics)
            
            # Add league breakdown if requested
            if include_league_breakdown:
                stats["league_breakdown"] = self._calculate_league_breakdown_stats(
                    facility, start_date, end_date, league
                )
                
            # Add per-day utilization if requested
            if include_per_day_utilization:
                stats["per_day_utilization"] = self._calculate_per_day_stats(
                    facility, start_date, end_date
                )
                
            # Add peak demand analysis if requested
            if include_peak_demand and league:
                stats["peak_demand"] = self._calculate_peak_demand_stats(
                    facility, league
                )
                
            # Add facility requirements if requested
            if include_requirements and league:
                stats["facility_requirements"] = self._calculate_facility_requirements_stats(
                    facility, league
                )
                
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating facility statistics: {e}")
            return {
                "facility_id": facility.id,
                "facility_name": facility.name,
                "error": str(e),
                "total_utilization": 0.0
            }
    
    def _calculate_core_utilization_metrics(self, 
                                          facility: Facility, 
                                          league: Optional[League],
                                          start_date: datetime,
                                          end_date: datetime) -> Dict[str, Any]:
        """Calculate core utilization metrics for a facility"""
        # Get all scheduled matches for this facility in the date range
        if league:
            self.cursor.execute("""
                SELECT scheduled_times, date, league_id 
                FROM matches 
                WHERE facility_id = ? AND league_id = ? AND status = 'scheduled'
                AND date BETWEEN ? AND ?
            """, (facility.id, league.id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        else:
            self.cursor.execute("""
                SELECT scheduled_times, date, league_id 
                FROM matches 
                WHERE facility_id = ? AND status = 'scheduled'
                AND date BETWEEN ? AND ?
            """, (facility.id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
        
        matches = self.cursor.fetchall()
        
        total_court_hours_used = 0
        total_time_slots_used = 0
        unique_dates = set()
        active_leagues = set()
        
        for match in matches:
            if match["scheduled_times"]:
                unique_dates.add(match["date"])
                active_leagues.add(match["league_id"])
                try:
                    times = json.loads(match["scheduled_times"])
                    if isinstance(times, list):
                        total_time_slots_used += len(times)
                        total_court_hours_used += len(times) * 2.5  # Standard match duration
                    else:
                        total_time_slots_used += 1
                        total_court_hours_used += 2.5
                except (json.JSONDecodeError, TypeError):
                    total_time_slots_used += 1
                    total_court_hours_used += 2.5
        
        # Calculate total available slots in the period
        total_available_slots = self._calculate_total_available_slots(
            facility, start_date, end_date, league
        )
        
        # Calculate utilization percentage
        utilization_percentage = (total_time_slots_used / max(total_available_slots, 1)) * 100 if total_available_slots > 0 else 0
        
        return {
            "total_utilization": round(utilization_percentage, 2),
            "total_scheduled_matches": len(matches),
            "total_court_hours_used": round(total_court_hours_used, 1),
            "total_time_slots_used": total_time_slots_used,
            "total_available_slots": total_available_slots,
            "unique_dates_with_matches": len(unique_dates),
            "active_leagues": len(active_leagues)
        }
    
    def _calculate_league_breakdown_stats(self, 
                                        facility: Facility,
                                        start_date: datetime,
                                        end_date: datetime,
                                        target_league: Optional[League] = None) -> Dict[str, Any]:
        """Calculate per-league breakdown statistics"""
        leagues = [target_league] if target_league else self.db.list_leagues()
        breakdown = {}
        
        for league in leagues:
            if not league:
                continue
                
            # Get teams using this facility for this league
            teams = self.db.list_teams(league)
            facility_teams = [team for team in teams if team.preferred_facilities and 
                            any(f.id == facility.id for f in team.preferred_facilities)]
            
            if not facility_teams:
                continue
                
            # Calculate league-specific metrics
            league_slots = self._calculate_total_court_time_slots(facility, league)
            
            self.cursor.execute("""
                SELECT scheduled_times FROM matches 
                WHERE league_id = ? AND facility_id = ? AND status = 'scheduled'
                AND date BETWEEN ? AND ?
            """, (league.id, facility.id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
            
            matches = self.cursor.fetchall()
            league_usage = 0
            
            for match in matches:
                if match["scheduled_times"]:
                    try:
                        times = json.loads(match["scheduled_times"])
                        league_usage += len(times) if isinstance(times, list) else 1
                    except (json.JSONDecodeError, TypeError):
                        league_usage += 1
            
            breakdown[league.id] = {
                "league_name": league.name,
                "teams_using_facility": len(facility_teams),
                "total_available_slots": league_slots,
                "slots_used": league_usage,
                "utilization_percentage": round((league_usage / max(league_slots, 1)) * 100, 2),
                "matches_scheduled": len(matches)
            }
        
        return breakdown
    
    def _calculate_per_day_stats(self, 
                               facility: Facility,
                               start_date: datetime,
                               end_date: datetime) -> Dict[str, float]:
        """Calculate utilization statistics by day of week"""
        # Generate list of dates in the range
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
        
        # Get facility availability for all dates
        facility_availability = self.get_facility_availability(
            facility=facility,
            dates=date_list[:365]  # Limit for performance
        )
        
        # Aggregate by day of week
        day_totals = {day: {'total_slots': 0, 'used_slots': 0} 
                     for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
        
        for availability_info in facility_availability:
            if availability_info.available and availability_info.total_court_slots > 0:
                day_name = availability_info.day_of_week
                day_totals[day_name]['total_slots'] += availability_info.total_court_slots
                day_totals[day_name]['used_slots'] += availability_info.used_court_slots
        
        # Calculate utilization percentages
        utilization = {}
        for day in day_totals:
            total = day_totals[day]['total_slots']
            used = day_totals[day]['used_slots']
            utilization[day] = round((used / total) * 100, 2) if total > 0 else 0.0
        
        return utilization
    
    def _calculate_peak_demand_stats(self, facility: Facility, league: League) -> Dict[str, Any]:
        """Calculate peak demand analysis for a league at a facility"""
        teams = self.db.list_teams(league)
        total_teams = len(teams)
        matches_per_team = league.num_matches
        total_matches = (total_teams * matches_per_team) // 2
        lines_per_match = league.num_lines_per_match
        
        # Estimate peak demand patterns
        league_days = league.preferred_days or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        peak_demand_per_day = total_matches / len(league_days) if league_days else 0
        peak_courts_needed = peak_demand_per_day * lines_per_match
        
        return {
            "total_matches": total_matches,
            "peak_demand_per_day": round(peak_demand_per_day, 1),
            "peak_courts_needed": round(peak_courts_needed, 1),
            "league_preferred_days": league_days,
            "lines_per_match": lines_per_match
        }
    
    def _calculate_facility_requirements_stats(self, facility: Facility, league: League) -> Dict[str, Any]:
        """Calculate facility requirements for a specific league"""
        teams = self.db.list_teams(league)
        total_teams = len(teams)
        matches_per_team = league.num_matches
        total_matches = (total_teams * matches_per_team) // 2
        lines_per_match = league.num_lines_per_match
        hours_per_match = 2.5
        total_court_hours = total_matches * lines_per_match * hours_per_match
        
        return {
            "total_teams": total_teams,
            "total_matches": total_matches,
            "total_court_hours_needed": round(total_court_hours, 1),
            "lines_per_match": lines_per_match,
            "matches_per_team": matches_per_team,
            "league_duration_weeks": self._calculate_league_duration_weeks(league)
        }
    
    def _calculate_total_available_slots(self, 
                                       facility: Facility,
                                       start_date: datetime,
                                       end_date: datetime,
                                       league: Optional[League] = None) -> int:
        """Calculate total available time slots for a facility in a date range"""
        if league:
            return self._calculate_total_court_time_slots(facility, league)
        
        # For general calculation without specific league
        total_slots = 0
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            day_name = current_date.strftime("%A")
            
            # Get schedule for this day
            if facility.schedule and hasattr(facility.schedule, day_name.lower()):
                day_schedule = getattr(facility.schedule, day_name.lower())
                if day_schedule and day_schedule.start_times:
                    total_slots += len(day_schedule.start_times) * facility.total_courts
            
            current_date += timedelta(days=1)
        
        return total_slots
    
    def _calculate_total_available_slots_basic(self, facility: Facility) -> int:
        """Calculate basic total available slots for a facility without date constraints"""
        try:
            total_slots = 0
            # Calculate weekly capacity
            for day_name, day_schedule in facility.schedule.get_all_days().items():
                for time_slot in day_schedule.start_times:
                    total_slots += time_slot.available_courts
            
            # Assume 52 weeks per year as baseline capacity
            return total_slots * 52
            
        except Exception as e:
            logger.warning(f"Error calculating basic total slots for facility {facility.id}: {e}")
            return 0

    def calculate_league_facility_requirements(
        self, 
        league: League, 
        include_utilization: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate facility availability requirements for an entire league
        
        This method now uses the unified facility_statistics method to eliminate redundancy.
        
        Args:
            league: League to analyze
            include_utilization: Whether to include current utilization data
            
        Returns:
            Dictionary containing facility requirement analysis
            
        Raises:
            ValueError: If league is invalid
            RuntimeError: If there's a database error
        """
        try:
            # Validate league
            if not league or not self.db.league_manager.get_league(league.id):
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
            
            # Analyze facilities used by teams
            facilities_analysis = self._analyze_league_facilities(teams, league)
            
            # For each facility, get comprehensive stats using the unified method
            all_facility_stats = {}
            for facility_info in facilities_analysis["facilities_used"]:
                facility = self.get_facility(facility_info["facility_id"])
                if facility:
                    stats = self.facility_statistics(
                        facility=facility,
                        league=league,
                        include_league_breakdown=include_utilization,
                        include_per_day_utilization=False,
                        include_peak_demand=True,
                        include_requirements=True
                    )
                    all_facility_stats[facility.id] = stats
            
            # Aggregate results from unified statistics
            total_matches = sum(stats.get("facility_requirements", {}).get("total_matches", 0) 
                              for stats in all_facility_stats.values())
            total_court_hours = sum(stats.get("total_court_hours_used", 0) 
                                  for stats in all_facility_stats.values())
            
            # Use existing helper methods for peak demand and recommendations
            peak_demand_analysis = self._calculate_peak_demand(
                league, teams, total_matches, league.num_lines_per_match
            )
            
            utilization_analysis = None
            if include_utilization:
                utilization_analysis = self._calculate_current_utilization(
                    league, facilities_analysis["facilities_used"]
                )
            
            recommendations = self._generate_facility_recommendations(
                league, facilities_analysis, peak_demand_analysis, utilization_analysis
            )
            
            return {
                "league_id": league.id,
                "league_name": league.name,
                "total_teams": len(teams),
                "total_matches": total_matches or ((len(teams) * league.num_matches) // 2),
                "total_court_hours": total_court_hours or (total_matches * league.num_lines_per_match * 2.5),
                "lines_per_match": league.num_lines_per_match,
                "matches_per_team": league.num_matches,
                "league_duration_weeks": self._calculate_league_duration_weeks(league),
                "facilities_analysis": facilities_analysis,
                "facility_statistics": all_facility_stats,  # Detailed per-facility stats
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
