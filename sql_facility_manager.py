"""
Facility Management Helper for SQLite Tennis Database

Handles all facility-related database operations including CRUD operations,
facility schedules, availability, and utilization tracking.

Updated to work without Line class - uses match scheduled_times instead.
Added get_available_dates API for finding available dates for matches.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from usta import Facility, WeeklySchedule, DaySchedule, TimeSlot, FacilityAvailabilityInfo, TimeSlotAvailability

# Logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

class SQLFacilityManager:
    """Helper class for managing facility operations in SQLite database"""
    
    def __init__(self, cursor: sqlite3.Cursor):
        """
        Initialize SQLFacilityManager
        
        Args:
            cursor: SQLite cursor for database operations
        """
        self.cursor = cursor
    
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
            self.cursor.execute("""
                INSERT INTO facilities (id, name, short_name, location, total_courts)
                VALUES (?, ?, ?, ?, ?)
            """, (
                facility.id,
                facility.name,
                facility.short_name,
                facility.location,
                facility.total_courts
            ))
            
            # Insert schedule data
            self._insert_facility_schedule(facility, facility.schedule)
            
            # Insert unavailable dates
            self._insert_facility_unavailable_dates(facility, facility.unavailable_dates)
            
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding facility: {e}")
        return True

    def get_facility(self, facility_id: int) -> Optional[Facility]:
        """Get a facility by ID"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Get basic facility info
            self.cursor.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            facility_data = self._dictify(row)
            
            # Create basic facility (including short_name)
            facility = Facility(
                id=facility_data['id'],
                name=facility_data['name'],
                short_name=facility_data['short_name'],
                location=facility_data['location'],
                total_courts=facility_data['total_courts']
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
            self.cursor.execute("""
                UPDATE facilities 
                SET name = ?, short_name = ?, location = ?, total_courts = ?
                WHERE id = ?
            """, (
                facility.name,
                facility.short_name,
                facility.location,
                facility.total_courts,
                facility.id
            ))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update facility {facility.id}")
            
            # Update schedule data (clear and re-insert)
            self._insert_facility_schedule(facility.id, facility.schedule)
            
            # Update unavailable dates (clear and re-insert)
            self._insert_facility_unavailable_dates(facility.id, facility.unavailable_dates)
            
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
            self.cursor.execute("SELECT COUNT(*) as count FROM teams WHERE home_facility_id = ?", (facility_id,))
            team_count = self.cursor.fetchone()['count']
            if team_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {team_count} team(s)")
            
            # Check if facility is referenced by matches
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE facility_id = ?", (facility_id,))
            match_count = self.cursor.fetchone()['count']
            if match_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {match_count} match(es)")
            
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
                        row_data['id'], row_data['name'], row_data.get('short_name'), row_data['location'], row_data['total_courts']
                    )
                    
                    # Create facility with basic info and default schedule
                    facility = Facility(
                        id=row_data['id'],
                        name=row_data['name'],
                        short_name=row_data.get('short_name'),
                        location=row_data['location'],
                        total_courts=row_data['total_courts'],
                        schedule=WeeklySchedule(),  # Ensure we have a valid schedule
                        unavailable_dates=[]  # Initialize with empty list
                    )
    
                    # Load schedule data separately with error handling
                    logger.debug("Loading schedule for facility id=%s", facility.id)
                    try:
                        loaded_schedule = self._load_facility_schedule(facility)
                        if loaded_schedule and isinstance(loaded_schedule, WeeklySchedule):
                            facility.schedule = loaded_schedule
                            logger.debug("Schedule loaded successfully for facility id=%s", facility.id)
                        else:
                            logger.warning("Invalid schedule returned for facility id=%s, using default", facility.id)
                            facility.schedule = WeeklySchedule()
                    except Exception as schedule_error:
                        logger.error("Error loading schedule for facility id=%s: %s", facility.id, schedule_error)
                        facility.schedule = WeeklySchedule()  # Use default empty schedule
    
                    # Load unavailable dates with error handling
                    logger.debug("Loading unavailable dates for facility id=%s", facility.id)
                    try:
                        unavailable_dates = self._load_facility_unavailable_dates(facility)
                        if unavailable_dates and isinstance(unavailable_dates, list):
                            facility.unavailable_dates = unavailable_dates
                            logger.debug("Unavailable dates loaded for facility id=%s: %s", facility.id, facility.unavailable_dates)
                        else:
                            # Empty list just means its always available
                            facility.unavailable_dates = []
                    except Exception as dates_error:
                        logger.error("Error loading unavailable dates for facility id=%s: %s", facility.id, dates_error)
                        facility.unavailable_dates = []  # Use empty list
    
                    # Validate the facility object before adding to list
                    if not isinstance(facility.schedule, WeeklySchedule):
                        logger.error("Facility id=%s has invalid schedule type: %s", facility.id, type(facility.schedule))
                        facility.schedule = WeeklySchedule()
                    
                    # Test that the schedule has the expected methods
                    try:
                        test_days = facility.schedule.get_all_days()
                        if not isinstance(test_days, dict):
                            logger.error("Facility id=%s schedule.get_all_days() returned invalid type: %s", facility.id, type(test_days))
                            facility.schedule = WeeklySchedule()
                    except AttributeError as attr_error:
                        logger.error("Facility id=%s schedule missing get_all_days method: %s", facility.id, attr_error)
                        facility.schedule = WeeklySchedule()
                    except Exception as test_error:
                        logger.error("Facility id=%s schedule test failed: %s", facility.id, test_error)
                        facility.schedule = WeeklySchedule()
    
                    facilities.append(facility)
                    logger.debug("Successfully appended facility id=%s to result list", facility.id)
    
                except Exception as facility_error:
                    logger.error("Error processing facility row %s: %s", row_data.get('id', 'unknown'), facility_error)
                    # Skip this facility and continue with others
                    continue
    
            logger.info("Completed list_facilities, returning %d facilities", len(facilities))
            return facilities
    
        except Exception as e:
            logger.exception("Error in list_facilities")
            raise


    
    def get_facilities_by_name(self, name: str, exact_match: bool = True) -> List[Facility]:
        """Get facilities by name or partial name match"""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Name must be a non-empty string")
        
        try:
            if exact_match:
                # Check both name and short_name for exact matches
                self.cursor.execute("""
                    SELECT * FROM facilities 
                    WHERE name = ? OR short_name = ? 
                    ORDER BY name
                """, (name, name))
            else:
                # Partial match on both name and short_name
                self.cursor.execute("""
                    SELECT * FROM facilities 
                    WHERE name LIKE ? OR short_name LIKE ? 
                    ORDER BY name
                """, (f"%{name}%", f"%{name}%"))
            
            facilities = []
            for row in self.cursor.fetchall():
                facility_data = self._dictify(row)
                
                facility = Facility(
                    id=facility_data['id'],
                    name=facility_data['name'],
                    short_name=facility_data.get('short_name'),
                    location=facility_data['location'],
                    total_courts=facility_data.get('total_courts', 0)
                )
                
                # Load schedule and unavailable dates
                facility.schedule = self._load_facility_schedule(facility)
                facility.unavailable_dates = self._load_facility_unavailable_dates(facility)
                
                facilities.append(facility)
            
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting facilities by name: {e}")


    # ======= Facility Schedule Methods ========

    def _insert_facility_schedule(self, facility: Facility, schedule: WeeklySchedule) -> None:
        """Insert facility schedule data into the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        facility_id = facility.id
        try:
            # Clear existing schedule data for this facility
            self.cursor.execute("DELETE FROM facility_schedules WHERE facility_id = ?", (facility_id,))
            
            # Insert schedule for each day
            for day_name, day_schedule in schedule.get_all_days().items():
                for time_slot in day_schedule.start_times:
                    self.cursor.execute("""
                        INSERT INTO facility_schedules (facility_id, day, time, available_courts)
                        VALUES (?, ?, ?, ?)
                    """, (facility_id, day_name, time_slot.time, time_slot.available_courts))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error inserting facility schedule: {e}")





    def _load_facility_schedule(self, facility: Facility) -> WeeklySchedule:
        """Load facility schedule from the database with enhanced error handling"""
        
        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id
            self.cursor.execute("""
                SELECT day, time, available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? 
                ORDER BY day, time
            """, (facility_id,))
            
            # Create a new WeeklySchedule with proper initialization
            schedule = WeeklySchedule()
            
            rows = self.cursor.fetchall()
            
            for row in rows:
                try:
                    day_name = row['day']
                    time_slot = TimeSlot(
                        time=row['time'],
                        available_courts=row['available_courts']
                    )
                    
                    # Get the day schedule and add the time slot
                    day_schedule = schedule.get_day_schedule(day_name)
                    day_schedule.start_times.append(time_slot)
                    
                    logger.debug("Added time slot %s with %d courts for %s", 
                               time_slot.time, time_slot.available_courts, day_name)
                    
                except Exception as slot_error:
                    logger.error("Error processing schedule row for facility_id=%s: %s", facility_id, slot_error)
                    continue  # Skip this time slot and continue
            
            # Verify the schedule object is valid
            try:
                test_days = schedule.get_all_days()
                if not isinstance(test_days, dict):
                    logger.error("Created schedule has invalid get_all_days() result for facility_id=%s", facility_id)
                    return WeeklySchedule()  # Return empty schedule
            except Exception as validation_error:
                logger.error("Schedule validation failed for facility_id=%s: %s", facility_id, validation_error)
                return WeeklySchedule()  # Return empty schedule
            
            #logger.debug("Successfully loaded schedule for facility_id=%s", facility_id)
            return schedule
            
        except sqlite3.Error as e:
            logger.error("Database error loading facility schedule for facility_id=%s: %s", facility_id, e)
            return WeeklySchedule()  # Return empty schedule instead of raising
        except Exception as e:
            logger.error("Unexpected error loading facility schedule for facility_id=%s: %s", facility_id, e)
            return WeeklySchedule()  # Return empty schedule instead of raising


    # ======== Facility Unavailable Dates Methods ========

    def add_unavailable_date(self, facility: Facility, date: str) -> bool:
        """Add an unavailable date to a facility"""

        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id

            self.cursor.execute("""
                INSERT OR IGNORE INTO facility_unavailable_dates (facility_id, date)
                VALUES (?, ?)
            """, (facility_id, date))
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
            self.cursor.execute("""
                DELETE FROM facility_unavailable_dates 
                WHERE facility_id = ? AND date = ?
            """, (facility_id, date))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error removing unavailable date: {e}")
        return True
    

    def _insert_facility_unavailable_dates(self, facility: Facility, unavailable_dates: List[str]) -> None:
        """Insert facility unavailable dates into the database"""
        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id

            # Clear existing unavailable dates for this facility
            self.cursor.execute("DELETE FROM facility_unavailable_dates WHERE facility_id = ?", (facility_id,))
            
            # Insert unavailable dates
            for date_str in unavailable_dates:
                self.cursor.execute("""
                    INSERT INTO facility_unavailable_dates (facility_id, date)
                    VALUES (?, ?)
                """, (facility_id, date_str))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error inserting facility unavailable dates: {e}")
        


    def _load_facility_unavailable_dates(self, facility: Facility) -> List[str]:
        """Load facility unavailable dates from the database"""
        try:
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            facility_id = facility.id

            self.cursor.execute("""
                SELECT date 
                FROM facility_unavailable_dates 
                WHERE facility_id = ? 
                ORDER BY date
            """, (facility_id,))
            
            return [row['date'] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error loading facility unavailable dates: {e}")






    # ======== Facility Availability Methods ========

    def get_facility_availability(self, 
                                facility: Facility, 
                                dates: List[str],
                                max_days: int = 50) -> List['FacilityAvailabilityInfo']:
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
            available_dates, unavailable_dates_info = self._filter_dates_by_facility_availability(facility, dates)
            
            facility_availability_info = []
            
            # Add unavailable date info first
            facility_availability_info.extend(unavailable_dates_info)
            
            # Only query database for dates when facility is actually available
            if available_dates:
                # Single database query to get scheduled times for available dates only
                scheduled_times_by_date = self._get_scheduled_times_batch(facility, available_dates)
                
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


    def _filter_dates_by_facility_availability(self, facility: Facility, dates: List[str]) -> Tuple[List[str], List['FacilityAvailabilityInfo']]:
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
                    reason='Facility marked as unavailable'
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
                        reason=f'No time slots available on {day_name}'
                    )
                    unavailable_dates_info.append(unavailable_info)
                    continue
            except ValueError:
                unavailable_info = FacilityAvailabilityInfo.create_unavailable(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    date=date,
                    day_of_week=day_name,
                    reason=f'No schedule available for {day_name}'
                )
                unavailable_dates_info.append(unavailable_info)
                continue
            
            # If we get here, facility is available and has schedule - needs DB query
            available_dates.append(date)
        
        return available_dates, unavailable_dates_info


    def _validate_facility_availability_inputs(self, facility: Facility, dates: List[str], max_days: int) -> None:
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
        
        if not isinstance(dates, list) or not all(isinstance(date, str) for date in dates):
            raise TypeError("dates must be a list of date strings in YYYY-MM-DD format")
        
        if not dates:
            raise ValueError("dates list cannot be empty")
        
        if len(dates) > max_days:
            raise ValueError(f"Cannot check more than {max_days} dates at once")
        
        # Validate all date formats in one pass
        for date in dates:
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD")


    def _get_scheduled_times_batch(self, facility: Facility, dates: List[str]) -> Dict[str, List[str]]:
        """
        Get scheduled times for multiple dates in a single database query
        
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
            placeholders = ','.join('?' for _ in dates)
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
            
            for row in rows:
                date = row['date']
                times_json = row['scheduled_times']
                
                if times_json:
                    try:
                        import json
                        times = json.loads(times_json)
                        if isinstance(times, list):
                            scheduled_times_by_date[date].extend(times)
                    except (json.JSONDecodeError, TypeError):
                        # Skip invalid JSON, log warning if needed
                        logger.warning(f"Invalid scheduled_times JSON for match on {date}: {times_json}")
                        continue
            
            return scheduled_times_by_date
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting scheduled times batch: {e}")
        except Exception as e:
            raise RuntimeError(f"Error getting scheduled times for facility {facility.id}: {e}")


    def _get_facility_availability_for_date(self, facility: Facility, date: str, 
                                        scheduled_times: List[str]) -> Optional['FacilityAvailabilityInfo']:
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
                time_slots=time_slot_availabilities
            )
            
        except Exception as e:
            raise RuntimeError(f"Error processing facility availability for {date}: {e}")


    def _get_day_name_safe(self, date: str) -> str:
        """
        Safely get day name from date string
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            Day name (Monday, Tuesday, etc.) or "Unknown" if parsing fails
        """
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            return date_obj.strftime('%A')
        except ValueError:
            return "Unknown"


    def _build_time_slot_availabilities(self, day_schedule: 'DaySchedule', 
                                    scheduled_times: List[str]) -> List['TimeSlotAvailability']:
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
            available_courts = max(0, total_courts - used_courts)
            utilization_percentage = (used_courts / total_courts * 100) if total_courts > 0 else 0
            
            slot_availability = TimeSlotAvailability(
                time=time,
                total_courts=total_courts,
                used_courts=used_courts,
                available_courts=available_courts,
                utilization_percentage=round(utilization_percentage, 1)
            )
            time_slot_availabilities.append(slot_availability)
        
        return time_slot_availabilities