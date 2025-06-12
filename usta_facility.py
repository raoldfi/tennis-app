from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
import itertools
import re
from collections import defaultdict
import logging 

logger = logging.getLogger(__name__)

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TimeSlot:
    """Represents a time slot with available courts"""
    time: str  # Format: "HH:MM" (24-hour format)
    available_courts: int
    
    def __post_init__(self):
        """Validate time format and court count"""
        if not isinstance(self.time, str):
            raise ValueError("Time must be a string")
        
        # Validate time format (HH:MM)
        try:
            parts = self.time.split(':')
            if len(parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: '{self.time}'. Expected HH:MM format")
        
        if not isinstance(self.available_courts, int) or self.available_courts < 0:
            raise ValueError(f"Available courts must be a non-negative integer, got: {self.available_courts}")

    # ========== TimeSlot Class Getters ==========
    def get_time(self) -> str:
        """Get the time string in HH:MM format"""
        return self.time
    
    def get_available_courts(self) -> int:
        """Get the number of available courts"""
        return self.available_courts
    
    def get_hour(self) -> int:
        """Get the hour component of the time (0-23)"""
        return int(self.time.split(':')[0])
    
    def get_minute(self) -> int:
        """Get the minute component of the time (0-59)"""
        return int(self.time.split(':')[1])
    
    def get_time_as_minutes(self) -> int:
        """Get time as total minutes from midnight"""
        hour, minute = self.get_hour(), self.get_minute()
        return hour * 60 + minute

@dataclass
class DaySchedule:
    """Represents the schedule for a single day"""
    start_times: List[TimeSlot] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate that all start_times are TimeSlot objects"""
        if not isinstance(self.start_times, list):
            raise ValueError("start_times must be a list")
        
        for i, slot in enumerate(self.start_times):
            if not isinstance(slot, TimeSlot):
                raise ValueError(f"All items in start_times must be TimeSlot objects, item {i} is {type(slot)}")
    
    # ========== DaySchedule Class Getters ==========

    def get_start_times(self) -> List[TimeSlot]:
        """Get the list of time slots for this day"""
        return self.start_times.copy()
    
    def get_time_slots_count(self) -> int:
        """Get the number of time slots for this day"""
        return len(self.start_times)
    
    def get_earliest_time(self) -> Optional[str]:
        """Get the earliest start time for this day"""
        if not self.start_times:
            return None
        return min(slot.time for slot in self.start_times)
    
    def get_latest_time(self) -> Optional[str]:
        """Get the latest start time for this day"""
        if not self.start_times:
            return None
        return max(slot.time for slot in self.start_times)
    
    def get_total_courts_available(self) -> int:
        """Get total courts available across all time slots"""
        return sum(slot.available_courts for slot in self.start_times)
    
    def get_time_range(self) -> Optional[Tuple[str, str]]:
        """Get the time range (earliest, latest) for this day"""
        earliest = self.get_earliest_time()
        latest = self.get_latest_time()
        if earliest and latest:
            return (earliest, latest)
        return None
    
    def add_time_slot(self, time: str, available_courts: int) -> None:
        """Add a new time slot to this day"""
        self.start_times.append(TimeSlot(time=time, available_courts=available_courts))
    
    def get_available_courts_at_time(self, time: str) -> Optional[int]:
        """Get the number of available courts at a specific time"""
        for slot in self.start_times:
            if slot.time == time:
                return slot.available_courts
        return None
    
    def has_availability(self) -> bool:
        """Check if this day has any available time slots"""
        return len(self.start_times) > 0 and any(slot.available_courts > 0 for slot in self.start_times)
    
    def get_times_with_min_courts(self, min_courts: int) -> List[str]:
        """Get all times that have at least the specified number of courts available"""
        return [slot.time for slot in self.start_times if slot.available_courts >= min_courts]
    
    def get_max_courts_available(self) -> int:
        """Get the maximum number of courts available at any time during this day"""
        if not self.start_times:
            return 0
        return max(slot.available_courts for slot in self.start_times)

@dataclass
class WeeklySchedule:
    """Represents a weekly schedule for a facility"""
    monday: DaySchedule = field(default_factory=DaySchedule)
    tuesday: DaySchedule = field(default_factory=DaySchedule)
    wednesday: DaySchedule = field(default_factory=DaySchedule)
    thursday: DaySchedule = field(default_factory=DaySchedule)
    friday: DaySchedule = field(default_factory=DaySchedule)
    saturday: DaySchedule = field(default_factory=DaySchedule)
    sunday: DaySchedule = field(default_factory=DaySchedule)

    # ========== WeeklySchedule Class Getters ==========

    def get_monday(self) -> DaySchedule:
        """Get Monday's schedule"""
        return self.monday
    
    def get_tuesday(self) -> DaySchedule:
        """Get Tuesday's schedule"""
        return self.tuesday
    
    def get_wednesday(self) -> DaySchedule:
        """Get Wednesday's schedule"""
        return self.wednesday
    
    def get_thursday(self) -> DaySchedule:
        """Get Thursday's schedule"""
        return self.thursday
    
    def get_friday(self) -> DaySchedule:
        """Get Friday's schedule"""
        return self.friday
    
    def get_saturday(self) -> DaySchedule:
        """Get Saturday's schedule"""
        return self.saturday
    
    def get_sunday(self) -> DaySchedule:
        """Get Sunday's schedule"""
        return self.sunday
    
    def get_weekdays(self) -> Dict[str, DaySchedule]:
        """Get weekday schedules (Monday-Friday)"""
        return {
            'Monday': self.monday,
            'Tuesday': self.tuesday,
            'Wednesday': self.wednesday,
            'Thursday': self.thursday,
            'Friday': self.friday
        }
    
    def get_weekends(self) -> Dict[str, DaySchedule]:
        """Get weekend schedules (Saturday-Sunday)"""
        return {
            'Saturday': self.saturday,
            'Sunday': self.sunday
        }
    
    def get_days_with_availability(self) -> List[str]:
        """Get list of days that have any availability"""
        available_days = []
        for day_name, day_schedule in self.get_all_days().items():
            if day_schedule.has_availability():
                available_days.append(day_name)
        return available_days
    
    
    def get_day_schedule(self, day: str) -> DaySchedule:
        """Get schedule for a specific day (case-insensitive)"""
        day_lower = day.lower()
        day_mapping = {
            'monday': self.monday,
            'tuesday': self.tuesday,
            'wednesday': self.wednesday,
            'thursday': self.thursday,
            'friday': self.friday,
            'saturday': self.saturday,
            'sunday': self.sunday
        }
        
        if day_lower not in day_mapping:
            raise ValueError(f"Invalid day: {day}. Must be one of: {list(day_mapping.keys())}")
        
        return day_mapping[day_lower]
    
    def set_day_schedule(self, day: str, schedule: DaySchedule) -> None:
        """Set schedule for a specific day"""
        day_lower = day.lower()
        if day_lower == 'monday':
            self.monday = schedule
        elif day_lower == 'tuesday':
            self.tuesday = schedule
        elif day_lower == 'wednesday':
            self.wednesday = schedule
        elif day_lower == 'thursday':
            self.thursday = schedule
        elif day_lower == 'friday':
            self.friday = schedule
        elif day_lower == 'saturday':
            self.saturday = schedule
        elif day_lower == 'sunday':
            self.sunday = schedule
        else:
            raise ValueError(f"Invalid day: {day}")
    
    def get_all_days(self) -> Dict[str, DaySchedule]:
        """Get all day schedules as a dictionary"""
        return {
            'Monday': self.monday,
            'Tuesday': self.tuesday,
            'Wednesday': self.wednesday,
            'Thursday': self.thursday,
            'Friday': self.friday,
            'Saturday': self.saturday,
            'Sunday': self.sunday
        }

@dataclass
class Line:
    """Represents a single line (court assignment) within a match"""
    id: int
    match_id: int
    line_number: int  # 1, 2, 3, etc. (line position within the match)
    facility_id: Optional[int] = None  # None for unscheduled lines
    date: Optional[str] = None  # YYYY-MM-DD format, None for unscheduled
    time: Optional[str] = None  # HH:MM format, None for unscheduled
    court_number: Optional[int] = None  # Specific court number if facility tracks them
    
    def __post_init__(self):
        """Validate line data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Line ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.match_id, int) or self.match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {self.match_id}")
        
        if not isinstance(self.line_number, int) or self.line_number <= 0:
            raise ValueError(f"Line number must be a positive integer, got: {self.line_number}")
        
        # Validate facility_id if provided
        if self.facility_id is not None:
            if not isinstance(self.facility_id, int) or self.facility_id <= 0:
                raise ValueError(f"Facility ID must be a positive integer or None, got: {self.facility_id}")
        
        # Validate date format if provided
        if self.date is not None:
            if not isinstance(self.date, str):
                raise ValueError("Date must be a string or None")
            try:
                parts = self.date.split('-')
                if len(parts) != 3:
                    raise ValueError("Invalid date format")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                    raise ValueError("Invalid date values")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid date format: '{self.date}'. Expected YYYY-MM-DD format")
        
        # Validate time format if provided
        if self.time is not None:
            if not isinstance(self.time, str):
                raise ValueError("Time must be a string or None")
            try:
                parts = self.time.split(':')
                if len(parts) != 2:
                    raise ValueError("Invalid time format")
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time values")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid time format: '{self.time}'. Expected HH:MM format")
        
        # Validate court_number if provided
        if self.court_number is not None:
            if not isinstance(self.court_number, int) or self.court_number <= 0:
                raise ValueError(f"Court number must be a positive integer or None, got: {self.court_number}")

    # ========== Line Class Getters ==========

    def get_id(self) -> int:
        """Get the line ID"""
        return self.id
    
    def get_match_id(self) -> int:
        """Get the match ID this line belongs to"""
        return self.match_id
    
    def get_line_number(self) -> int:
        """Get the line number within the match"""
        return self.line_number
    
    def get_facility_id(self) -> Optional[int]:
        """Get the facility ID (None if unscheduled)"""
        return self.facility_id
    
    def get_date(self) -> Optional[str]:
        """Get the scheduled date in YYYY-MM-DD format (None if unscheduled)"""
        return self.date
    
    def get_time(self) -> Optional[str]:
        """Get the scheduled time in HH:MM format (None if unscheduled)"""
        return self.time
    
    def get_court_number(self) -> Optional[int]:
        """Get the court number (None if not assigned)"""
        return self.court_number
    
    def get_date_time_str(self) -> Optional[str]:
        """Get combined date and time string (None if unscheduled)"""
        if self.date and self.time:
            return f"{self.date} {self.time}"
        return None
    
    def get_scheduling_info(self) -> Dict[str, Any]:
        """Get all scheduling information as a dictionary"""
        return {
            'facility_id': self.facility_id,
            'date': self.date,
            'time': self.time,
            'court_number': self.court_number,
            'is_scheduled': self.is_scheduled()
        }

    
    def is_scheduled(self) -> bool:
        """Check if the line is scheduled (has date, time, and facility)"""
        return all([self.facility_id is not None, self.date is not None, self.time is not None])
    
    def is_unscheduled(self) -> bool:
        """Check if the line is unscheduled"""
        return not self.is_scheduled()
    
    def get_status(self) -> str:
        """Get the scheduling status of the line"""
        return "scheduled" if self.is_scheduled() else "unscheduled"
    
    def schedule(self, facility_id: int, date: str, time: str, court_number: Optional[int] = None) -> 'Line':
        """Return a new Line instance with scheduling information"""
        return Line(
            id=self.id,
            match_id=self.match_id,
            line_number=self.line_number,
            facility_id=facility_id,
            date=date,
            time=time,
            court_number=court_number
        )
    
    def unschedule(self) -> 'Line':
        """Return a new Line instance without scheduling information"""
        return Line(
            id=self.id,
            match_id=self.match_id,
            line_number=self.line_number,
            facility_id=None,
            date=None,
            time=None,
            court_number=None
        )

@dataclass
class Facility:
    """Represents a tennis facility with scheduling capabilities"""
    id: int
    name: str
    short_name: Optional[str] = None  # Short name for display (e.g., "VR", "TCA")
    location: Optional[str] = None
    schedule: WeeklySchedule = field(default_factory=WeeklySchedule)
    unavailable_dates: List[str] = field(default_factory=list)  # List of dates in "YYYY-MM-DD" format
    total_courts: int = 0  # Total number of courts at the facility
    
    def __post_init__(self):
        """Validate facility data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Facility name must be a non-empty string")
        
        # Validate short_name
        if self.short_name is not None:
            if not isinstance(self.short_name, str) or not self.short_name.strip():
                raise ValueError("Short name must be a non-empty string or None")
            if len(self.short_name) > 10:
                raise ValueError("Short name must be 10 characters or less")
        
        if self.location is not None and not isinstance(self.location, str):
            raise ValueError("Location must be a string or None")
        
        if not isinstance(self.schedule, WeeklySchedule):
            raise ValueError("Schedule must be a WeeklySchedule object")
        
        if not isinstance(self.unavailable_dates, list):
            raise ValueError("Unavailable dates must be a list")
        
        if not isinstance(self.total_courts, int) or self.total_courts < 0:
            raise ValueError(f"Total courts must be a non-negative integer, got: {self.total_courts}")
        
        # Validate date formats in unavailable_dates
        for date_str in self.unavailable_dates:
            if not isinstance(date_str, str):
                raise ValueError(f"All unavailable dates must be strings, got: {type(date_str)}")
            try:
                # Validate YYYY-MM-DD format
                parts = date_str.split('-')
                if len(parts) != 3:
                    raise ValueError("Invalid date format")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                    raise ValueError("Invalid date values")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD format")

    # ========== Facility Class Getters ==========

    def get_id(self) -> int:
        """Get the facility ID"""
        return self.id
    
    def get_name(self) -> str:
        """Get the facility name"""
        return self.name
    
    def get_short_name(self) -> Optional[str]:
        """Get the short name (abbreviation)"""
        return self.short_name
    
    def get_location(self) -> Optional[str]:
        """Get the facility location"""
        return self.location
    
    def get_schedule(self) -> WeeklySchedule:
        """Get the weekly schedule"""
        return self.schedule
    
    def get_unavailable_dates(self) -> List[str]:
        """Get list of unavailable dates in YYYY-MM-DD format"""
        return self.unavailable_dates.copy()
    
    def get_total_courts(self) -> int:
        """Get the total number of courts at the facility"""
        return self.total_courts
    
    def get_unavailable_dates_count(self) -> int:
        """Get the number of unavailable dates"""
        return len(self.unavailable_dates)
    
    def get_facility_summary(self) -> Dict[str, Any]:
        """Get a summary of facility information"""
        return {
            'id': self.id,
            'name': self.name,
            'short_name': self.short_name,
            'location': self.location,
            'total_courts': self.total_courts,
            'unavailable_dates_count': len(self.unavailable_dates),
            'has_schedule': any(day.has_availability() for day in self.schedule.get_all_days().values())
        }
    
    def get_available_dates_in_range(self, start_date: str, end_date: str) -> List[str]:
        """Get all available dates in a date range"""
        from datetime import datetime, timedelta
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        available_dates = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_str = current_dt.strftime('%Y-%m-%d')
            if self.is_available_on_date(date_str):
                available_dates.append(date_str)
            current_dt += timedelta(days=1)
        
        return available_dates


    def generate_short_name(self, max_length: int = 10) -> str:
        """
        Generate a short name (abbreviation) from the facility's full name.
        
        Args:
            max_length: Maximum length for the short name (default 10, matching validation)
            
        Returns:
            A short name/abbreviation of the facility name
            
        Examples:
            "Valley Ranch Tennis Club" -> "VRTC"
            "Tennis Center of Albuquerque" -> "TCA"
            "Rio Rancho Tennis Complex" -> "RRTC"
            "Sandia Peak Tennis" -> "SPT"
        """
        if not self.name or not self.name.strip():
            return "UNK"  # Unknown
        
        # Clean and normalize the name
        name = self.name.strip()
        
        # Remove common words that don't add meaning to abbreviations
        stop_words = {
            'the', 'of', 'at', 'in', 'on', 'and', 'or', 'but', 'for', 'with',
            'a', 'an', 'de', 'del', 'la', 'las', 'los', 'el'
        }
        
        # Split into words and filter
        words = re.findall(r'\b\w+\b', name.lower())
        meaningful_words = [word for word in words if word not in stop_words]
        
        # If we filtered out everything, use original words
        if not meaningful_words:
            meaningful_words = re.findall(r'\b\w+\b', name.lower())
        
        # Strategy 1: Try initials of meaningful words
        if len(meaningful_words) <= 5:  # Reasonable number of words
            initials = ''.join(word[0].upper() for word in meaningful_words)
            if len(initials) <= max_length:
                return initials
        
        # Strategy 2: Try initials of first few words if too many
        if len(meaningful_words) > 5:
            first_words = meaningful_words[:4]  # Take first 4 words
            initials = ''.join(word[0].upper() for word in first_words)
            if len(initials) <= max_length:
                return initials
        
        # Strategy 3: Use first word + initials of rest
        if len(meaningful_words) >= 2:
            first_word = meaningful_words[0]
            rest_initials = ''.join(word[0].upper() for word in meaningful_words[1:])
            
            # Try different combinations
            combinations = [
                first_word[:3].upper() + rest_initials,  # First 3 chars + initials
                first_word[:4].upper() + rest_initials,  # First 4 chars + initials
                first_word[:2].upper() + rest_initials,  # First 2 chars + initials
            ]
            
            for combo in combinations:
                if len(combo) <= max_length:
                    return combo
        
        # Strategy 4: Truncate first word if single word or nothing else works
        if len(meaningful_words) >= 1:
            first_word = meaningful_words[0].upper()
            if len(first_word) <= max_length:
                return first_word
            else:
                return first_word[:max_length]
        
        # Fallback: Just truncate the original name
        clean_name = re.sub(r'[^A-Za-z0-9]', '', name).upper()
        return clean_name[:max_length] if clean_name else "FACILITY"
    
    def set_short_name(self, short_name: Optional[str]) -> None:
        """
        Set the short name, with validation.
        
        Args:
            short_name: The short name to set, or None to clear it
        """
        if short_name is not None:
            if not isinstance(short_name, str) or not short_name.strip():
                raise ValueError("Short name must be a non-empty string or None")
            if len(short_name) > 10:
                raise ValueError("Short name must be 10 characters or less")
        
        self.short_name = short_name
    
    def auto_generate_short_name(self) -> str:
        """
        Generate and set a short name if one doesn't exist.
        
        Returns:
            The generated short name
        """
        if self.short_name is None:
            self.short_name = self.generate_short_name()
        return self.short_name
    
    def get_display_name(self) -> str:
        """Get the display name (short_name if available, otherwise generate one)"""
        if self.short_name:
            return self.short_name
        else:
            # Auto-generate short name if not set
            return self.generate_short_name()
    
    def get_full_display_name(self) -> str:
        """Get full display name with both names if short_name exists"""
        current_short_name = self.short_name or self.generate_short_name()
        if current_short_name and current_short_name != self.name:
            return f"{current_short_name} ({self.name})"
        return self.name
    
    def ensure_short_name(self) -> str:
        """
        Ensure the facility has a short name, generating one if needed.
        This modifies the facility object if short_name was None.
        
        Returns:
            The short name (existing or newly generated)
        """
        if self.short_name is None:
            self.short_name = self.generate_short_name()
        return self.short_name
    
    def add_unavailable_date(self, date_str: str) -> None:
        """Add a date to the unavailable dates list"""
        # Validate the date format first
        try:
            parts = date_str.split('-')
            if len(parts) != 3:
                raise ValueError("Invalid date format")
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                raise ValueError("Invalid date values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD format")
        
        if date_str not in self.unavailable_dates:
            self.unavailable_dates.append(date_str)
    
    def remove_unavailable_date(self, date_str: str) -> None:
        """Remove a date from the unavailable dates list"""
        if date_str in self.unavailable_dates:
            self.unavailable_dates.remove(date_str)
    
    def is_available_on_date(self, date_str: str) -> bool:
        """Check if the facility is available on a specific date"""
        return date_str not in self.unavailable_dates
    
    def get_available_courts_on_day_time(self, day: str, time: str) -> Optional[int]:
        """Get the number of available courts for a specific day and time"""
        try:
            day_schedule = self.schedule.get_day_schedule(day)
            return day_schedule.get_available_courts_at_time(time)
        except ValueError:
            return None
    
    def has_availability_on_day(self, day: str) -> bool:
        """Check if the facility has any availability on a specific day of the week"""
        try:
            day_schedule = self.schedule.get_day_schedule(day)
            return day_schedule.has_availability()
        except ValueError:
            return False
    
    def can_accommodate_lines(self, day: str, time: str, num_lines: int) -> bool:
        """
        Check if the facility can accommodate the required number of lines at a specific day/time
        
        Args:
            day: Day of the week
            time: Time in HH:MM format
            num_lines: Number of lines (courts) needed
            
        Returns:
            True if facility has enough courts available
        """
        available_courts = self.get_available_courts_on_day_time(day, time)
        return available_courts is not None and available_courts >= num_lines
    
    def get_available_times_for_lines(self, day: str, num_lines: int) -> List[str]:
        """
        Get all available times on a day that can accommodate the required number of lines
        
        Args:
            day: Day of the week
            num_lines: Number of lines (courts) needed
            
        Returns:
            List of time strings that have enough courts available
        """
        try:
            day_schedule = self.schedule.get_day_schedule(day)
            return day_schedule.get_times_with_min_courts(num_lines)
        except ValueError:
            return []
    
    def get_scheduling_options_for_match(self, league, date_str: str) -> Dict[str, List[str]]:
        """
        Get all scheduling options for a match on a specific date
        
        Args:
            league: League object to get line requirements
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary mapping day of week to list of available times
        """
        if not self.is_available_on_date(date_str):
            return {}
        
        # Get day of week from date
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')  # Full day name (Monday, Tuesday, etc.)
        except ValueError:
            return {}
        
        num_lines = league.get_total_courts_needed()
        available_times = self.get_available_times_for_lines(day_name, num_lines)
        
        if available_times:
            return {day_name: available_times}
        else:
            return {}
    
    def find_scheduling_slots_for_split_lines(self, day: str, num_lines: int, 
                                            max_time_gap_minutes: int = 120) -> List[List[Tuple[str, int]]]:
        """
        Find scheduling slots when lines can be split across different times
        
        Args:
            day: Day of the week
            num_lines: Total number of lines needed
            max_time_gap_minutes: Maximum time gap between line start times (default 2 hours)
            
        Returns:
            List of scheduling options, where each option is a list of (time, courts_at_time) tuples
        """
        try:
            day_schedule = self.schedule.get_day_schedule(day)
        except ValueError:
            return []
        
        if not day_schedule.start_times:
            return []
        
        # Get all available time slots with court counts
        time_slots = [(slot.time, slot.available_courts) for slot in day_schedule.start_times 
                     if slot.available_courts > 0]
        
        if not time_slots:
            return []
        
        # Convert times to minutes for gap calculation
        def time_to_minutes(time_str):
            parts = time_str.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        
        # Find combinations that sum to required lines
        scheduling_options = []
        
        # Try single time slot first (preferred)
        for time_str, courts in time_slots:
            if courts >= num_lines:
                scheduling_options.append([(time_str, num_lines)])
        
        # Try combinations of time slots if single slot isn't enough
        if not scheduling_options:
            for r in range(2, min(len(time_slots) + 1, num_lines + 1)):
                for combination in itertools.combinations(time_slots, r):
                    # Check if times are within max gap
                    times_minutes = [time_to_minutes(time_str) for time_str, _ in combination]
                    if max(times_minutes) - min(times_minutes) <= max_time_gap_minutes:
                        # Check if total courts meet requirement
                        total_available = sum(courts for _, courts in combination)
                        if total_available >= num_lines:
                            # Distribute lines across time slots
                            lines_distribution = []
                            remaining_lines = num_lines
                            for time_str, courts in combination:
                                lines_for_slot = min(courts, remaining_lines)
                                if lines_for_slot > 0:
                                    lines_distribution.append((time_str, lines_for_slot))
                                    remaining_lines -= lines_for_slot
                                if remaining_lines == 0:
                                    break
                            
                            if remaining_lines == 0:
                                scheduling_options.append(lines_distribution)
        
        return scheduling_options
    
    @classmethod
    def from_yaml_dict(cls, data: Dict[str, Any]) -> 'Facility':
        """Create a Facility from a YAML dictionary structure"""
        # Extract basic facility info
        facility_id = data.get('id')
        name = data.get('name')
        short_name = data.get('short_name')
        location = data.get('location')
        total_courts = data.get('total_courts', 0)
        
        # Require schedule to be present
        if 'schedule' not in data:
            raise ValueError(f"Facility '{name}' (ID: {facility_id}) is missing required 'schedule' field")
        
        # Require unavailable_dates to be present (can be empty list)
        if 'unavailable_dates' not in data:
            raise ValueError(f"Facility '{name}' (ID: {facility_id}) is missing required 'unavailable_dates' field")
        
        # Create the facility with basic info first
        facility = cls(
            id=facility_id, 
            name=name, 
            short_name=short_name,
            location=location, 
            total_courts=total_courts
        )
        
        # Auto-generate short_name if not provided
        if facility.short_name is None:
            facility.auto_generate_short_name()
        
        # Process schedule data - now required
        schedule_data = data['schedule']
        if not isinstance(schedule_data, dict):
            raise ValueError(f"Facility '{name}' schedule must be a dictionary with day names as keys")
        
        # Validate that all 7 days are present
        required_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
        provided_days = set(schedule_data.keys())
        
        missing_days = required_days - provided_days
        if missing_days:
            raise ValueError(f"Facility '{name}' schedule is missing required days: {sorted(missing_days)}")
        
        extra_days = provided_days - required_days
        if extra_days:
            raise ValueError(f"Facility '{name}' schedule has invalid day names: {sorted(extra_days)}")
        
        # Process each day's schedule
        for day_name, day_data in schedule_data.items():
            if not isinstance(day_data, dict):
                raise ValueError(f"Facility '{name}' schedule for {day_name} must be a dictionary")
            
            if 'start_times' not in day_data:
                raise ValueError(f"Facility '{name}' schedule for {day_name} is missing 'start_times' field")
            
            start_times_data = day_data['start_times']
            if not isinstance(start_times_data, list):
                raise ValueError(f"Facility '{name}' start_times for {day_name} must be a list")
            
            day_schedule = DaySchedule()
            for i, time_slot_data in enumerate(start_times_data):
                if not isinstance(time_slot_data, dict):
                    raise ValueError(f"Facility '{name}' {day_name} time slot {i} must be a dictionary")
                
                if 'time' not in time_slot_data:
                    raise ValueError(f"Facility '{name}' {day_name} time slot {i} is missing 'time' field")
                
                if 'available_courts' not in time_slot_data:
                    raise ValueError(f"Facility '{name}' {day_name} time slot {i} is missing 'available_courts' field")
                
                time_slot = TimeSlot(
                    time=time_slot_data['time'],
                    available_courts=time_slot_data['available_courts']
                )
                day_schedule.start_times.append(time_slot)
            
            facility.schedule.set_day_schedule(day_name, day_schedule)
        
        # Process unavailable dates - now required
        unavailable_dates = data['unavailable_dates']
        if not isinstance(unavailable_dates, list):
            raise ValueError(f"Facility '{name}' unavailable_dates must be a list")
        
        facility.unavailable_dates = unavailable_dates.copy()
        
        return facility
    
    def to_yaml_dict(self) -> Dict[str, Any]:
        """Convert facility to YAML-serializable dictionary with debug logging"""
        logger.debug("Starting to_yaml_dict for facility id=%s name=%s", self.id, self.name)
        try:
            # Build schedule dictionary
            schedule_dict = {}
            if hasattr(self, 'schedule') and self.schedule:
                all_days = self.schedule.get_all_days()
                logger.debug("Found schedule with days: %s", list(all_days.keys()))
                for day_name, day_schedule in all_days.items():
                    if hasattr(day_schedule, 'start_times') and day_schedule.start_times:
                        logger.debug("Processing day '%s' with %d time slots", day_name, len(day_schedule.start_times))
                        # Convert start_times list to dictionary format
                        time_slots = {}
                        for time_slot in day_schedule.start_times:
                            logger.debug(
                                "Day %s: time_slot time=%s available_courts=%s",
                                day_name,
                                time_slot.time,
                                time_slot.available_courts
                            )
                            time_slots[time_slot.time] = time_slot.available_courts
                        schedule_dict[day_name] = time_slots
            else:
                logger.debug("No schedule attribute or schedule is empty")

            # Build the facility dictionary
            facility_dict = {
                'id': self.id,
                'name': self.name,
                'location': getattr(self, 'location', '') or '',
                'total_courts': getattr(self, 'total_courts', 0),
                'schedule': schedule_dict,
                'unavailable_dates': getattr(self, 'unavailable_dates', []) or []
            }
            logger.debug("Basic facility_dict constructed: %s", facility_dict)

            # Add short_name if it exists and is different from name
            if hasattr(self, 'short_name') and self.short_name and self.short_name != self.name:
                facility_dict['short_name'] = self.short_name
                logger.debug("Added short_name: %s", self.short_name)

            logger.debug("Finished to_yaml_dict for facility id=%s", self.id)
            return facility_dict

        except Exception as e:
            logger.exception("Error converting facility %s to YAML dict", self.id)
            raise Exception(f"Error converting facility {self.id} to YAML dict: {str(e)}")
