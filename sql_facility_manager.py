"""
Facility Management Helper for SQLite Tennis Database

Handles all facility-related database operations including CRUD operations,
facility schedules, availability, and utilization tracking.

Updated to work without Line class - uses match scheduled_times instead.
Added get_available_dates API for finding available dates for matches.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from usta import Facility, WeeklySchedule, DaySchedule, TimeSlot

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
            self._insert_facility_schedule(facility.id, facility.schedule)
            
            # Insert unavailable dates
            self._insert_facility_unavailable_dates(facility.id, facility.unavailable_dates)
            
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
            facility.schedule = self._load_facility_schedule(facility_id)
            
            # Load unavailable dates
            facility.unavailable_dates = self._load_facility_unavailable_dates(facility_id)
            
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
    
    def delete_facility(self, facility_id: int) -> bool:
        """Delete a facility from the database"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Check if facility exists
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
                        loaded_schedule = self._load_facility_schedule(facility.id)
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
                        unavailable_dates = self._load_facility_unavailable_dates(facility.id)
                        if unavailable_dates and isinstance(unavailable_dates, list):
                            facility.unavailable_dates = unavailable_dates
                            logger.debug("Unavailable dates loaded for facility id=%s: %s", facility.id, facility.unavailable_dates)
                        else:
                            logger.warning("Invalid unavailable dates returned for facility id=%s, using empty list", facility.id)
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
                facility.schedule = self._load_facility_schedule(facility.id)
                facility.unavailable_dates = self._load_facility_unavailable_dates(facility.id)
                
                facilities.append(facility)
            
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting facilities by name: {e}")

    def get_available_dates(self, facility: Facility, num_lines: int, 
                           allow_split_lines: bool = False, 
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           max_dates: int = 50) -> List[str]:
        """
        Get available dates for a facility that can accommodate the required number of lines
        
        Args:
            facility: Facility object to check availability for
            num_lines: Number of lines (courts) needed
            allow_split_lines: Whether lines can be split across different time slots
            start_date: Start date for search (YYYY-MM-DD format). If None, uses today's date
            end_date: End date for search (YYYY-MM-DD format). If None, searches 16 weeks from start
            max_dates: Maximum number of dates to return
            
        Returns:
            List of available date strings in YYYY-MM-DD format, ordered by preference
        """
        try:
            # Set default date range if not provided
            if start_date is None:
                start_date = datetime.now().strftime('%Y-%m-%d')
            
            if end_date is None:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = start_dt + timedelta(weeks=16)
                end_date = end_dt.strftime('%Y-%m-%d')
            
            # Validate date range
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            if start_dt > end_dt:
                raise ValueError("Start date must be before or equal to end date")
            
            available_dates = []
            current_dt = start_dt
            
            while current_dt <= end_dt and len(available_dates) < max_dates:
                date_str = current_dt.strftime('%Y-%m-%d')
                
                # Check if facility is available on this date
                if not facility.is_available_on_date(date_str):
                    current_dt += timedelta(days=1)
                    continue
                
                # Get day of week
                day_name = current_dt.strftime('%A')
                
                # Get day schedule
                try:
                    day_schedule = facility.schedule.get_day_schedule(day_name)
                except ValueError:
                    # Invalid day name or no schedule for this day
                    current_dt += timedelta(days=1)
                    continue
                
                # Check if this date can accommodate the required lines
                if self._can_accommodate_lines_on_date(facility, date_str, day_schedule, num_lines, allow_split_lines):
                    available_dates.append(date_str)
                
                current_dt += timedelta(days=1)
            
            return available_dates
            
        except Exception as e:
            raise RuntimeError(f"Error getting available dates for facility {facility.id}: {e}")
    
    def _can_accommodate_lines_on_date(self, facility: Facility, date_str: str, 
                                     day_schedule: DaySchedule, num_lines: int, 
                                     allow_split_lines: bool) -> bool:
        """
        Check if a facility can accommodate the required lines on a specific date
        
        Args:
            facility: Facility object
            date_str: Date string in YYYY-MM-DD format
            day_schedule: DaySchedule for the day of week
            num_lines: Number of lines needed
            allow_split_lines: Whether lines can be split across time slots
            
        Returns:
            True if the facility can accommodate the lines
        """
        try:
            # Get scheduled times at this facility on this date
            scheduled_times = self.get_scheduled_times_at_facility(facility.id, date_str)
            
            if not allow_split_lines:
                # All lines must be at the same time - check each time slot individually
                for time_slot in day_schedule.start_times:
                    time = time_slot.time
                    available_courts = time_slot.available_courts
                    used_courts = scheduled_times.count(time)
                    remaining_courts = available_courts - used_courts
                    
                    if remaining_courts >= num_lines:
                        return True
                
                return False
            
            else:
                # Lines can be split - check if total available courts across all time slots >= num_lines
                total_available = 0
                
                for time_slot in day_schedule.start_times:
                    time = time_slot.time
                    available_courts = time_slot.available_courts
                    used_courts = scheduled_times.count(time)
                    remaining_courts = max(0, available_courts - used_courts)
                    total_available += remaining_courts
                
                return total_available >= num_lines
            
        except Exception as e:
            logger.error(f"Error checking line accommodation for facility {facility.id} on {date_str}: {e}")
            return False

    def _insert_facility_schedule(self, facility_id: int, schedule: WeeklySchedule) -> None:
        """Insert facility schedule data into the database"""
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

    def _insert_facility_unavailable_dates(self, facility_id: int, unavailable_dates: List[str]) -> None:
        """Insert facility unavailable dates into the database"""
        try:
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



    def _load_facility_schedule(self, facility_id: int) -> WeeklySchedule:
        """Load facility schedule from the database with enhanced error handling"""
        
        logger.setLevel(logging.INFO)
        
        try:
            logger.debug("Loading schedule for facility_id=%s", facility_id)
            self.cursor.execute("""
                SELECT day, time, available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? 
                ORDER BY day, time
            """, (facility_id,))
            
            # Create a new WeeklySchedule with proper initialization
            schedule = WeeklySchedule()
            
            rows = self.cursor.fetchall()
            logger.debug("Found %d schedule rows for facility_id=%s", len(rows), facility_id)
            
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
            
            logger.debug("Successfully loaded schedule for facility_id=%s", facility_id)
            return schedule
            
        except sqlite3.Error as e:
            logger.error("Database error loading facility schedule for facility_id=%s: %s", facility_id, e)
            return WeeklySchedule()  # Return empty schedule instead of raising
        except Exception as e:
            logger.error("Unexpected error loading facility schedule for facility_id=%s: %s", facility_id, e)
            return WeeklySchedule()  # Return empty schedule instead of raising


    

    def _load_facility_unavailable_dates(self, facility_id: int) -> List[str]:
        """Load facility unavailable dates from the database"""
        try:
            self.cursor.execute("""
                SELECT date 
                FROM facility_unavailable_dates 
                WHERE facility_id = ? 
                ORDER BY date
            """, (facility_id,))
            
            return [row['date'] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error loading facility unavailable dates: {e}")

    def get_facility_availability(self, facility_id: int, date: str) -> Dict[str, Any]:
        """Get facility availability information for a specific date"""
        try:
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Check if facility is available on this date
            if not facility.is_available_on_date(date):
                return {
                    'facility_id': facility_id,
                    'date': date,
                    'available': False,
                    'reason': 'Facility marked as unavailable'
                }
            
            # Get day of week and schedule
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return {
                    'facility_id': facility_id,
                    'date': date,
                    'available': False,
                    'reason': 'Invalid date format'
                }
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            # Get scheduled times at this facility on this date
            scheduled_times = self.get_scheduled_times_at_facility(facility_id, date)
            
            # Calculate availability for each time slot
            time_slot_availability = []
            total_available_slots = 0
            total_used_slots = 0
            
            for time_slot in day_schedule.start_times:
                time = time_slot.time
                available_courts = time_slot.available_courts
                used_courts = scheduled_times.count(time)
                remaining_courts = max(0, available_courts - used_courts)
                
                time_slot_availability.append({
                    'time': time,
                    'total_courts': available_courts,
                    'used_courts': used_courts,
                    'available_courts': remaining_courts,
                    'utilization_percentage': (used_courts / available_courts * 100) if available_courts > 0 else 0
                })
                
                total_available_slots += available_courts
                total_used_slots += used_courts
            
            overall_utilization = (total_used_slots / total_available_slots * 100) if total_available_slots > 0 else 0
            
            return {
                'facility_id': facility_id,
                'facility_name': facility.name,
                'date': date,
                'day_of_week': day_name,
                'available': True,
                'overall_utilization_percentage': round(overall_utilization, 1),
                'total_court_slots': total_available_slots,
                'used_court_slots': total_used_slots,
                'available_court_slots': total_available_slots - total_used_slots,
                'time_slots': time_slot_availability
            }
            
        except Exception as e:
            raise RuntimeError(f"Error getting facility availability: {e}")

    def get_scheduled_times_at_facility(self, facility_id: int, date: str) -> List[str]:
        """Get all scheduled times at a facility on a specific date"""
        try:
            self.cursor.execute("""
                SELECT scheduled_times 
                FROM matches 
                WHERE facility_id = ? AND date = ? AND status = 'scheduled' AND scheduled_times IS NOT NULL
            """, (facility_id, date))
            
            all_times = []
            for row in self.cursor.fetchall():
                if row['scheduled_times']:
                    try:
                        times = json.loads(row['scheduled_times'])
                        if isinstance(times, list):
                            all_times.extend(times)
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            return all_times
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting scheduled times: {e}")

    def check_time_availability(self, facility_id: int, date: str, time: str, courts_needed: int = 1) -> bool:
        """Check if a specific time slot is available at a facility"""
        try:
            # Get all scheduled times at this facility/date
            scheduled_times = self.get_scheduled_times_at_facility(facility_id, date)
            
            # Count how many times this specific time is already used
            times_used = scheduled_times.count(time)
            
            # Get facility information to check total courts
            facility = self.get_facility(facility_id)
            if not facility:
                return False
            
            # Get day of week and check if time slot exists
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return False
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            # Find the time slot
            time_slot = None
            for slot in day_schedule.start_times:
                if slot.time == time:
                    time_slot = slot
                    break
            
            if not time_slot:
                return False  # Time slot not available at this facility
            
            # Check if there are enough courts available
            available_courts = time_slot.available_courts - times_used
            return available_courts >= courts_needed
            
        except Exception as e:
            return False

    def get_available_times_at_facility(self, facility_id: int, date: str, courts_needed: int = 1) -> List[str]:
        """Get all available times at a facility for the specified number of courts"""
        try:
            facility = self.get_facility(facility_id)
            if not facility:
                return []
            
            # Check if facility is available on this date
            if not facility.is_available_on_date(date):
                return []
            
            # Get day of week
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return []
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            available_times = []
            for time_slot in day_schedule.start_times:
                if self.check_time_availability(facility_id, date, time_slot.time, courts_needed):
                    available_times.append(time_slot.time)
            
            return available_times
            
        except Exception as e:
            return []

    def get_facility_utilization(self, facility_id: int, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get facility utilization statistics for a date range"""
        try:
            # Verify facility exists
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Calculate total available court-hours in the date range
            total_available_hours = 0
            total_used_hours = 0
            
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current_date <= end_date_obj:
                date_str = current_date.strftime('%Y-%m-%d')
                day_name = current_date.strftime('%A')
                
                if facility.is_available_on_date(date_str):
                    day_schedule = facility.schedule.get_day_schedule(day_name)
                    scheduled_times = self.get_scheduled_times_at_facility(facility_id, date_str)
                    
                    for time_slot in day_schedule.start_times:
                        # Each time slot is typically 3 hours (for tennis matches)
                        hours_per_slot = 3.0
                        slot_available_hours = time_slot.available_courts * hours_per_slot
                        total_available_hours += slot_available_hours
                        
                        # Count used courts at this time slot
                        used_courts = scheduled_times.count(time_slot.time)
                        slot_used_hours = used_courts * hours_per_slot
                        total_used_hours += slot_used_hours
                
                current_date += timedelta(days=1)
            
            # Calculate utilization metrics
            utilization_percentage = (total_used_hours / total_available_hours * 100) if total_available_hours > 0 else 0
            
            return {
                'facility_id': facility_id,
                'facility_name': facility.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_available_hours': total_available_hours,
                'total_used_hours': total_used_hours,
                'utilization_percentage': round(utilization_percentage, 2),
                'days_analyzed': (end_date_obj - datetime.strptime(start_date, '%Y-%m-%d')).days + 1
            }
            
        except Exception as e:
            raise RuntimeError(f"Error calculating facility utilization: {e}")

    def add_unavailable_date(self, facility_id: int, date: str) -> bool:
        """Add an unavailable date to a facility"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        # Verify facility exists
        if not self.get_facility(facility_id):
            raise ValueError(f"Facility with ID {facility_id} does not exist")
        
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO facility_unavailable_dates (facility_id, date)
                VALUES (?, ?)
            """, (facility_id, date))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding unavailable date: {e}")
        return True

    def remove_unavailable_date(self, facility_id: int, date: str) -> bool:
        """Remove an unavailable date from a facility"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            self.cursor.execute("""
                DELETE FROM facility_unavailable_dates 
                WHERE facility_id = ? AND date = ?
            """, (facility_id, date))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error removing unavailable date: {e}")
        return True