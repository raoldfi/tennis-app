from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date
import itertools
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
class Facility:
    """Represents a tennis facility with scheduling capabilities"""
    id: int
    name: str
    location: Optional[str] = None
    schedule: WeeklySchedule = field(default_factory=WeeklySchedule)
    unavailable_dates: List[str] = field(default_factory=list)  # List of dates in "YYYY-MM-DD" format
    
    def __post_init__(self):
        """Validate facility data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Facility name must be a non-empty string")
        
        if self.location is not None and not isinstance(self.location, str):
            raise ValueError("Location must be a string or None")
        
        if not isinstance(self.schedule, WeeklySchedule):
            raise ValueError("Schedule must be a WeeklySchedule object")
        
        if not isinstance(self.unavailable_dates, list):
            raise ValueError("Unavailable dates must be a list")
        
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
    
    @classmethod
    def from_yaml_dict(cls, data: Dict[str, Any]) -> 'Facility':
        """Create a Facility from a YAML dictionary structure"""
        # Extract basic facility info
        facility_id = data.get('id')
        name = data.get('name')
        location = data.get('location')
        
        # Require schedule to be present
        if 'schedule' not in data:
            raise ValueError(f"Facility '{name}' (ID: {facility_id}) is missing required 'schedule' field")
        
        # Require unavailable_dates to be present (can be empty list)
        if 'unavailable_dates' not in data:
            raise ValueError(f"Facility '{name}' (ID: {facility_id}) is missing required 'unavailable_dates' field")
        
        # Create the facility with basic info first
        facility = cls(id=facility_id, name=name, location=location)
        
        # Process schedule - now required
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
        
        if self.location:
            result['location'] = self.location
        
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
    
    def calculate_pairings(self, teams: List['Team']) -> List[tuple]:
        """
        Calculate all permutations of pairings from the list of teams.
        
        This algorithm ensures:
        - Fair distribution of matches for each team
        - Balanced home/away games
        - Optimal pairing distribution
        - Handles odd numbers of teams by adjusting match count
        
        Args:
            teams: List of Team objects in this league
            
        Returns:
            List of tuples (home_team, visitor_team) representing all matches
            
        Raises:
            ValueError: If teams list is invalid
        """
        # Import itertools if not already available
        import itertools
        from collections import defaultdict
        
        if len(teams) < 2:
            raise ValueError("Need at least 2 teams to generate pairings")
        
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
        
        return selected_pairs


@dataclass
class Team:
    """Represents a tennis team"""
    id: int
    name: str
    league: League
    home_facility_id: int
    captain: Optional[str] = None
    preferred_days: List[str] = field(default_factory=list)  # Preferred days for scheduling
    
    def __post_init__(self):
        """Validate team data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {self.id}")
        
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Team name must be a non-empty string")
        
        if not isinstance(self.league, League):
            raise ValueError("League must be a League object")
        
        if not isinstance(self.home_facility_id, int) or self.home_facility_id <= 0:
            raise ValueError(f"Home facility ID must be a positive integer, got: {self.home_facility_id}")
        
        if self.captain is not None and (not isinstance(self.captain, str) or not self.captain.strip()):
            raise ValueError("Captain must be a non-empty string or None")
        
        # Validate preferred_days
        if not isinstance(self.preferred_days, list):
            raise ValueError("preferred_days must be a list")
        
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day in self.preferred_days:
            if not isinstance(day, str) or day not in valid_days:
                raise ValueError(f"Invalid preferred day: {day}. Must be one of: {valid_days}")
    
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
    
    def is_scheduled(self) -> bool:
        """Check if the match is scheduled (has date, time, and facility)"""
        return all([self.facility_id is not None, self.date is not None, self.time is not None])
    
    def is_unscheduled(self) -> bool:
        """Check if the match is unscheduled"""
        return not self.is_scheduled()
    
    def get_status(self) -> str:
        """Get the scheduling status of the match"""
        return "scheduled" if self.is_scheduled() else "unscheduled"
    
    def schedule(self, facility_id: int, date: str, time: str) -> 'Match':
        """Return a new Match instance with scheduling information"""
        return Match(
            id=self.id,
            league_id=self.league_id,
            home_team_id=self.home_team_id,
            visitor_team_id=self.visitor_team_id,
            facility_id=facility_id,
            date=date,
            time=time
        )
    
    def unschedule(self) -> 'Match':
        """Return a new Match instance without scheduling information"""
        return Match(
            id=self.id,
            league_id=self.league_id,
            home_team_id=self.home_team_id,
            visitor_team_id=self.visitor_team_id,
            facility_id=None,
            date=None,
            time=None
        )

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