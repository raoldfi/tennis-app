from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
import itertools
import re
from collections import defaultdict

# Predefined USTA categories for validation
USTA_SECTIONS = [
    "Caribbean",
    "Eastern", 
    "Florida",
    "Hawaii Pacific",
    "Intermountain",
    "Mid-Atlantic",
    "Middle States", 
    "Midwest",
    "Missouri Valley",
    "New England",
    "Northern",
    "Northern California",
    "Pacific Northwest",
    "Southern",
    "Southern California",
    "Southwest",
    "Texas"
]

USTA_REGIONS = [
    "Northern New Mexico",
    "Southern New Mexico", 
    "West Texas",
    "North Texas",
    "Central Texas",
    "East Texas",
    "South Texas",
    "Northern California",
    "Central California",
    "Southern California",
    "Arizona",
    "Nevada",
    "Utah",
    "Colorado"
]

USTA_AGE_GROUPS = [
    "18 & Over",
    "40 & Over", 
    "55 & Over",
    "65 & Over"
]

USTA_DIVISIONS = [
    "2.5 Women",
    "3.0 Women", 
    "3.5 Women",
    "4.0 Women",
    "4.5 Women",
    "5.0 Women",
    "2.5 Men",
    "3.0 Men",
    "3.5 Men", 
    "4.0 Men",
    "4.5 Men",
    "5.0 Men",
    "6.0 Mixed",
    "7.0 Mixed",
    "8.0 Mixed",
    "9.0 Mixed",
    "10.0 Mixed"
]

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
        """Convert the facility to a YAML-compatible dictionary structure"""
        result = {
            'id': self.id,
            'name': self.name
        }
        
        # Include short_name if present (or generate one)
        current_short_name = self.short_name or self.generate_short_name()
        if current_short_name:
            result['short_name'] = current_short_name
        
        if self.location:
            result['location'] = self.location
        
        if self.total_courts > 0:
            result['total_courts'] = self.total_courts
        
        # Add schedule if it has any time slots
        schedule_dict = {}
        for day_name, day_schedule in self.schedule.get_all_days().items():
            if day_schedule.start_times:
                schedule_dict[day_name] = {
                    'start_times': [
                        {
                            'time': slot.time,
                            'available_courts': slot.available_courts
                        }
                        for slot in day_schedule.start_times
                    ]
                }
            else:
                schedule_dict[day_name] = {'start_times': []}
        
        if any(day_data['start_times'] for day_data in schedule_dict.values()):
            result['schedule'] = schedule_dict
        
        # Add unavailable dates if any
        if self.unavailable_dates:
            result['unavailable_dates'] = self.unavailable_dates.copy()
        
        return result

@dataclass
class League:
    """Represents a tennis league"""
    id: int
    name: str
    year: int
    section: str
    region: str
    age_group: str
    division: str
    num_lines_per_match: int = 3  # Default to 3 lines per match (common for team tennis)
    num_matches: int = 10  # Default number of matches per team in the league
    allow_split_lines: bool = False  # Whether lines can be split across different time slots
    preferred_days: List[str] = field(default_factory=list)  # Preferred days for scheduling (e.g., ["Saturday", "Sunday"])
    backup_days: List[str] = field(default_factory=list)  # Backup days for scheduling
    start_date: Optional[str] = None  # League start date in YYYY-MM-DD format
    end_date: Optional[str] = None  # League end date in YYYY-MM-DD format
    
    def __post_init__(self):
        """Validate league data against USTA constants"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"League ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("League name must be a non-empty string")
        
        if not isinstance(self.year, int) or self.year < 1900 or self.year > 2100:
            raise ValueError(f"Year must be between 1900 and 2100, got: {self.year}")
        
        if self.section not in USTA_SECTIONS:
            raise ValueError(f"Invalid section: {self.section}. Must be one of: {USTA_SECTIONS}")
        
        if self.region not in USTA_REGIONS:
            raise ValueError(f"Invalid region: {self.region}. Must be one of: {USTA_REGIONS}")
        
        if self.age_group not in USTA_AGE_GROUPS:
            raise ValueError(f"Invalid age group: {self.age_group}. Must be one of: {USTA_AGE_GROUPS}")
        
        if self.division not in USTA_DIVISIONS:
            raise ValueError(f"Invalid division: {self.division}. Must be one of: {USTA_DIVISIONS}")
        
        if not isinstance(self.num_lines_per_match, int) or self.num_lines_per_match <= 0:
            raise ValueError(f"Number of lines per match must be a positive integer, got: {self.num_lines_per_match}")
        
        # Validate reasonable range for lines per match (1-10 is typical)
        if self.num_lines_per_match > 10:
            raise ValueError(f"Number of lines per match seems unusually high: {self.num_lines_per_match}. Expected 1-10.")
        
        # Validate num_matches
        if not isinstance(self.num_matches, int) or self.num_matches <= 0:
            raise ValueError(f"Number of matches must be a positive integer, got: {self.num_matches}")
        
        if self.num_matches > 50:
            raise ValueError(f"Number of matches seems unusually high: {self.num_matches}. Expected 1-50.")
        
        # Validate allow_split_lines
        if not isinstance(self.allow_split_lines, bool):
            raise ValueError(f"allow_split_lines must be a boolean, got: {type(self.allow_split_lines)}")
        
        # Validate preferred_days and backup_days
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        if not isinstance(self.preferred_days, list):
            raise ValueError("preferred_days must be a list")
        
        for day in self.preferred_days:
            if not isinstance(day, str) or day not in valid_days:
                raise ValueError(f"Invalid preferred day: {day}. Must be one of: {valid_days}")
        
        if not isinstance(self.backup_days, list):
            raise ValueError("backup_days must be a list")
        
        for day in self.backup_days:
            if not isinstance(day, str) or day not in valid_days:
                raise ValueError(f"Invalid backup day: {day}. Must be one of: {valid_days}")
        
        # Check for overlap between preferred and backup days
        overlapping_days = set(self.preferred_days) & set(self.backup_days)
        if overlapping_days:
            raise ValueError(f"Days cannot be both preferred and backup: {sorted(overlapping_days)}")
        
        # Validate start_date and end_date formats
        if self.start_date is not None:
            if not isinstance(self.start_date, str):
                raise ValueError("start_date must be a string or None")
            try:
                parts = self.start_date.split('-')
                if len(parts) != 3:
                    raise ValueError("Invalid start_date format")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                    raise ValueError("Invalid start_date values")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid start_date format: '{self.start_date}'. Expected YYYY-MM-DD format")
        
        if self.end_date is not None:
            if not isinstance(self.end_date, str):
                raise ValueError("end_date must be a string or None")
            try:
                parts = self.end_date.split('-')
                if len(parts) != 3:
                    raise ValueError("Invalid end_date format")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                    raise ValueError("Invalid end_date values")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid end_date format: '{self.end_date}'. Expected YYYY-MM-DD format")
        
        # Validate that end_date is after start_date
        if self.start_date and self.end_date:
            from datetime import datetime
            try:
                start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
                if end_dt <= start_dt:
                    raise ValueError(f"end_date ({self.end_date}) must be after start_date ({self.start_date})")
            except ValueError as e:
                if "does not match format" in str(e):
                    pass  # Date format validation already handled above
                else:
                    raise

    # ========== League Class Getters ==========

    def get_id(self) -> int:
        """Get the league ID"""
        return self.id
    
    def get_name(self) -> str:
        """Get the league name"""
        return self.name
    
    def get_year(self) -> int:
        """Get the league year"""
        return self.year
    
    def get_section(self) -> str:
        """Get the USTA section"""
        return self.section
    
    def get_region(self) -> str:
        """Get the USTA region"""
        return self.region
    
    def get_age_group(self) -> str:
        """Get the age group"""
        return self.age_group
    
    def get_division(self) -> str:
        """Get the division"""
        return self.division
    
    def get_num_lines_per_match(self) -> int:
        """Get the number of lines per match"""
        return self.num_lines_per_match
    
    def get_num_matches(self) -> int:
        """Get the number of matches per team"""
        return self.num_matches
    
    def get_allow_split_lines(self) -> bool:
        """Get whether lines can be split across time slots"""
        return self.allow_split_lines
    
    def get_preferred_days(self) -> List[str]:
        """Get the list of preferred scheduling days"""
        return self.preferred_days.copy()
    
    def get_backup_days(self) -> List[str]:
        """Get the list of backup scheduling days"""
        return self.backup_days.copy()
    
    def get_start_date(self) -> Optional[str]:
        """Get the league start date in YYYY-MM-DD format"""
        return self.start_date
    
    def get_end_date(self) -> Optional[str]:
        """Get the league end date in YYYY-MM-DD format"""
        return self.end_date
    
    def get_preferred_days_count(self) -> int:
        """Get the number of preferred days"""
        return len(self.preferred_days)
    
    def get_backup_days_count(self) -> int:
        """Get the number of backup days"""
        return len(self.backup_days)
    
    def get_total_scheduling_days_count(self) -> int:
        """Get the total number of available scheduling days"""
        return len(self.get_all_scheduling_days())
    
    def get_league_type(self) -> str:
        """Get league type based on division (e.g., 'Men', 'Women', 'Mixed')"""
        if 'Men' in self.division:
            return 'Men'
        elif 'Women' in self.division:
            return 'Women'
        elif 'Mixed' in self.division:
            return 'Mixed'
        else:
            return 'Unknown'
    
    def get_skill_level(self) -> str:
        """Extract skill level from division (e.g., '3.0', '4.5')"""
        import re
        match = re.search(r'(\d+\.?\d*)', self.division)
        return match.group(1) if match else 'Unknown'
    
    def get_league_description(self) -> str:
        """Get a descriptive string for the league"""
        return f"{self.year} {self.region} {self.age_group} {self.division}"
    
    def get_date_range_info(self) -> Dict[str, Any]:
        """Get information about the league's date range"""
        info = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'has_dates': bool(self.start_date and self.end_date),
            'duration_days': self.get_season_duration_days(),
            'duration_weeks': self.get_season_duration_weeks()
        }
        if info['has_dates']:
            info['status'] = self.get_season_status()
        return info
    


    
    def get_total_courts_needed(self) -> int:
        """Calculate total courts needed for a match (lines per match)"""
        return self.num_lines_per_match
    
    def get_match_duration_estimate(self, minutes_per_line: int = 120) -> int:
        """
        Estimate match duration in minutes
        
        Args:
            minutes_per_line: Average time per line in minutes (default 120 = 2 hours)
            
        Returns:
            Estimated total match duration in minutes
        """
        return self.num_lines_per_match * minutes_per_line
    
    def get_total_match_duration_estimate(self, minutes_per_line: int = 120) -> int:
        """
        Estimate total duration if lines are played sequentially (when allow_split_lines is False)
        
        Args:
            minutes_per_line: Average time per line in minutes (default 120 = 2 hours)
            
        Returns:
            Estimated total duration in minutes if all lines played sequentially
        """
        if self.allow_split_lines:
            # If lines can be split, matches could potentially be shorter
            return minutes_per_line  # Just one line's worth of time
        else:
            # All lines must be played at the same time, so duration is just per line
            return minutes_per_line
    
    def get_format_description(self) -> str:
        """Get a description of the match format based on division and lines"""
        format_descriptions = {
            1: "Singles format",
            2: "Doubles format",
            3: "Standard team format (3 lines)",
            4: "Extended team format (4 lines)", 
            5: "Full team format (5 lines)"
        }
        
        base_desc = format_descriptions.get(self.num_lines_per_match, f"Custom format ({self.num_lines_per_match} lines)")
        
        if self.allow_split_lines:
            base_desc += " - Lines can be split across time slots"
        else:
            base_desc += " - All lines must start simultaneously"
        
        return base_desc
    
    def is_team_format(self) -> bool:
        """Check if this is a team format (multiple lines) vs individual format"""
        return self.num_lines_per_match > 2
    
    def get_all_scheduling_days(self) -> List[str]:
        """Get all days that can be used for scheduling (preferred + backup)"""
        return list(set(self.preferred_days + self.backup_days))
    
    def can_schedule_on_day(self, day: str) -> bool:
        """Check if matches can be scheduled on a specific day"""
        return day in self.preferred_days or day in self.backup_days
    
    def is_preferred_day(self, day: str) -> bool:
        """Check if a day is a preferred scheduling day"""
        return day in self.preferred_days
    
    def is_backup_day(self, day: str) -> bool:
        """Check if a day is a backup scheduling day"""
        return day in self.backup_days
    
    def get_scheduling_priority(self, day: str) -> int:
        """
        Get scheduling priority for a day
        
        Returns:
            1 for preferred days, 2 for backup days, 3 for unavailable days
        """
        if day in self.preferred_days:
            return 1
        elif day in self.backup_days:
            return 2
        else:
            return 3
    
    def estimate_season_duration_weeks(self) -> int:
        """
        Estimate how many weeks the season might last based on number of matches
        Assumes roughly 1 match per team per week
        """
        return max(self.num_matches, 4)  # Minimum 4 weeks for any season
    
    def get_season_duration_days(self) -> Optional[int]:
        """
        Get the actual season duration in days if start_date and end_date are set
        
        Returns:
            Number of days between start_date and end_date, or None if dates not set
        """
        if not self.start_date or not self.end_date:
            return None
        
        from datetime import datetime
        try:
            start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            return (end_dt - start_dt).days
        except ValueError:
            return None
    
    def get_season_duration_weeks(self) -> Optional[float]:
        """
        Get the actual season duration in weeks if start_date and end_date are set
        
        Returns:
            Number of weeks between start_date and end_date, or None if dates not set
        """
        days = self.get_season_duration_days()
        return days / 7.0 if days is not None else None
    
    def is_active_on_date(self, date_str: str) -> bool:
        """
        Check if the league is active on a specific date
        
        Args:
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            True if league is active on that date, False otherwise
        """
        if not self.start_date or not self.end_date:
            # If no dates set, assume league could be active
            return True
        
        try:
            from datetime import datetime
            check_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            return start_dt <= check_date <= end_dt
        except ValueError:
            return False
    
    def get_remaining_days(self, current_date: str = None) -> Optional[int]:
        """
        Get the number of days remaining in the season
        
        Args:
            current_date: Current date in YYYY-MM-DD format. If None, uses today.
            
        Returns:
            Number of days remaining, 0 if season has ended, or None if end_date not set
        """
        if not self.end_date:
            return None
        
        from datetime import datetime, date
        try:
            if current_date:
                current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            else:
                current_dt = datetime.combine(date.today(), datetime.min.time())
            
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            remaining = (end_dt - current_dt).days
            return max(0, remaining)
        except ValueError:
            return None
    
    def has_started(self, current_date: str = None) -> bool:
        """
        Check if the league season has started
        
        Args:
            current_date: Current date in YYYY-MM-DD format. If None, uses today.
            
        Returns:
            True if season has started, False if not started, True if no start_date set
        """
        if not self.start_date:
            return True  # Assume started if no start date
        
        from datetime import datetime, date
        try:
            if current_date:
                current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            else:
                current_dt = datetime.combine(date.today(), datetime.min.time())
            
            start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
            return current_dt >= start_dt
        except ValueError:
            return True
    
    def has_ended(self, current_date: str = None) -> bool:
        """
        Check if the league season has ended
        
        Args:
            current_date: Current date in YYYY-MM-DD format. If None, uses today.
            
        Returns:
            True if season has ended, False if still active, False if no end_date set
        """
        if not self.end_date:
            return False  # Assume not ended if no end date
        
        from datetime import datetime, date
        try:
            if current_date:
                current_dt = datetime.strptime(current_date, '%Y-%m-%d')
            else:
                current_dt = datetime.combine(date.today(), datetime.min.time())
            
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            return current_dt > end_dt
        except ValueError:
            return False
    
    def get_season_status(self, current_date: str = None) -> str:
        """
        Get a human-readable season status
        
        Args:
            current_date: Current date in YYYY-MM-DD format. If None, uses today.
            
        Returns:
            One of: "Not Started", "Active", "Ended", "Unknown"
        """
        if not self.start_date and not self.end_date:
            return "Unknown"
        
        if not self.has_started(current_date):
            return "Not Started"
        elif self.has_ended(current_date):
            return "Ended"
        else:
            return "Active"

    def generate_matches(self, teams: List['Team']) -> List['Match']:
        """
        Generate a list of unscheduled Match objects from the list of teams.
        
        Updated to work with teams that have string facility names instead of facility IDs.
        
        This algorithm ensures:
        - Fair distribution of matches for each team
        - Balanced home/away games
        - Optimal pairing distribution
        - Handles odd numbers of teams by adjusting match count
        - Deterministic sequential match IDs that prevent duplicate scheduling
        
        Match IDs are generated deterministically: the same league always gets the same
        starting match ID, then matches are numbered sequentially. This ensures that
        regenerating matches for the same league produces the identical sequence of IDs.
        
        Args:
            teams: List of Team objects in this league
            
        Returns:
            List of Match objects with deterministic sequential IDs (unscheduled)
            
        Raises:
            ValueError: If teams list is invalid
        """
        # Import itertools if not already available
        import itertools
        from collections import defaultdict
        
        if len(teams) < 2:
            raise ValueError("Need at least 2 teams to generate matches")
        
        # Validate all teams are in this league
        for team in teams:
            if not isinstance(team, Team):
                raise ValueError("All items in teams list must be Team objects")
            if team.league.id != self.id:
                raise ValueError(f"Team {team.name} (ID: {team.id}) is not in league {self.name} (ID: {self.id})")
        
        team_list = teams
        num_matches = self.num_matches
        
        # Generate all permutations of team pairs
        permutations = list(itertools.permutations(team_list, 2))
        total_usage_counts = defaultdict(int)  # Use team IDs as keys
        first_usage_counts = defaultdict(int)  # Tracks home game counts (use team IDs)
        selected_pairs = []
        pair_counts = defaultdict(int)  # Use tuple of team IDs as keys
        
        # If odd number of teams, adjust num_matches to be fair
        if len(team_list) % 2 == 1:
            n = len(team_list)
            k = num_matches // (n - 1)
            m = num_matches % (n - 1)
            if m > 0:
                num_matches = (k + 1) * (n - 1)
            else:
                num_matches = k * (n - 1)
        
        # Calculate total number of pairs needed
        num_pairs = num_matches * len(team_list) // 2
        
        # Keep backup of all permutations
        backup_permutations = permutations.copy()
        
        # Select pairs iteratively
        for _ in range(num_pairs):
            # Sort permutations by total usage (least used teams first), then by home game balance
            # Use team IDs for dictionary lookups
            permutations.sort(key=lambda pair: (
                total_usage_counts[pair[0].id] + total_usage_counts[pair[1].id], 
                first_usage_counts[pair[0].id]
            ))
            
            # If we run out of permutations, reset to backup
            if not permutations:
                permutations = backup_permutations.copy()
            
            if permutations:
                selected_pair = permutations.pop(0)
                inverse_pair = (selected_pair[1], selected_pair[0])
                
                # Choose home/away based on balance
                # If first team has more home games than second team, swap them
                if first_usage_counts[selected_pair[0].id] > first_usage_counts[selected_pair[1].id]:
                    selected_pair = inverse_pair
                
                # Create hashable keys for pair counting (using team IDs)
                selected_pair_key = (selected_pair[0].id, selected_pair[1].id)
                inverse_pair_key = (selected_pair[1].id, selected_pair[0].id)
                
                # If this exact pairing has been used more than its inverse, use the inverse
                if pair_counts[selected_pair_key] > pair_counts[inverse_pair_key]:
                    selected_pair = inverse_pair
                    selected_pair_key = inverse_pair_key
                
                # Add the selected pair
                selected_pairs.append(selected_pair)
                
                # Update usage counts using team IDs as keys
                total_usage_counts[selected_pair[0].id] += 1  # Home team total matches
                total_usage_counts[selected_pair[1].id] += 1  # Away team total matches
                first_usage_counts[selected_pair[0].id] += 1  # Home team home matches
                pair_counts[selected_pair_key] += 1             # This specific pairing count
                
                # Remove the used pair and its inverse from available permutations
                # Compare by team IDs to ensure proper matching
                selected_ids = (selected_pair[0].id, selected_pair[1].id)
                inverse_ids = (selected_pair[1].id, selected_pair[0].id)
                permutations = [p for p in permutations 
                              if (p[0].id, p[1].id) != selected_ids and (p[0].id, p[1].id) != inverse_ids]
        
        # Generate deterministic starting match ID for this league
        base_match_id = self._generate_deterministic_start_id()
        
        # Convert team pairs to Match objects with sequential IDs from deterministic base
        matches = []
        for i, (home_team, visitor_team) in enumerate(selected_pairs):
            match_id = base_match_id + i + 1  # Sequential: base+1, base+2, base+3, etc.
            
            # For matches, we still need facility_id for scheduling, but we can derive it
            # from the home team's facility name. For now, we'll leave facility_id as None
            # since this is for unscheduled matches, and it will be resolved during scheduling.
            match = Match(
                id=match_id,
                league_id=self.id,
                home_team_id=home_team.id,
                visitor_team_id=visitor_team.id,
                facility_id=None,  # Will be resolved during scheduling based on home team's facility
                date=None,  # Unscheduled
                time=None   # Unscheduled
            )
            matches.append(match)
        
        return matches

    def resolve_facility_id_from_team_facility_name(self, facility_name: str, facilities_list: List['Facility']) -> Optional[int]:
        """
        Helper method to resolve a facility ID from a team's home_facility name
        
        Args:
            facility_name: The facility name from the team
            facilities_list: List of available facilities to search
            
        Returns:
            Facility ID if found, None if not found
        """
        for facility in facilities_list:
            if (facility.name == facility_name or 
                (facility.short_name and facility.short_name == facility_name)):
                return facility.id
        return None


    def set_home_facility_for_matches(self, matches: List['Match'], teams: List['Team'], 
                                    facilities_list: List['Facility']) -> List['Match']:
        """
        Set the facility_id for matches based on home team's facility name
        
        Args:
            matches: List of matches to update
            teams: List of teams (to look up facility names)
            facilities_list: List of facilities (to resolve IDs)
            
        Returns:
            List of matches with facility_id set where possible
        """
        # Create a mapping of team_id to team for quick lookup
        team_map = {team.id: team for team in teams}
        
        updated_matches = []
        for match in matches:
            # Find the home team
            home_team = team_map.get(match.home_team_id)
            if home_team:
                # Resolve facility ID from facility name
                facility_id = self.resolve_facility_id_from_team_facility_name(
                    home_team.home_facility, facilities_list
                )
                
                # Create new match with facility_id set
                updated_match = Match(
                    id=match.id,
                    league_id=match.league_id,
                    home_team_id=match.home_team_id,
                    visitor_team_id=match.visitor_team_id,
                    facility_id=facility_id,  # Now resolved
                    date=match.date,
                    time=match.time,
                    lines=match.lines.copy()
                )
                updated_matches.append(updated_match)
            else:
                # Keep original match if home team not found
                updated_matches.append(match)
        
        return updated_matches
    
    def _generate_deterministic_start_id(self) -> int:
        """
        Generate a deterministic starting match ID for this league.
        
        This creates a unique base ID that incorporates league characteristics,
        ensuring the same league always gets the same starting match ID.
        Matches are then numbered sequentially from this base.
        
        Returns:
            Deterministic starting match ID for this league
            
        Example:
            League "2025 Northern NM 18+ 3.0 Women" might get start ID: 202512340000
            Then matches become: 202512340001, 202512340002, 202512340003, etc.
            
            Regenerating the same league produces the same sequence.
        """
        import hashlib
        
        # Create identifier string from all league characteristics
        identifier = f"{self.year}_{self.region}_{self.age_group}_{self.division}_{self.id}"
        
        # Create MD5 hash of the identifier for deterministic number generation
        hash_obj = hashlib.md5(identifier.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Take first 8 characters and convert to int, then mod to get reasonable size
        hash_int = int(hash_hex[:8], 16) % 100000  # 0-99999 range
        
        # Create base ID: YYYY + 5-digit hash + 0000 (for sequential numbering)
        # Format: YYYYHHHHH0000 (13 digits total, leaves room for ~9999 matches)
        base_id = (self.year * 1000000000) + (hash_int * 10000)
        
        return base_id


@dataclass
class Team:
    """Represents a tennis team"""
    id: int
    name: str
    league: League
    home_facility: Facility  # CHANGED: from str to Facility object
    captain: Optional[str] = None
    preferred_days: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate team data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Team name must be a non-empty string")
        
        if not isinstance(self.league, League):
            raise ValueError("League must be a League object")
        
        if not isinstance(self.home_facility, Facility):  # CHANGED: validate Facility object
            raise ValueError("Home facility must be a Facility object")
        
        if self.captain is not None and (not isinstance(self.captain, str) or not self.captain.strip()):
            raise ValueError("Captain must be a non-empty string or None")
        
        # Validate preferred_days
        if not isinstance(self.preferred_days, list):
            raise ValueError("preferred_days must be a list")
        
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day in self.preferred_days:
            if not isinstance(day, str) or day not in valid_days:
                raise ValueError(f"Invalid preferred day: {day}. Must be one of: {valid_days}")

    # ========== Team Class Getters ==========

    def get_id(self) -> int:
        """Get the team ID"""
        return self.id
    
    def get_name(self) -> str:
        """Get the team name"""
        return self.name
    
    def get_league(self) -> League:
        """Get the league this team belongs to"""
        return self.league
    
    def get_home_facility(self) -> Facility:
        """Get the home facility object"""
        return self.home_facility
    
    def get_captain(self) -> Optional[str]:
        """Get the team captain name"""
        return self.captain
    
    def get_preferred_days(self) -> List[str]:
        """Get the list of preferred playing days"""
        return self.preferred_days.copy()
    
    def get_league_id(self) -> int:
        """Get the ID of the league this team belongs to"""
        return self.league.id
    
    def get_home_facility_id(self) -> int:
        """Get the ID of the home facility"""
        return self.home_facility.id
    
    def get_home_facility_name(self) -> str:
        """Get the name of the home facility"""
        return self.home_facility.name
    
    def get_home_facility_short_name(self) -> Optional[str]:
        """Get the short name of the home facility"""
        return self.home_facility.short_name
    
    def get_preferred_days_count(self) -> int:
        """Get the number of preferred days"""
        return len(self.preferred_days)
    
    def get_league_year(self) -> int:
        """Get the year of the league this team plays in"""
        return self.league.year
    
    def get_league_division(self) -> str:
        """Get the division of the league this team plays in"""
        return self.league.division
    
    def get_league_region(self) -> str:
        """Get the region of the league this team plays in"""
        return self.league.region
    
    def get_team_summary(self) -> Dict[str, Any]:
        """Get a summary of team information"""
        return {
            'id': self.id,
            'name': self.name,
            'captain': self.captain,
            'league_id': self.league.id,
            'league_name': self.league.name,
            'league_division': self.league.division,
            'home_facility_id': self.home_facility.id,
            'home_facility_name': self.home_facility.name,
            'preferred_days_count': len(self.preferred_days),
            'preferred_days': self.preferred_days.copy()
        }
    
    def get_full_team_description(self) -> str:
        """Get a full descriptive string for the team"""
        return f"{self.name} ({self.league.division} - {self.home_facility.name})"


    
    
    def can_play_on_day(self, day: str) -> bool:
        """Check if the team can play on a specific day"""
        if not self.preferred_days:
            # If no preferred days set, assume team can play any day
            return True
        return day in self.preferred_days
    
    def get_scheduling_priority(self, day: str) -> int:
        """
        Get scheduling priority for a day
        
        Returns:
            1 for preferred days, 2 for non-preferred days
        """
        if not self.preferred_days:
            return 1  # No preference means any day is fine
        
        return 1 if day in self.preferred_days else 2
    
    def add_preferred_day(self, day: str) -> None:
        """Add a day to the preferred days list"""
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        if day not in valid_days:
            raise ValueError(f"Invalid day: {day}. Must be one of: {valid_days}")
        
        if day not in self.preferred_days:
            self.preferred_days.append(day)
    
    def remove_preferred_day(self, day: str) -> None:
        """Remove a day from the preferred days list"""
        if day in self.preferred_days:
            self.preferred_days.remove(day)
    
    def has_preferred_days(self) -> bool:
        """Check if the team has any preferred days set"""
        return len(self.preferred_days) > 0
    
    def get_preferred_days_formatted(self) -> str:
        """Get preferred days as a formatted string"""
        if not self.preferred_days:
            return "No preference"
        return ", ".join(self.preferred_days)
    
    def conflicts_with_league_days(self) -> List[str]:
        """
        Check if team's preferred days conflict with league's scheduling days
        
        Returns:
            List of conflicting days (team prefers but league doesn't schedule on)
        """
        if not self.preferred_days:
            return []
        
        league_days = set(self.league.get_all_scheduling_days())
        if not league_days:
            return []  # League has no scheduling restrictions
        
        team_days = set(self.preferred_days)
        conflicts = team_days - league_days
        return list(conflicts)
    
    def get_compatible_days(self) -> List[str]:
        """
        Get days that are compatible with both team preferences and league scheduling
        
        Returns:
            List of days that work for both team and league
        """
        if not self.preferred_days:
            # If team has no preference, use league's days
            return self.league.get_all_scheduling_days()
        
        league_days = set(self.league.get_all_scheduling_days())
        if not league_days:
            # If league has no restrictions, use team's preferences
            return self.preferred_days.copy()
        
        team_days = set(self.preferred_days)
        compatible = team_days & league_days
        return list(compatible)
    
    def get_best_scheduling_days(self) -> List[str]:
        """
        Get the best days for scheduling this team's matches
        
        Returns priority order:
        1. Days that are both team preferred and league preferred
        2. Days that are team preferred and league backup
        3. Days that are league preferred (if team has no preference)
        4. Days that are league backup (if team has no preference)
        """
        if not self.preferred_days:
            # Team has no preference, use league priorities
            return self.league.preferred_days + self.league.backup_days
        
        league_preferred = set(self.league.preferred_days)
        league_backup = set(self.league.backup_days)
        team_preferred = set(self.preferred_days)
        
        # Priority 1: Team preferred AND league preferred
        best_days = list(team_preferred & league_preferred)
        
        # Priority 2: Team preferred AND league backup
        good_days = list(team_preferred & league_backup)
        
        return best_days + good_days
    
    def get_home_facility_display(self) -> str:
        """Get a display-friendly version of the home facility name"""
        return self.home_facility.name


    def matches_facility_name(self, facility_name: str, 
                            check_short_name: bool = True,
                            case_sensitive: bool = False) -> bool:
        """Check if this team's home facility matches a given facility name"""
        # Check against main name
        if not case_sensitive:
            name_match = self.home_facility.name.lower() == facility_name.lower()
        else:
            name_match = self.home_facility.name == facility_name
        
        if name_match:
            return True
        
        # Check against short name if enabled
        if check_short_name and self.home_facility.short_name:
            if not case_sensitive:
                return self.home_facility.short_name.lower() == facility_name.lower()
            else:
                return self.home_facility.short_name == facility_name
        
        return False



@dataclass
class Match:
    """Represents a tennis match (scheduled or unscheduled)"""
    id: int
    league_id: int
    home_team_id: int
    visitor_team_id: int
    facility_id: Optional[int] = None  # None for unscheduled matches
    date: Optional[str] = None  # YYYY-MM-DD format, None for unscheduled
    time: Optional[str] = None  # HH:MM format, None for unscheduled
    lines: List[Line] = field(default_factory=list)  # Individual line assignments
    
    def __post_init__(self):
        """Validate match data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.league_id, int) or self.league_id <= 0:
            raise ValueError(f"League ID must be a positive integer, got: {self.league_id}")
        
        if not isinstance(self.home_team_id, int) or self.home_team_id <= 0:
            raise ValueError(f"Home team ID must be a positive integer, got: {self.home_team_id}")
        
        if not isinstance(self.visitor_team_id, int) or self.visitor_team_id <= 0:
            raise ValueError(f"Visitor team ID must be a positive integer, got: {self.visitor_team_id}")
        
        if self.home_team_id == self.visitor_team_id:
            raise ValueError("Home team and visitor team cannot be the same")
        
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
        
        # Validate lines
        if not isinstance(self.lines, list):
            raise ValueError("Lines must be a list")
        
        for i, line in enumerate(self.lines):
            if not isinstance(line, Line):
                raise ValueError(f"All lines must be Line objects, line {i} is {type(line)}")
            if line.match_id != self.id:
                raise ValueError(f"Line {i} match_id ({line.match_id}) doesn't match this match ID ({self.id})")

    # ========== Match Class Getters ==========

    def get_id(self) -> int:
        """Get the match ID"""
        return self.id
    
    def get_league_id(self) -> int:
        """Get the league ID"""
        return self.league_id
    
    def get_home_team_id(self) -> int:
        """Get the home team ID"""
        return self.home_team_id
    
    def get_visitor_team_id(self) -> int:
        """Get the visitor team ID"""
        return self.visitor_team_id
    
    def get_facility_id(self) -> Optional[int]:
        """Get the facility ID (None if unscheduled)"""
        return self.facility_id
    
    def get_date(self) -> Optional[str]:
        """Get the match date in YYYY-MM-DD format (None if unscheduled)"""
        return self.date
    
    def get_time(self) -> Optional[str]:
        """Get the match time in HH:MM format (None if unscheduled)"""
        return self.time
    
    def get_lines(self) -> List[Line]:
        """Get the list of lines for this match"""
        return self.lines.copy()
    
    def get_lines_count(self) -> int:
        """Get the number of lines in this match"""
        return len(self.lines)
    
    def get_scheduled_lines_count(self) -> int:
        """Get the number of scheduled lines"""
        return len(self.get_scheduled_lines())
    
    def get_unscheduled_lines_count(self) -> int:
        """Get the number of unscheduled lines"""
        return len(self.get_unscheduled_lines())
    
    def get_date_time_str(self) -> Optional[str]:
        """Get combined date and time string (None if unscheduled)"""
        if self.date and self.time:
            return f"{self.date} {self.time}"
        return None
    
    def get_team_ids(self) -> Tuple[int, int]:
        """Get both team IDs as a tuple (home, visitor)"""
        return (self.home_team_id, self.visitor_team_id)
    
    def get_all_line_ids(self) -> List[int]:
        """Get list of all line IDs"""
        return [line.id for line in self.lines]
    
    def get_scheduled_line_ids(self) -> List[int]:
        """Get list of scheduled line IDs"""
        return [line.id for line in self.lines if line.is_scheduled()]
    
    def get_unscheduled_line_ids(self) -> List[int]:
        """Get list of unscheduled line IDs"""
        return [line.id for line in self.lines if line.is_unscheduled()]
    
    def get_lines_by_number(self) -> Dict[int, Line]:
        """Get lines organized by line number"""
        return {line.line_number: line for line in self.lines}
    
    def get_match_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of match information"""
        return {
            'id': self.id,
            'league_id': self.league_id,
            'home_team_id': self.home_team_id,
            'visitor_team_id': self.visitor_team_id,
            'facility_id': self.facility_id,
            'date': self.date,
            'time': self.time,
            'is_scheduled': self.is_scheduled(),
            'status': self.get_status(),
            'lines_count': len(self.lines),
            'scheduled_lines_count': self.get_scheduled_lines_count(),
            'unscheduled_lines_count': self.get_unscheduled_lines_count(),
            'line_scheduling_status': self.get_line_scheduling_status(),
            'missing_fields': self.get_missing_fields()
        }
    
    def get_earliest_line_time(self) -> Optional[str]:
        """Get the earliest scheduled line time"""
        scheduled_times = [line.time for line in self.lines if line.time]
        return min(scheduled_times) if scheduled_times else None
    
    def get_latest_line_time(self) -> Optional[str]:
        """Get the latest scheduled line time"""
        scheduled_times = [line.time for line in self.lines if line.time]
        return max(scheduled_times) if scheduled_times else None
    
    def get_unique_facilities_used(self) -> List[int]:
        """Get list of unique facility IDs used by lines"""
        facility_ids = [line.facility_id for line in self.lines if line.facility_id]
        return list(set(facility_ids))
    
    def get_unique_dates_used(self) -> List[str]:
        """Get list of unique dates used by lines"""
        dates = [line.date for line in self.lines if line.date]
        return list(set(dates))
    
    def get_unique_times_used(self) -> List[str]:
        """Get list of unique times used by lines"""
        times = [line.time for line in self.lines if line.time]
        return list(set(times))
    # ========== Basic Status Methods ==========
    
    def is_scheduled(self) -> bool:
        """Check if the match is scheduled (has date, time, and facility)"""
        return all([self.facility_id is not None, self.date is not None, self.time is not None])
    
    def is_unscheduled(self) -> bool:
        """Check if the match is unscheduled"""
        return not self.is_scheduled()
    
    def get_status(self) -> str:
        """Get the scheduling status of the match"""
        return "scheduled" if self.is_scheduled() else "unscheduled"
    
    def are_lines_scheduled(self) -> bool:
        """Check if all lines are scheduled"""
        return len(self.lines) > 0 and all(line.is_scheduled() for line in self.lines)
    
    def are_lines_unscheduled(self) -> bool:
        """Check if all lines are unscheduled"""
        return len(self.lines) == 0 or all(line.is_unscheduled() for line in self.lines)
    
    def get_line_scheduling_status(self) -> str:
        """Get the detailed scheduling status including line information"""
        if len(self.lines) == 0:
            return "no lines created"
        elif self.are_lines_scheduled():
            return "fully scheduled (all lines)"
        elif self.are_lines_unscheduled():
            return "unscheduled (no lines)"
        else:
            scheduled_count = sum(1 for line in self.lines if line.is_scheduled())
            return f"partially scheduled ({scheduled_count}/{len(self.lines)} lines)"
    
    # ========== Line Management Methods ==========
    
    def needs_lines_created(self) -> bool:
        """Check if this match needs lines to be created"""
        return len(self.lines) == 0
    
    def has_complete_lines(self, league: 'League') -> bool:
        """Check if match has the correct number of lines for the league"""
        return len(self.lines) == league.get_total_courts_needed()
    
    def create_lines(self, league: 'League') -> None:
        """
        Create unscheduled Line objects for this match based on league requirements
        
        Args:
            league: League object to get number of lines needed
        """
        # Clear existing lines
        self.lines.clear()
        
        # Create new lines
        num_lines = league.get_total_courts_needed()
        base_line_id = self._generate_line_id_base()
        
        for line_num in range(1, num_lines + 1):
            line_id = base_line_id + line_num
            line = Line(
                id=line_id,
                match_id=self.id,
                line_number=line_num,
                facility_id=None,
                date=None,
                time=None,
                court_number=None
            )
            self.lines.append(line)
    
    def _generate_line_id_base(self) -> int:
        """Generate base ID for lines (match_id * 100 to leave room for line numbers)"""
        return self.id * 100
    
    # ========== Scheduling Methods ==========
    
    def schedule_all_lines_same_time(self, facility_id: int, date: str, time: str) -> bool:
        """
        Schedule all lines at the same facility, date, and time
        
        Args:
            facility_id: Facility ID
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            
        Returns:
            True if all lines were scheduled successfully
        """
        if not self.lines:
            return False
        
        # Schedule all lines
        for line in self.lines:
            line.facility_id = facility_id
            line.date = date
            line.time = time
        
        # Also update match-level scheduling
        self.facility_id = facility_id
        self.date = date
        self.time = time
        
        return True
    
    def schedule_lines_split_times(self, scheduling_plan: List[Tuple[str, int, int]]) -> bool:
        """
        Schedule lines across different times (when league allows split lines)
        
        Args:
            scheduling_plan: List of (time, facility_id, num_lines_at_time) tuples
            
        Returns:
            True if all lines were scheduled successfully
        """
        if not self.lines:
            return False
        
        total_planned_lines = sum(num_lines for _, _, num_lines in scheduling_plan)
        if total_planned_lines != len(self.lines):
            raise ValueError(f"Scheduling plan covers {total_planned_lines} lines but match has {len(self.lines)} lines")
        
        # Assign lines to time slots
        line_index = 0
        facilities_used = set()
        dates_used = set()
        
        for time, facility_id, num_lines_at_time in scheduling_plan:
            for _ in range(num_lines_at_time):
                if line_index >= len(self.lines):
                    break
                
                line = self.lines[line_index]
                line.facility_id = facility_id
                line.date = self.date or date.today().strftime('%Y-%m-%d')  # Use match date or today
                line.time = time
                
                facilities_used.add(facility_id)
                dates_used.add(line.date)
                line_index += 1
        
        # Update match-level info with primary facility/date/time
        if scheduling_plan:
            primary_time, primary_facility, _ = scheduling_plan[0]
            self.facility_id = primary_facility
            self.date = list(dates_used)[0] if dates_used else None
            self.time = primary_time
        
        return line_index == len(self.lines)
    
    def unschedule_all_lines(self) -> None:
        """Unschedule all lines and the match"""
        for line in self.lines:
            line.facility_id = None
            line.date = None
            line.time = None
            line.court_number = None
        
        self.facility_id = None
        self.date = None
        self.time = None
    
    def schedule(self, facility_id: int, date: str, time: str) -> 'Match':
        """Return a new Match instance with scheduling information"""
        return Match(
            id=self.id,
            league_id=self.league_id,
            home_team_id=self.home_team_id,
            visitor_team_id=self.visitor_team_id,
            facility_id=facility_id,
            date=date,
            time=time,
            lines=self.lines.copy()  # Copy the lines
        )
    
    def unschedule(self) -> 'Match':
        """Return a new Match instance without scheduling information"""
        # Create unscheduled lines
        unscheduled_lines = [line.unschedule() for line in self.lines]
        
        return Match(
            id=self.id,
            league_id=self.league_id,
            home_team_id=self.home_team_id,
            visitor_team_id=self.visitor_team_id,
            facility_id=None,
            date=None,
            time=None,
            lines=unscheduled_lines
        )
    
    # ========== Analysis and Reporting Methods ==========
    
    def get_scheduled_lines(self) -> List[Line]:
        """Get all scheduled lines"""
        return [line for line in self.lines if line.is_scheduled()]
    
    def get_unscheduled_lines(self) -> List[Line]:
        """Get all unscheduled lines"""
        return [line for line in self.lines if line.is_unscheduled()]
    
    def get_lines_by_time(self) -> Dict[str, List[Line]]:
        """Group lines by their scheduled time"""
        lines_by_time = defaultdict(list)
        for line in self.lines:
            if line.time is not None:
                lines_by_time[line.time].append(line)
        return dict(lines_by_time)
    
    def get_lines_by_facility(self) -> Dict[int, List[Line]]:
        """Group lines by their scheduled facility"""
        lines_by_facility = defaultdict(list)
        for line in self.lines:
            if line.facility_id is not None:
                lines_by_facility[line.facility_id].append(line)
        return dict(lines_by_facility)
    
    def get_time_span(self) -> Optional[Tuple[str, str]]:
        """
        Get the time span of all scheduled lines
        
        Returns:
            Tuple of (earliest_time, latest_time) or None if no lines scheduled
        """
        scheduled_times = [line.time for line in self.lines if line.time is not None]
        if not scheduled_times:
            return None
        
        return (min(scheduled_times), max(scheduled_times))
    
    def get_missing_fields(self) -> List[str]:
        """
        Get a list of fields that are missing for this match to be fully scheduled
        
        Returns:
            List of missing field names (e.g., ['facility', 'date', 'time'])
        """
        missing = []
        
        if self.facility_id is None:
            missing.append('facility')
        
        if self.date is None:
            missing.append('date')
        
        if self.time is None:
            missing.append('time')
        
        return missing
    
    # ========== String Representation ==========
    
    def __str__(self) -> str:
        """String representation of the match"""
        status = self.get_line_scheduling_status()
        if self.is_scheduled():
            return f"Match {self.id}: Team {self.home_team_id} vs {self.visitor_team_id} - {self.date} {self.time} ({status})"
        else:
            return f"Match {self.id}: Team {self.home_team_id} vs {self.visitor_team_id} - Unscheduled ({status})"
    
    def __repr__(self) -> str:
        """Detailed representation of the match"""
        return (f"Match(id={self.id}, league_id={self.league_id}, "
                f"home_team_id={self.home_team_id}, visitor_team_id={self.visitor_team_id}, "
                f"facility_id={self.facility_id}, date='{self.date}', time='{self.time}', "
                f"lines={len(self.lines)})")