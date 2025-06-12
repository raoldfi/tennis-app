"""
Updated Match Class - No Line Class

The Match class now contains an array of scheduled times instead of Line objects.
All lines for a match are scheduled on the same day at the same facility, but can
have different start times representing different time slots.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from datetime import date, datetime, timedelta
import itertools
import re
from collections import defaultdict

# Use TYPE_CHECKING for all USTA classes to avoid circular imports
if TYPE_CHECKING:
    from usta_league import League
    from usta_team import Team
    from usta_facility import Facility

@dataclass
class Match:
    """
    Represents a tennis match with direct object references
    
    The match contains an array of scheduled times instead of Line objects.
    All lines are assumed to be at the same facility and date, but can have different start times.
    """
    id: int
    league: 'League'  # Direct League object reference
    home_team: 'Team'  # Direct Team object reference  
    visitor_team: 'Team'  # Direct Team object reference
    facility: Optional['Facility'] = None  # Direct Facility object reference (None if unscheduled)
    date: Optional[str] = None  # YYYY-MM-DD format (None if unscheduled)
    scheduled_times: List[str] = field(default_factory=list)  # Array of HH:MM times for each line
    
    def __post_init__(self):
        """Validate match data"""
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {self.id}")
        
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
        
        # Validate scheduled_times
        if not isinstance(self.scheduled_times, list):
            raise ValueError("scheduled_times must be a list")
        
        for i, time_str in enumerate(self.scheduled_times):
            if not isinstance(time_str, str):
                raise ValueError(f"All scheduled times must be strings, item {i} is {type(time_str)}")
            try:
                parts = time_str.split(':')
                if len(parts) != 2:
                    raise ValueError("Invalid time format")
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time values")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid time format: '{time_str}'. Expected HH:MM format")

    # ========== Match Scheduling Status ==========
    
    def is_scheduled(self) -> bool:
        """Check if the match is scheduled (has facility, date, and at least one time)"""
        return all([
            self.facility is not None,
            self.date is not None,
            len(self.scheduled_times) > 0
        ])
    
    def is_unscheduled(self) -> bool:
        """Check if the match is unscheduled"""
        return not self.is_scheduled()
    
    def is_partially_scheduled(self) -> bool:
        """Check if the match is partially scheduled (has some but not all required lines)"""
        if self.is_unscheduled():
            return False
        expected_lines = self.league.num_lines_per_match
        return 0 < len(self.scheduled_times) < expected_lines
    
    def is_fully_scheduled(self) -> bool:
        """Check if the match is fully scheduled (has all required lines)"""
        if self.is_unscheduled():
            return False
        expected_lines = self.league.num_lines_per_match
        return len(self.scheduled_times) == expected_lines
    
    def get_status(self) -> str:
        """Get the scheduling status of the match"""
        if self.is_unscheduled():
            return "unscheduled"
        elif self.is_partially_scheduled():
            return "partially_scheduled"
        elif self.is_fully_scheduled():
            return "fully_scheduled"
        else:
            return "over_scheduled"  # More lines than expected

    # ========== Match Line Management ==========
    
    def get_num_scheduled_lines(self) -> int:
        """Get the number of scheduled lines (times)"""
        return len(self.scheduled_times)
    
    def get_expected_lines(self) -> int:
        """Get the expected number of lines from the league configuration"""
        return self.league.num_lines_per_match
    
    def get_missing_lines_count(self) -> int:
        """Get the number of lines still needed to be scheduled"""
        return max(0, self.get_expected_lines() - self.get_num_scheduled_lines())
    
    def add_scheduled_time(self, time: str) -> None:
        """Add a scheduled time for a new line"""
        # Validate time format
        try:
            parts = time.split(':')
            if len(parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: '{time}'. Expected HH:MM format")
        
        if time not in self.scheduled_times:
            self.scheduled_times.append(time)
            self.scheduled_times.sort()  # Keep times sorted
    
    def remove_scheduled_time(self, time: str) -> bool:
        """Remove a scheduled time. Returns True if time was found and removed."""
        if time in self.scheduled_times:
            self.scheduled_times.remove(time)
            return True
        return False
    
    def clear_scheduled_times(self) -> None:
        """Clear all scheduled times (unschedule all lines)"""
        self.scheduled_times.clear()

    # ========== Match Information ==========
    
    def get_date_time_strings(self) -> List[str]:
        """Get combined date and time strings for all scheduled lines"""
        if not self.date:
            return []
        return [f"{self.date} {time}" for time in self.scheduled_times]
    
    def get_earliest_time(self) -> Optional[str]:
        """Get the earliest scheduled time, or None if no times scheduled"""
        return min(self.scheduled_times) if self.scheduled_times else None
    
    def get_latest_time(self) -> Optional[str]:
        """Get the latest scheduled time, or None if no times scheduled"""
        return max(self.scheduled_times) if self.scheduled_times else None
    
    def get_match_duration_hours(self) -> float:
        """Estimate match duration in hours based on earliest and latest times"""
        if len(self.scheduled_times) < 2:
            return 3.0  # Default 3 hours for single time or no times
        
        earliest = self.get_earliest_time()
        latest = self.get_latest_time()
        
        if not earliest or not latest:
            return 3.0
        
        # Parse times and calculate difference
        earliest_parts = earliest.split(':')
        latest_parts = latest.split(':')
        
        earliest_minutes = int(earliest_parts[0]) * 60 + int(earliest_parts[1])
        latest_minutes = int(latest_parts[0]) * 60 + int(latest_parts[1])
        
        duration_minutes = latest_minutes - earliest_minutes + 180  # Add 3 hours for last match
        return duration_minutes / 60.0

    # ========== Match Scheduling Operations ==========
    
    def schedule_all_lines_same_time(self, facility: 'Facility', date: str, time: str) -> None:
        """Schedule all lines at the same time slot"""
        self.facility = facility
        self.date = date
        self.scheduled_times = [time] * self.league.num_lines_per_match
    
    def schedule_lines_sequential(self, facility: 'Facility', date: str, start_time: str, interval_minutes: int = 180) -> None:
        """Schedule lines sequentially with specified interval between start times"""
        self.facility = facility
        self.date = date
        self.scheduled_times = []
        
        # Parse start time
        start_parts = start_time.split(':')
        start_hour = int(start_parts[0])
        start_minute = int(start_parts[1])
        
        # Generate sequential times
        for i in range(self.league.num_lines_per_match):
            total_minutes = start_hour * 60 + start_minute + (i * interval_minutes)
            hour = (total_minutes // 60) % 24
            minute = total_minutes % 60
            time_str = f"{hour:02d}:{minute:02d}"
            self.scheduled_times.append(time_str)
    
    def schedule_lines_custom_times(self, facility: 'Facility', date: str, times: List[str]) -> None:
        """Schedule lines at custom specified times"""
        if len(times) != self.league.num_lines_per_match:
            raise ValueError(f"Must provide exactly {self.league.num_lines_per_match} times, got {len(times)}")
        
        self.facility = facility
        self.date = date
        self.scheduled_times = sorted(times.copy())
    
    def unschedule(self) -> None:
        """Unschedule the match (remove facility, date, and all times)"""
        self.facility = None
        self.date = None
        self.scheduled_times.clear()


    def get_optimal_scheduling_dates(self, start_date: Optional[str] = None,
                                   end_date: Optional[str] = None,
                                   num_dates: int = 20) -> List[str]:
        """
        Find optimal dates for scheduling a specific match, prioritizing team preferences
        Updated to work with Match objects directly.
        
        Args:
            match: Match object to find dates for
            start_date: Start date for search (defaults to league start_date)
            end_date: End date for search (defaults to league end_date)  
            num_dates: Number of dates to return
            
        Returns:
            List of date strings in YYYY-MM-DD format, ordered by preference
            (team preferred days first, then league preferred days, then backup days)
        """
        print(f"DEBUG: Getting optimal dates for match {self.id}")
        print(f"DEBUG: League start_date: {self.league.start_date}")
        print(f"DEBUG: League end_date: {self.league.end_date}")
        print(f"DEBUG: League preferred_days: {self.league.preferred_days}")
        print(f"DEBUG: League backup_days: {self.league.backup_days}")
        print(f"DEBUG: Home team preferred_days: {getattr(self.home_team, 'preferred_days', 'NOT_SET')}")
        print(f"DEBUG: Visitor team preferred_days: {getattr(self.visitor_team, 'preferred_days', 'NOT_SET')}")


        try:

            
            # Use league dates or reasonable defaults
            search_start = start_date or self.league.start_date or datetime.now().strftime('%Y-%m-%d')
            search_end = end_date or self.league.end_date
            
            if not search_end:
                # Default to 16 weeks from start
                start_dt = datetime.strptime(search_start, '%Y-%m-%d')
                end_dt = start_dt + timedelta(weeks=16)
                search_end = end_dt.strftime('%Y-%m-%d')
            
            # Generate candidate dates with priority system
            start_dt = datetime.strptime(search_start, '%Y-%m-%d')
            end_dt = datetime.strptime(search_end, '%Y-%m-%d')
            
            candidate_dates = []
            current = start_dt
            
            # Create combined team preferred days (intersection is highest priority)
            home_preferred = set(self.home_team.preferred_days)
            visitor_preferred = set(self.visitor_team.preferred_days)
            
            # Priority levels:
            # 1 = Both teams prefer this day
            # 2 = One team prefers this day
            # 3 = League prefers this day (but no team preference)
            # 4 = League backup day (but no team preference)
            # 5 = Day is allowed but not preferred by anyone
            
            while current <= end_dt:
                day_name = current.strftime('%A')
                date_str = current.strftime('%Y-%m-%d')
                
                # Skip days that the league doesn't allow
                if day_name not in self.league.preferred_days and day_name not in self.league.backup_days:
                    current += timedelta(days=1)
                    continue
                
                # Determine priority based on team and league preferences
                priority = 5  # Default: allowed but not preferred
                
                if day_name in home_preferred and day_name in visitor_preferred:
                    priority = 1  # Both teams prefer this day
                elif day_name in home_preferred or day_name in visitor_preferred:
                    priority = 2  # One team prefers this day
                elif day_name in match.league.preferred_days:
                    priority = 3  # League prefers this day
                elif day_name in match.league.backup_days:
                    priority = 4  # League backup day
                
                candidate_dates.append((date_str, priority))
                current += timedelta(days=1)
            
            # Sort by priority (lower number = higher priority)
            # For same priority, maintain chronological order
            candidate_dates.sort(key=lambda x: (x[1], x[0]))
            
            # Return the requested number of dates
            return [date for date, _ in candidate_dates[:num_dates]]
            
        except Exception as e:
            raise RuntimeError(f"Error getting optimal scheduling dates for match {match.id}: {e}")
    # ========== Convenience Properties ==========
    
    @property
    def facility_name(self) -> str:
        """Get facility name or 'Unscheduled' if no facility"""
        return self.facility.name if self.facility else "Unscheduled"
    
    @property
    def facility_short_name(self) -> str:
        """Get facility short name or 'N/A' if no facility"""
        return self.facility.short_name if self.facility and self.facility.short_name else "N/A"
    
    @property
    def league_name(self) -> str:
        """Get league name"""
        return self.league.name
    
    @property
    def home_team_name(self) -> str:
        """Get home team name"""
        return self.home_team.name
    
    @property
    def visitor_team_name(self) -> str:
        """Get visitor team name"""
        return self.visitor_team.name

    # ========== String Representation ==========
    
    def __str__(self) -> str:
        """String representation of the match"""
        status = self.get_status()
        if self.is_scheduled():
            return f"Match {self.id}: {self.home_team_name} vs {self.visitor_team_name} at {self.facility_name} on {self.date} ({len(self.scheduled_times)} lines, {status})"
        else:
            return f"Match {self.id}: {self.home_team_name} vs {self.visitor_team_name} ({status})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert match to dictionary for serialization"""
        return {
            'id': self.id,
            'league_id': self.league.id,
            'league_name': self.league.name,
            'home_team_id': self.home_team.id,
            'home_team_name': self.home_team.name,
            'visitor_team_id': self.visitor_team.id,
            'visitor_team_name': self.visitor_team.name,
            'facility_id': self.facility.id if self.facility else None,
            'facility_name': self.facility_name,
            'date': self.date,
            'scheduled_times': self.scheduled_times.copy(),
            'status': self.get_status(),
            'num_scheduled_lines': self.get_num_scheduled_lines(),
            'expected_lines': self.get_expected_lines()
        }



    