from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Any, Optional
from datetime import date as date_type, datetime, timedelta
from datetime import date
import itertools
import re
from collections import defaultdict
import logging 
from usta_match import Match
from usta_team import Team
from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS


logger = logging.getLogger(__name__)

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
    
    def __post_init__(self) -> None:
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
    
    def __post_init__(self) -> None:
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
    
    def get_available_times(self, min_courts: int) -> List[str]:
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
    date: Optional[date] = None  # Date object, None for unscheduled
    time: Optional[str] = None  # HH:MM format, None for unscheduled
    court_number: Optional[int] = None  # Specific court number if facility tracks them
    
    def __post_init__(self) -> None:
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
            if not isinstance(self.date, date):
                raise ValueError("Date must be a date object or None")
        
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
    
    def get_date(self) -> Optional[date_type]:
        """Get the scheduled date (None if unscheduled)"""
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
    
    def schedule(self, facility_id: int, match_date: date_type, time: str, court_number: Optional[int] = None) -> 'Line':
        """Return a new Line instance with scheduling information"""
        return Line(
            id=self.id,
            match_id=self.match_id,
            line_number=self.line_number,
            facility_id=facility_id,
            date=match_date,
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
    """Represents a tennis facility with its schedule constraints. """
    id: int
    name: str
    short_name: Optional[str] = None  # Short name for display (e.g., "VR", "TCA")
    location: Optional[str] = None
    schedule: WeeklySchedule = field(default_factory=WeeklySchedule)
    unavailable_dates: List[date] = field(default_factory=list)  # List of date objects
    total_courts: int = 0  # Total number of courts at the facility
    
    def __eq__(self, other: Any) -> bool:
        """Check equality based on ID and name"""
        if not isinstance(other, Facility):
            return False
        return self.id == other.id and self.name == other.name
    
    def __hash__(self) -> int:
        """Hash based on ID and name for use in sets/dictionaries"""
        return hash((self.id, self.name))
    
    def __str__(self) -> str:
        """String representation of the facility"""
        return f"Facility(id={self.id}, name='{self.name}', short_name='{self.short_name}', location='{self.location}', total_courts={self.total_courts})"
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging"""
        return (f"Facility(id={self.id}, name='{self.name}', short_name='{self.short_name}', "
                f"location='{self.location}', total_courts={self.total_courts}, "
                f"unavailable_dates={self.unavailable_dates}, schedule={self.schedule})")

    def __post_init__(self) -> None:
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
        for date_obj in self.unavailable_dates:
            if not isinstance(date_obj, date):
                raise ValueError(f"All unavailable dates must be date objects, got: {type(date_obj)}")

        if self.total_courts == 0:
            # make total_courts the maximum of the schedule's available courts for a single time slot
            # This assumes that the schedule has been properly initialized with DaySchedule objects
            max_courts = 0
            for day_schedule in self.schedule.get_all_days().values():
                for time_slot in day_schedule.get_start_times():
                    if time_slot.available_courts > max_courts:
                        max_courts = time_slot.available_courts

            self.total_courts = max_courts


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
    
    def get_unavailable_dates(self) -> List[date]:
        """Get list of unavailable dates"""
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
                    return str(combo)
        
        # Strategy 4: Truncate first word if single word or nothing else works
        if len(meaningful_words) >= 1:
            first_word = meaningful_words[0].upper()
            if len(first_word) <= max_length:
                return str(first_word)
            else:
                return str(first_word[:max_length])
        
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
    
    def add_unavailable_date(self, date_obj: date) -> None:
        """Add a date to the unavailable dates list"""
        if not isinstance(date_obj, date):
            raise ValueError("Date must be a date object")
        
        if date_obj not in self.unavailable_dates:
            self.unavailable_dates.append(date_obj)
    
    def remove_unavailable_date(self, date_obj: date) -> None:
        """Remove a date from the unavailable dates list"""
        if date_obj in self.unavailable_dates:
            self.unavailable_dates.remove(date_obj)
    
    def is_available_on_date(self, date_obj: date) -> bool:
        """Check if the facility is available on a specific date"""
        return date_obj not in self.unavailable_dates
    
    def get_available_courts_on_day_time(self, day: str, time: str) -> Optional[int]:
        """Get the number of available courts for a specific day and time"""
        try:
            day_schedule = self.schedule.get_day_schedule(day)
            return day_schedule.get_available_courts_at_time(time)
        except ValueError:
            return None
        
    def get_available_courts_on_date_time(self, date_obj: date, time: str) -> Optional[int]:
        """Get the number of available courts for a specific date and time"""
        # Convert date to day of week
        try:
            day_of_week = date_obj.strftime('%A')  # Get full weekday name
            return self.get_available_courts_on_day_time(day_of_week, time)
        except ValueError:
            return None
    
    def has_availability_on_day(self, day: str) -> bool:
        """Check if the facility has any availability on a specific day of the week"""
        try:
            day_schedule = self.schedule.get_day_schedule(day)
            return day_schedule.has_availability()
        except ValueError:
            return False
    

    
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
        if facility_id is None:
            raise ValueError("Facility ID is required")
        if name is None:
            raise ValueError("Facility name is required")
        
        facility = cls(
            id=int(facility_id), 
            name=str(name), 
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


"""
Facility Availability Classes

These classes provide structured return types for facility availability queries,
replacing dictionary returns with type-safe, documented objects.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime



@dataclass
class TimeSlotAvailability:
    """
    Represents availability information for a specific time slot at a facility
    """
    time: str  # Time in HH:MM format
    total_courts: int  # Total courts available at this time slot
    used_courts: int  # Courts currently scheduled/booked
    available_courts: int  # Courts still available for booking
    utilization_percentage: float  # Percentage of courts being used (0-100)
    
    def __post_init__(self) -> None:
        """Validate time slot availability data"""
        # Validate time format
        if not isinstance(self.time, str):
            raise ValueError("Time must be a string")
        
        try:
            parts = self.time.split(':')
            if len(parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: '{self.time}'. Expected HH:MM format")
        
        # Validate court counts
        if not isinstance(self.total_courts, int) or self.total_courts < 0:
            raise ValueError(f"Total courts must be a non-negative integer, got: {self.total_courts}")
        
        if not isinstance(self.used_courts, int) or self.used_courts < 0:
            raise ValueError(f"Used courts must be a non-negative integer, got: {self.used_courts}")
        
        if not isinstance(self.available_courts, int) or self.available_courts < 0:
            raise ValueError(f"Available courts must be a non-negative integer, got: {self.available_courts}")
        
        # Validate logical consistency
        if self.used_courts > self.total_courts:
            raise ValueError(f"Used courts ({self.used_courts}) cannot exceed total courts ({self.total_courts})")
        
        if self.available_courts != (self.total_courts - self.used_courts):
            raise ValueError(f"Available courts ({self.available_courts}) must equal total ({self.total_courts}) minus used ({self.used_courts})")
        
        # Validate utilization percentage
        if not isinstance(self.utilization_percentage, (int, float)) or not (0 <= self.utilization_percentage <= 100):
            raise ValueError(f"Utilization percentage must be between 0 and 100, got: {self.utilization_percentage}")
    
    def is_fully_booked(self) -> bool:
        """Check if this time slot is fully booked"""
        return self.available_courts == 0
    
    def has_availability(self) -> bool:
        """Check if this time slot has any available courts"""
        return self.available_courts > 0
    
    def can_accommodate(self, courts_needed: int) -> bool:
        """Check if this time slot can accommodate the requested number of courts"""
        return self.available_courts >= courts_needed
    
    def get_utilization_level(self) -> str:
        """Get a descriptive utilization level"""
        if self.utilization_percentage == 0:
            return "Empty"
        elif self.utilization_percentage < 25:
            return "Light"
        elif self.utilization_percentage < 50:
            return "Moderate"
        elif self.utilization_percentage < 75:
            return "Heavy"
        elif self.utilization_percentage < 100:
            return "Nearly Full"
        else:
            return "Full"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'time': self.time,
            'total_courts': self.total_courts,
            'used_courts': self.used_courts,
            'available_courts': self.available_courts,
            'utilization_percentage': self.utilization_percentage,
            'utilization_level': self.get_utilization_level(),
            'fully_booked': self.is_fully_booked(),
            'has_availability': self.has_availability()
        }





@dataclass
class FacilityAvailabilityInfo:
    """
    Comprehensive availability information for a facility on a specific date
    """
    facility_id: int
    facility_name: str
    date: date  # Date object
    day_of_week: str  # Full day name (Monday, Tuesday, etc.)
    available: bool  # Whether facility is available on this date
    time_slots: List[TimeSlotAvailability] = field(default_factory=list)
    total_court_slots: int = 0  # Total court-time slots across all times
    used_court_slots: int = 0  # Used court-time slots across all times
    available_court_slots: int = 0  # Available court-time slots across all times
    overall_utilization_percentage: float = 0.0  # Overall utilization across all time slots
    reason: Optional[str] = None  # Reason if facility is not available
    
    def __post_init__(self) -> None:
        """Validate facility availability info"""
        if not isinstance(self.facility_id, int) or self.facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {self.facility_id}")
        
        if not isinstance(self.facility_name, str) or not self.facility_name.strip():
            raise ValueError("Facility name must be a non-empty string")
        
        # Validate date format
        if not isinstance(self.date, date):
            raise ValueError("Date must be a date object")
        
        # Validate day of week
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if self.day_of_week not in valid_days:
            raise ValueError(f"Invalid day of week: {self.day_of_week}. Must be one of: {valid_days}")
        
        # Validate time slots
        if not isinstance(self.time_slots, list):
            raise ValueError("Time slots must be a list")
        
        for i, slot in enumerate(self.time_slots):
            if not isinstance(slot, TimeSlotAvailability):
                raise ValueError(f"All time slots must be TimeSlotAvailability objects, item {i} is {type(slot)}")
        
        # Validate court slot counts
        if not isinstance(self.total_court_slots, int) or self.total_court_slots < 0:
            raise ValueError(f"Total court slots must be a non-negative integer, got: {self.total_court_slots}")
        
        if not isinstance(self.used_court_slots, int) or self.used_court_slots < 0:
            raise ValueError(f"Used court slots must be a non-negative integer, got: {self.used_court_slots}")
        
        if not isinstance(self.available_court_slots, int) or self.available_court_slots < 0:
            raise ValueError(f"Available court slots must be a non-negative integer, got: {self.available_court_slots}")
        
        # Validate utilization percentage
        if not isinstance(self.overall_utilization_percentage, (int, float)) or not (0 <= self.overall_utilization_percentage <= 100):
            raise ValueError(f"Overall utilization percentage must be between 0 and 100, got: {self.overall_utilization_percentage}")
    
    def is_fully_booked(self) -> bool:
        """Check if facility is fully booked for the entire day"""
        return self.available and self.available_court_slots == 0
    
    def has_any_availability(self) -> bool:
        """Check if facility has any availability during the day"""
        return self.available and self.available_court_slots > 0
    
    
    def get_peak_utilization_time(self) -> Optional[TimeSlotAvailability]:
        """Get the time slot with highest utilization"""
        if not self.time_slots:
            return None
        return max(self.time_slots, key=lambda slot: slot.utilization_percentage)
    
    def get_lowest_utilization_time(self) -> Optional[TimeSlotAvailability]:
        """Get the time slot with lowest utilization"""
        if not self.time_slots:
            return None
        return min(self.time_slots, key=lambda slot: slot.utilization_percentage)
    
    def get_utilization_summary(self) -> Dict[str, int]:
        """Get summary of utilization levels across time slots"""
        summary = {"Empty": 0, "Light": 0, "Moderate": 0, "Heavy": 0, "Nearly Full": 0, "Full": 0}
        for slot in self.time_slots:
            level = slot.get_utilization_level()
            summary[level] += 1
        return summary
    
    def find_consecutive_available_slots(self, courts_needed: int, slots_needed: int) -> List[List[str]]:
        """
        Find consecutive time slots that can accommodate the required courts
        
        Args:
            courts_needed: Number of courts needed per time slot
            slots_needed: Number of consecutive time slots needed
            
        Returns:
            List of consecutive time slot sequences that meet the requirements
        """
        if slots_needed <= 0 or courts_needed <= 0:
            return []
        
        suitable_times = [slot.time for slot in self.time_slots if slot.can_accommodate(courts_needed)]
        
        if len(suitable_times) < slots_needed:
            return []
        
        consecutive_sequences = []
        
        # Find consecutive sequences of the required length
        for i in range(len(suitable_times) - slots_needed + 1):
            sequence = suitable_times[i:i + slots_needed]
            
            # Check if times are actually consecutive (this is a simplified check)
            # In a real implementation, you'd want to check actual time intervals
            consecutive_sequences.append(sequence)
        
        return consecutive_sequences
    
    def check_time_availability(self, time: str, courts_needed: int = 1) -> bool:
        """
        Check if a specific time slot has availability for the required number of courts
        
        Args:
            time: Time in HH:MM format
            courts_needed: Number of courts needed
            
        Returns:
            True if the time slot can accommodate the request, False otherwise
        """
        if not self.available:
            return False
            
        for time_slot in self.time_slots:
            if time_slot.time == time:
                return time_slot.can_accommodate(courts_needed)
        
        return False

    def get_available_times(self, courts_needed: int = 1) -> List[str]:
        """
        Get all available times that can accommodate the required number of courts
        
        Args:
            courts_needed: Number of courts needed
            
        Returns:
            List of available time strings in HH:MM format
        """
        if not self.available:
            return []
            
        return [slot.time for slot in self.time_slots if slot.can_accommodate(courts_needed)]

    


    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'facility_id': self.facility_id,
            'facility_name': self.facility_name,
            'date': self.date,
            'day_of_week': self.day_of_week,
            'available': self.available,
            'reason': self.reason,
            'total_court_slots': self.total_court_slots,
            'used_court_slots': self.used_court_slots,
            'available_court_slots': self.available_court_slots,
            'overall_utilization_percentage': self.overall_utilization_percentage,
            'time_slots': [slot.to_dict() for slot in self.time_slots],
            'summary': {
                'fully_booked': self.is_fully_booked(),
                'has_availability': self.has_any_availability(),
                'available_times_count': len(self.get_available_times()),
                'peak_utilization': (lambda x: x.utilization_percentage if x else 0)(self.get_peak_utilization_time()),
                'lowest_utilization': (lambda x: x.utilization_percentage if x else 0)(self.get_lowest_utilization_time()),
                'utilization_distribution': self.get_utilization_summary()
            }
        }
    
    @classmethod
    def create_unavailable(cls, facility_id: int, facility_name: str, match_date: date_type, 
                          day_of_week: str, reason: str) -> 'FacilityAvailabilityInfo':
        """
        Create a FacilityAvailabilityInfo for an unavailable facility
        
        Args:
            facility_id: ID of the facility
            facility_name: Name of the facility
            match_date: Date object
            day_of_week: Day of the week
            reason: Reason why facility is unavailable
            
        Returns:
            FacilityAvailabilityInfo instance marked as unavailable
        """
        return cls(
            facility_id=facility_id,
            facility_name=facility_name,
            date=match_date,
            day_of_week=day_of_week,
            available=False,
            time_slots=[],
            total_court_slots=0,
            used_court_slots=0,
            available_court_slots=0,
            overall_utilization_percentage=0.0,
            reason=reason
        )
    
    @classmethod
    def from_time_slots(cls, facility_id: int, facility_name: str, match_date: date_type, 
                       day_of_week: str, time_slots: List[TimeSlotAvailability]) -> 'FacilityAvailabilityInfo':
        """
        Create a FacilityAvailabilityInfo from a list of time slots
        
        Args:
            facility_id: ID of the facility
            facility_name: Name of the facility
            match_date: Date object
            day_of_week: Day of the week
            time_slots: List of TimeSlotAvailability objects
            
        Returns:
            FacilityAvailabilityInfo instance with calculated totals
        """
        total_court_slots = sum(slot.total_courts for slot in time_slots)
        used_court_slots = sum(slot.used_courts for slot in time_slots)
        available_court_slots = total_court_slots - used_court_slots
        
        overall_utilization = (used_court_slots / total_court_slots * 100) if total_court_slots > 0 else 0.0
        
        return cls(
            facility_id=facility_id,
            facility_name=facility_name,
            date=match_date,
            day_of_week=day_of_week,
            available=True,
            time_slots=time_slots,
            total_court_slots=total_court_slots,
            used_court_slots=used_court_slots,
            available_court_slots=available_court_slots,
            overall_utilization_percentage=round(overall_utilization, 1)
        )

    def validate_scheduling_request(self, times: List[str], scheduling_mode: str, lines_needed: int) -> Tuple[bool, Optional[str]]:
        """
        Validate a scheduling request against this facility's availability
        
        Args:
            times: List of requested time strings
            scheduling_mode: Mode ('same_time', 'split_times', 'custom')
            lines_needed: Number of lines/courts needed
            
        Returns:
            (is_valid, error_message)
        """
        if not self.available:
            return False, f"Facility not available on {self.date}: {self.reason}"
        
        if scheduling_mode == 'same_time':
            return self._validate_same_time(times, lines_needed)
        elif scheduling_mode == 'split_times':
            return self._validate_split_times(times, lines_needed)
        elif scheduling_mode == 'custom':
            return self._validate_custom(times, lines_needed)
        else:
            return False, f"Unknown scheduling mode: {scheduling_mode}"

    def _validate_same_time(self, times: List[str], lines_needed: int) -> Tuple[bool, Optional[str]]:
        """Validate same time scheduling"""
        if len(times) != 1:
            return False, "Same time mode requires exactly one time slot"
        
        time = times[0]
        if not self.check_time_availability(time, lines_needed):
            available_alternatives = self.get_available_times(lines_needed)
            if available_alternatives:
                return False, f"Time {time} cannot accommodate {lines_needed} courts. Available: {', '.join(available_alternatives)}"
            else:
                return False, f"No time slots can accommodate {lines_needed} courts on {self.date}"
        
        return True, None


    def _validate_split_times(self, times: List[str], lines_needed: int) -> Tuple[bool, Optional[str]]:
        """Validate split times scheduling"""
        if len(times) != 2:
            return False, "Split times mode requires exactly two time slots"
        
        import math
        from datetime import datetime, timedelta
        
        time1, time2 = sorted(times)
        courts_per_slot = math.ceil(lines_needed / 2)
        
        # Check time gap
        try:
            dt1 = datetime.strptime(time1, '%H:%M')
            dt2 = datetime.strptime(time2, '%H:%M')
            if dt2 < dt1:
                dt2 += timedelta(days=1)
            if dt2 - dt1 < timedelta(hours=1):
                return False, "Split time slots must be at least 1 hour apart"
        except ValueError:
            return False, "Invalid time format"
        
        # Check availability for both slots
        if not self.check_time_availability(time1, courts_per_slot):
            return False, f"Time {time1} cannot accommodate {courts_per_slot} courts"
        
        if not self.check_time_availability(time2, courts_per_slot):
            return False, f"Time {time2} cannot accommodate {courts_per_slot} courts"
        
        return True, None

    def _validate_custom(self, times: List[str], lines_needed: int) -> Tuple[bool, Optional[str]]:
        """Validate custom scheduling"""
        if len(times) != lines_needed:
            return False, f"Custom mode requires exactly {lines_needed} time slots"
        
        # Check each time individually
        for i, time in enumerate(times):
            if not self.check_time_availability(time, 1):
                return False, f"Time {time} (line {i+1}) is not available"
        
        # Check for duplicate times that exceed capacity
        from collections import Counter
        time_counts = Counter(times)
        for time, count in time_counts.items():
            if not self.check_time_availability(time, count):
                return False, f"Time {time} cannot accommodate {count} courts"
        
        return True, None

    def get_scheduling_suggestions(self, lines_needed: int) -> Dict[str, Any]:
        """
        Get scheduling suggestions for this facility/date
        
        Returns:
            Dictionary with suggestions for different scheduling modes
        """
        suggestions = {
            'date': self.date,
            'facility_name': self.facility_name,
            'available': self.available
        }
        
        if not self.available:
            suggestions['reason'] = self.reason
            return suggestions
        
        # Same time suggestions
        same_time_options = self.get_available_times(lines_needed)
        suggestions['same_time'] = {
            'possible': len(same_time_options) > 0,
            'options': same_time_options[:5]  # Limit to first 5
        }
        
        # Split times suggestions
        import math
        courts_per_slot = math.ceil(lines_needed / 2)
        split_time_options = self.get_available_times(courts_per_slot)
        
        if len(split_time_options) >= 2:
            suggestions['split_times'] = {
                'possible': True,
                'options': [
                    {'time1': split_time_options[i], 'time2': split_time_options[j]}
                    for i in range(len(split_time_options))
                    for j in range(i+1, min(i+4, len(split_time_options)))  # Limit combinations
                ][:5],
                'courts_per_slot': courts_per_slot
            }
        else:
            suggestions['split_times'] = {'possible': False}
        
        
        return suggestions
    

    def can_accommodate_match(self, match: 'Match') -> Tuple[bool, Optional[str]]:
        """
        Check if this facility can accommodate this match. This method should be 
        able to handle scheduling modes like 'same_time', 'split_times', and 'custom'.
        
        Args:
            match: Unscheduled Match object 
            
        Returns:
            (can_accommodate, reason)
        """
        if not self.available:
            return False, f"Facility not available on {self.date}: {self.reason}"

        lines_needed = match.league.num_lines_per_match

        # first check to see if we can accommodate all lines at the same time
        if lines_needed and len(self.get_available_times(lines_needed)) > 0:
            return True, None
        
        # if split times are allowed, check if we can accommodate in two time slots
        if match.league.allow_split_lines:
            import math
            courts_per_slot = math.ceil(lines_needed / 2)
            available_times = self.get_available_times(courts_per_slot)
            if len(available_times) >= 2:
                return True, None

        
        # if we reach here, we cannot accommodate the match
        return False, f"Facility cannot accommodate {lines_needed} lines on {self.date}"