"""
Facility Management Helper for SQLite Tennis Database

Handles all facility-related database operations including CRUD operations,
facility schedules, availability, and utilization tracking.
"""

import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from usta import Facility, WeeklySchedule, DaySchedule, TimeSlot, Line


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
    
    def add_facility(self, facility: Facility) -> None:
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
                facility.short_name,  # NEW: Include short_name
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
                short_name=facility_data.get('short_name'),  # NEW: Include short_name
                location=facility_data['location'],
                total_courts=facility_data.get('total_courts', 0)
            )
            
            # Load schedule data
            facility.schedule = self._load_facility_schedule(facility_id)
            
            # Load unavailable dates
            facility.unavailable_dates = self._load_facility_unavailable_dates(facility_id)
            
            return facility
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving facility {facility_id}: {e}")

    def update_facility(self, facility: Facility) -> None:
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
                facility.short_name,  # NEW: Include short_name
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
    
    def delete_facility(self, facility_id: int) -> None:
        """Delete a facility from the database"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Check if facility exists
            existing_facility = self.get_facility(facility_id)
            if not existing_facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Check if facility is referenced by teams (by facility name, not ID)
            facility = self.get_facility(facility_id)
            if facility:
                # Check both facility name and short_name
                if facility.short_name:
                    self.cursor.execute("""
                        SELECT COUNT(*) as count FROM teams 
                        WHERE home_facility = ? OR home_facility = ?
                    """, (facility.name, facility.short_name))
                else:
                    self.cursor.execute("SELECT COUNT(*) as count FROM teams WHERE home_facility = ?", (facility.name,))
                team_count = self.cursor.fetchone()['count']
            else:
                # Facility doesn't exist, so no teams can reference it
                team_count = 0
            
            if team_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {team_count} team(s)")
            
            # Check if facility is referenced by matches
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE facility_id = ?", (facility_id,))
            match_count = self.cursor.fetchone()['count']
            if match_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {match_count} match(es)")
            
            # Check if facility is referenced by lines
            self.cursor.execute("SELECT COUNT(*) as count FROM lines WHERE facility_id = ?", (facility_id,))
            line_count = self.cursor.fetchone()['count']
            if line_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {line_count} line(s)")
            
            # Delete the facility (CASCADE will delete schedule and unavailable_dates)
            self.cursor.execute("DELETE FROM facilities WHERE id = ?", (facility_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete facility {facility_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting facility {facility_id}: {e}")
        
    def list_facilities(self) -> List[Facility]:
        """List all facilities"""
        try:
            self.cursor.execute("SELECT * FROM facilities ORDER BY name")
            facilities = []
            
            for row in self.cursor.fetchall():
                facility_data = self._dictify(row)
                
                # Create basic facility (including short_name)
                facility = Facility(
                    id=facility_data['id'],
                    name=facility_data['name'],
                    short_name=facility_data.get('short_name'),  # NEW: Include short_name
                    location=facility_data['location'],
                    total_courts=facility_data.get('total_courts', 0)
                )
                
                # Load schedule and unavailable dates
                facility.schedule = self._load_facility_schedule(facility.id)
                facility.unavailable_dates = self._load_facility_unavailable_dates(facility.id)
                
                facilities.append(facility)
            
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing facilities: {e}")


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
        """Load facility schedule from the database"""
        try:
            self.cursor.execute("""
                SELECT day, time, available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? 
                ORDER BY day, time
            """, (facility_id,))
            
            schedule = WeeklySchedule()
            
            for row in self.cursor.fetchall():
                day_name = row['day']
                time_slot = TimeSlot(
                    time=row['time'],
                    available_courts=row['available_courts']
                )
                
                day_schedule = schedule.get_day_schedule(day_name)
                day_schedule.start_times.append(time_slot)
            
            return schedule
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error loading facility schedule: {e}")

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

    def get_available_courts_count(self, facility_id: int, date: str, time: str) -> int:
        """Get the number of courts available at a facility for a given date/time"""
        try:
            # Get facility to check availability
            facility = self.get_facility(facility_id)
            if not facility or not facility.is_available_on_date(date):
                return 0
            
            # Get day of week
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return 0
            
            # Get total courts available at this time
            self.cursor.execute("""
                SELECT available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? AND day = ? AND time = ?
            """, (facility_id, day_name, time))
            
            row = self.cursor.fetchone()
            if not row:
                return 0
            
            total_courts = row['available_courts']
            
            # Get courts already scheduled
            scheduled_lines = self.get_lines_by_time_slot(facility_id, date, time)
            used_courts = len(scheduled_lines)
            
            return max(0, total_courts - used_courts)
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error checking court availability: {e}")

    def get_lines_by_time_slot(self, facility_id: int, date: str, time: str) -> List[Line]:
        """Get all lines scheduled at a facility on a specific date and time"""
        try:
            self.cursor.execute("""
                SELECT * FROM lines 
                WHERE facility_id = ? AND date = ? AND time = ?
                ORDER BY line_number
            """, (facility_id, date, time))
            
            lines = []
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                lines.append(Line(**line_data))
            
            return lines
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting lines by time slot: {e}")

    def check_court_availability(self, facility_id: int, date: str, time: str, courts_needed: int) -> bool:
        """Check if enough courts are available at a facility for a given date/time"""
        available_courts = self.get_available_courts_count(facility_id, date, time)
        return available_courts >= courts_needed

    def get_facility_utilization_detailed(self, facility_id: int, date: str) -> Dict[str, Any]:
        """
        Get detailed utilization for a facility on a specific date
        
        Args:
            facility_id: Facility to analyze
            date: Date to check (YYYY-MM-DD format)
            
        Returns:
            Dictionary with detailed utilization information
        """
        try:
            # Get the facility
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Get scheduled lines for this facility/date
            self.cursor.execute("""
                SELECT * FROM lines WHERE facility_id = ? AND date = ?
            """, (facility_id, date))
            
            scheduled_lines = []
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                scheduled_lines.append(Line(**line_data))
            
            # Get day of week
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return {'error': 'Invalid date format'}
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            # Calculate utilization by time slot
            utilization_by_time = {}
            total_available_slots = 0
            total_used_slots = 0
            
            for time_slot in day_schedule.start_times:
                time = time_slot.time
                available_courts = time_slot.available_courts
                
                # Count lines scheduled at this time
                lines_at_time = [line for line in scheduled_lines if line.time == time]
                used_courts = len(lines_at_time)
                
                utilization_by_time[time] = {
                    'available_courts': available_courts,
                    'used_courts': used_courts,
                    'remaining_courts': available_courts - used_courts,
                    'utilization_percentage': (used_courts / available_courts * 100) if available_courts > 0 else 0,
                    'scheduled_lines': [{'line_id': line.id, 'match_id': line.match_id} for line in lines_at_time]
                }
                
                total_available_slots += available_courts
                total_used_slots += used_courts
            
            overall_utilization = (total_used_slots / total_available_slots * 100) if total_available_slots > 0 else 0
            
            return {
                'facility_id': facility_id,
                'facility_name': facility.name,
                'date': date,
                'day_of_week': day_name,
                'overall_utilization_percentage': round(overall_utilization, 1),
                'total_available_court_slots': total_available_slots,
                'total_used_court_slots': total_used_slots,
                'total_remaining_court_slots': total_available_slots - total_used_slots,
                'utilization_by_time': utilization_by_time,
                'scheduled_lines_count': len(scheduled_lines),
                'facility_available': facility.is_available_on_date(date)
            }
            
        except Exception as e:
            raise RuntimeError(f"Error getting facility utilization: {e}")

    def get_facility_availability_forecast(self, facility_id: int, 
                                         start_date: str, end_date: str) -> Dict[str, Dict]:
        """
        Get availability forecast for a facility over a date range
        
        Args:
            facility_id: Facility to analyze
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping dates to utilization info
        """
        try:
            # Get the facility
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            forecast = {}
            current = start_dt
            
            while current <= end_dt:
                date_str = current.strftime('%Y-%m-%d')
                
                if facility.is_available_on_date(date_str):
                    utilization = self.get_facility_utilization_detailed(facility_id, date_str)
                    forecast[date_str] = utilization
                else:
                    forecast[date_str] = {
                        'facility_id': facility_id,
                        'facility_name': facility.name,
                        'date': date_str,
                        'status': 'facility_unavailable',
                        'reason': 'Facility marked as unavailable'
                    }
                
                current += timedelta(days=1)
            
            return forecast
            
        except Exception as e:
            raise RuntimeError(f"Error getting facility availability forecast: {e}")

    def get_facility_utilization(self, facility_id: int, start_date: str, end_date: str) -> Dict[str, float]:
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
                    
                    for time_slot in day_schedule.start_times:
                        # Each time slot is typically 2 hours
                        hours_per_slot = 2.0
                        slot_available_hours = time_slot.available_courts * hours_per_slot
                        total_available_hours += slot_available_hours
                        
                        # Count used courts at this time slot
                        scheduled_lines = self.get_lines_by_time_slot(facility_id, date_str, time_slot.time)
                        used_courts = len(scheduled_lines)
                        slot_used_hours = used_courts * hours_per_slot
                        total_used_hours += slot_used_hours
                
                current_date += timedelta(days=1)
            
            # Calculate utilization metrics
            utilization_percentage = (total_used_hours / total_available_hours * 100) if total_available_hours > 0 else 0
            
            return {
                'total_available_hours': total_available_hours,
                'total_used_hours': total_used_hours,
                'utilization_percentage': round(utilization_percentage, 2),
                'start_date': start_date,
                'end_date': end_date,
                'days_analyzed': (end_date_obj - datetime.strptime(start_date, '%Y-%m-%d')).days + 1
            }
            
        except Exception as e:
            raise RuntimeError(f"Error calculating facility utilization: {e}")

    def get_facilities_by_location(self, location: str) -> List[Facility]:
        """Get all facilities in a specific location"""
        if not isinstance(location, str) or not location.strip():
            raise ValueError("Location must be a non-empty string")
        
        try:
            self.cursor.execute("SELECT * FROM facilities WHERE location LIKE ? ORDER BY name", (f"%{location}%",))
            facilities = []
            
            for row in self.cursor.fetchall():
                facility_data = self._dictify(row)
                
                # Create basic facility
                facility = Facility(
                    id=facility_data['id'],
                    name=facility_data['name'],
                    location=facility_data['location'],
                    total_courts=facility_data.get('total_courts', 0)
                )
                
                # Load schedule and unavailable dates
                facility.schedule = self._load_facility_schedule(facility.id)
                facility.unavailable_dates = self._load_facility_unavailable_dates(facility.id)
                
                facilities.append(facility)
            
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting facilities by location: {e}")

    def add_unavailable_date(self, facility_id: int, date: str) -> None:
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

    def remove_unavailable_date(self, facility_id: int, date: str) -> None:
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
