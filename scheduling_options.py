"""
Scheduling Options Module

This module provides classes for representing comprehensive scheduling options for tennis matches.
It includes detailed time slot information, date-specific options, and utility methods for 
finding optimal scheduling possibilities.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from datetime import datetime, timedelta

from matplotlib.pylab import ceil

# Use TYPE_CHECKING for imports to avoid circular dependencies
if TYPE_CHECKING:
    from usta_match import Match, MatchScheduling
    from usta_facility import Facility, FacilityAvailabilityInfo


@dataclass
class TimeSlotInfo:
    """
    Information about a specific time slot including court availability.
    
    This class encapsulates all the details about a particular time slot,
    including how many courts are available, used, and the utilization percentage.
    """
    
    time: str  # Time in HH:MM format (e.g., "09:00", "14:30")
    total_courts: int  # Total number of courts at this time
    available_courts: int  # Number of courts available for booking
    used_courts: int = 0  # Number of courts already booked
    
    def __post_init__(self) -> None:
        """Validate time slot data"""
        # Validate time format
        if not isinstance(self.time, str):
            raise ValueError("Time must be a string")
        
        try:
            parts = self.time.split(":")
            if len(parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: '{self.time}'. Expected HH:MM format")
        
        # Validate court numbers
        if self.total_courts < 0:
            raise ValueError("Total courts cannot be negative")
        if self.available_courts < 0:
            raise ValueError("Available courts cannot be negative")
        if self.used_courts < 0:
            raise ValueError("Used courts cannot be negative")
        if self.available_courts + self.used_courts > self.total_courts:
            raise ValueError("Available + used courts cannot exceed total courts")
    
    @property
    def utilization_percentage(self) -> float:
        """Calculate the utilization percentage of courts at this time slot"""
        if self.total_courts == 0:
            return 0.0
        return (self.used_courts / self.total_courts) * 100.0
    
    @property
    def availability_percentage(self) -> float:
        """Calculate the availability percentage of courts at this time slot"""
        if self.total_courts == 0:
            return 0.0
        return (self.available_courts / self.total_courts) * 100.0
    
    def can_accommodate(self, courts_needed: int) -> bool:
        """Check if this time slot can accommodate the requested number of courts"""
        return self.available_courts >= courts_needed
    
    def get_availability_level(self) -> str:
        """Get a descriptive availability level (high/medium/low/full)"""
        if self.available_courts == 0:
            return "full"
        elif self.availability_percentage >= 70:
            return "high"
        elif self.availability_percentage >= 30:
            return "medium"
        else:
            return "low"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "time": self.time,
            "total_courts": self.total_courts,
            "available_courts": self.available_courts,
            "used_courts": self.used_courts,
            "utilization_percentage": self.utilization_percentage,
            "availability_percentage": self.availability_percentage,
            "availability_level": self.get_availability_level()
        }


@dataclass
class DateOption:
    """
    Scheduling option for a specific date.
    
    This class represents all the scheduling possibilities for a particular date,
    including time slots, quality scoring, and any conflicts.
    """
    
    date: str  # Date in YYYY-MM-DD format
    day_of_week: str  # Day name (e.g., "Monday", "Tuesday")
    time_slots: List[TimeSlotInfo] = field(default_factory=list)
    quality_score: int = 0  # Match quality score for this date
    conflicts: List[str] = field(default_factory=list)  # List of conflict descriptions
    facility_name: str = ""  # Name of the facility
    
    def __post_init__(self) -> None:
        """Validate date option data"""
        # Validate date format
        if not isinstance(self.date, str):
            raise ValueError("Date must be a string")
        
        try:
            datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: '{self.date}'. Expected YYYY-MM-DD format")
        
        # Validate day of week
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if self.day_of_week not in valid_days:
            raise ValueError(f"Invalid day of week: '{self.day_of_week}'. Must be one of {valid_days}")
        
        # Validate time slots
        if not isinstance(self.time_slots, list):
            raise ValueError("Time slots must be a list")
        
        for slot in self.time_slots:
            if not isinstance(slot, TimeSlotInfo):
                raise ValueError("All time slots must be TimeSlotInfo instances")
    
    def get_available_times(self, courts_needed: int) -> List[str]:
        """Get list of times that can accommodate the requested number of courts"""
        return [
            slot.time for slot in self.time_slots
            if slot.can_accommodate(courts_needed)
        ]
    
    def get_best_time_slots(self, courts_needed: int, limit: int = 5) -> List[TimeSlotInfo]:
        """
        Get the best time slots that can accommodate the match, sorted by availability.
        
        Args:
            courts_needed: Number of courts required
            limit: Maximum number of slots to return
            
        Returns:
            List of TimeSlotInfo objects sorted by availability (most available first)
        """
        suitable_slots = [
            slot for slot in self.time_slots
            if slot.can_accommodate(courts_needed)
        ]
        
        # Sort by availability percentage (highest first)
        suitable_slots.sort(key=lambda slot: slot.availability_percentage, reverse=True)
        
        return suitable_slots[:limit]
    
    def has_conflicts(self) -> bool:
        """Check if this date has any scheduling conflicts"""
        return len(self.conflicts) > 0
    
    def get_total_available_slots(self) -> int:
        """Get total number of available time slots"""
        return len([slot for slot in self.time_slots if slot.available_courts > 0])
    
    def get_peak_utilization(self) -> float:
        """Get the highest utilization percentage across all time slots"""
        if not self.time_slots:
            return 0.0
        return max(slot.utilization_percentage for slot in self.time_slots)
    
    @classmethod
    def from_facility_info(cls, facility_info: 'FacilityAvailabilityInfo', match: 'Match') -> 'DateOption':
        """
        Create a DateOption from a FacilityAvailabilityInfo object.
        
        Args:
            facility_info: Facility availability information
            match: Match object for quality scoring
            
        Returns:
            DateOption instance
        """
        from datetime import datetime
        
        # Convert date to get day of week
        date_obj = datetime.strptime(facility_info.date, "%Y-%m-%d")
        day_of_week = date_obj.strftime("%A")
        
        # Convert time slots
        time_slots = []
        for slot in facility_info.time_slots:
            time_slot = TimeSlotInfo(
                time=slot.time,
                total_courts=slot.total_courts,
                available_courts=slot.available_courts,
                used_courts=slot.used_courts
            )
            time_slots.append(time_slot)
        
        # Calculate quality score
        quality_score = match.get_quality_score(facility_info.date) if match else 0
        
        return cls(
            date=facility_info.date,
            day_of_week=day_of_week,
            time_slots=time_slots,
            quality_score=quality_score,
            facility_name=facility_info.facility_name
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "date": self.date,
            "day_of_week": self.day_of_week,
            "formatted_date": datetime.strptime(self.date, "%Y-%m-%d").strftime("%B %d, %Y"),
            "time_slots": [slot.to_dict() for slot in self.time_slots],
            "time_slot_details": [slot.to_dict() for slot in self.time_slots],  # For template compatibility
            "available_times": self.get_available_times(1),  # Basic availability
            "quality_score": self.quality_score,
            "match_quality": self.quality_score,  # For template compatibility
            "conflicts": self.conflicts,
            "facility_name": self.facility_name,
            "total_time_slots": len(self.time_slots),
            "available_time_slots": self.get_total_available_slots(),
            "peak_utilization": self.get_peak_utilization(),
            "has_conflicts": self.has_conflicts()
        }


class SchedulingOptions:
    """
    Represents comprehensive scheduling options for a match.
    
    This class contains multiple date options with detailed time slot and court 
    availability information. It provides utility methods for finding optimal 
    scheduling possibilities and integrates with the existing match scheduling system.
    """
    
    def __init__(self, match: 'Match', facility: Optional['Facility'] = None):
        """
        Initialize scheduling options for a match.
        
        Args:
            match: Match object that needs scheduling
            facility: Optional facility to restrict options to
        """
        self.match = match
        self.facility = facility
        self.date_options: List[DateOption] = []
        self._creation_time = datetime.now()
    
    def add_date_option(self, date_option: DateOption) -> None:
        """
        Add a date option to the scheduling possibilities.
        
        Args:
            date_option: DateOption to add
        """
        if not isinstance(date_option, DateOption):
            raise TypeError("Expected DateOption instance")
        
        # Check for duplicate dates
        existing_dates = [option.date for option in self.date_options]
        if date_option.date in existing_dates:
            raise ValueError(f"Date option for {date_option.date} already exists")
        
        self.date_options.append(date_option)
        
        # Keep options sorted by date
        self.date_options.sort(key=lambda option: option.date)
    
    def get_best_dates(self, limit: int = 10) -> List[DateOption]:
        """
        Get the best scheduling dates based on quality score and availability.
        
        Args:
            limit: Maximum number of dates to return
            
        Returns:
            List of DateOption objects sorted by quality (best first)
        """
        # Sort by quality score (highest first), then by total available slots
        sorted_options = sorted(
            self.date_options,
            key=lambda option: (option.quality_score, option.get_total_available_slots()),
            reverse=True
        )
        
        return sorted_options[:limit]
    
    def get_dates_by_quality(self, min_quality: int = 0) -> List[DateOption]:
        """
        Get dates filtered by minimum quality score.
        
        Args:
            min_quality: Minimum quality score threshold
            
        Returns:
            List of DateOption objects meeting quality criteria
        """
        return [
            option for option in self.date_options
            if option.quality_score >= min_quality
        ]
    
    def can_schedule_on_date(self, date: str, courts_needed: Optional[int] = None) -> bool:
        """
        Check if match can be scheduled on a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            courts_needed: Number of courts needed (defaults to match requirement)
            
        Returns:
            True if scheduling is possible on this date
        """
        if courts_needed is None:
            courts_needed = self.match.league.num_lines_per_match if self.match.league else 1
        
        date_option = self.get_date_option(date)
        if not date_option:
            return False
        
        # Check if any time slot can accommodate the courts needed
        return len(date_option.get_available_times(courts_needed)) > 0
    
    def get_date_option(self, date: str) -> Optional[DateOption]:
        """
        Get the DateOption for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            DateOption if found, None otherwise
        """
        for option in self.date_options:
            if option.date == date:
                return option
        return None
    
    def get_total_scheduling_possibilities(self) -> int:
        """
        Get total number of possible scheduling time slots across all dates.
        
        Returns:
            Total count of available time slots
        """
        courts_needed = self.match.league.num_lines_per_match if self.match.league else 1
        total = 0
        
        for date_option in self.date_options:
            total += len(date_option.get_available_times(courts_needed))
        
        return total
    
    def get_dates_without_conflicts(self) -> List[DateOption]:
        """Get all date options that have no scheduling conflicts"""
        return [option for option in self.date_options if not option.has_conflicts()]
    
    def get_weekend_options(self) -> List[DateOption]:
        """Get date options that fall on weekends"""
        weekend_days = ["Saturday", "Sunday"]
        return [
            option for option in self.date_options
            if option.day_of_week in weekend_days
        ]
    
    def get_weekday_options(self) -> List[DateOption]:
        """Get date options that fall on weekdays"""
        weekday_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        return [
            option for option in self.date_options
            if option.day_of_week in weekday_days
        ]
    
    def has_any_options(self) -> bool:
        """Check if there are any scheduling options available"""
        return len(self.date_options) > 0
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about the scheduling options"""
        if not self.date_options:
            return {
                "total_dates": 0,
                "total_time_slots": 0,
                "best_quality_score": 0,
                "average_quality_score": 0,
                "dates_with_conflicts": 0,
                "weekend_dates": 0,
                "weekday_dates": 0
            }
        
        quality_scores = [option.quality_score for option in self.date_options]
        
        return {
            "total_dates": len(self.date_options),
            "total_time_slots": sum(len(option.time_slots) for option in self.date_options),
            "total_possibilities": self.get_total_scheduling_possibilities(),
            "best_quality_score": max(quality_scores),
            "average_quality_score": sum(quality_scores) / len(quality_scores),
            "dates_with_conflicts": len([opt for opt in self.date_options if opt.has_conflicts()]),
            "weekend_dates": len(self.get_weekend_options()),
            "weekday_dates": len(self.get_weekday_options()),
            "creation_time": self._creation_time.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization and web interface compatibility.
        
        Returns:
            Dictionary representation suitable for JSON serialization and template rendering
        """
        return {
            "match_id": self.match.id if self.match else None,
            "facility_id": self.facility.id if self.facility else None,
            "facility_name": self.facility.name if self.facility else None,
            "date_options": [option.to_dict() for option in self.date_options],
            "available_dates": [option.to_dict() for option in self.date_options],  # Template compatibility
            "summary_stats": self.get_summary_stats(),
            "best_dates": [option.to_dict() for option in self.get_best_dates(5)],
            "has_options": self.has_any_options()
        }
    
    @classmethod
    def from_facility_availability_list(
        cls, 
        match: 'Match', 
        facility_availability_list: List['FacilityAvailabilityInfo'],
        facility: Optional['Facility'] = None
    ) -> 'SchedulingOptions':
        """
        Create SchedulingOptions from a list of FacilityAvailabilityInfo objects.
        
        Args:
            match: Match object needing scheduling
            facility_availability_list: List of facility availability information
            facility: Optional facility constraint
            
        Returns:
            SchedulingOptions instance populated with the availability data
        """
        options = cls(match, facility)
        
        for facility_info in facility_availability_list:
            if facility_info.available:  # Only add available dates
                try:
                    date_option = DateOption.from_facility_info(facility_info, match)
                    options.add_date_option(date_option)
                except (ValueError, TypeError) as e:
                    # Log error but continue processing other dates
                    print(f"Error processing facility info for {facility_info.date}: {e}")
                    continue
        
        return options
    
    def __len__(self) -> int:
        """Return number of date options"""
        return len(self.date_options)
    
    def __bool__(self) -> bool:
        """Return True if there are any scheduling options"""
        return self.has_any_options()
    
    def __iter__(self):
        """Iterate over date options"""
        return iter(self.date_options)
    
    def get_best_match_scheduling(self, scheduling_mode: str = "same_time") -> Optional['MatchScheduling']:
        """
        Get the best MatchScheduling object based on quality score and availability.
        
        Args:
            scheduling_mode: The scheduling mode to use ("same_time", "split_times", "custom")
            
        Returns:
            MatchScheduling object for the best option, or None if no options available
        """
        if not self.date_options:
            return None
            
        # Get the best date option based on quality score and availability
        best_dates = self.get_best_dates(limit=1)
        if not best_dates:
            return None
            
        best_date_option = best_dates[0]
        
        # Determine how many courts we need
        courts_needed = self.match.league.num_lines_per_match if self.match.league else 1
        
        # Get the best time slots for this date
        best_time_slots = best_date_option.get_best_time_slots(courts_needed, limit=10)
        if not best_time_slots:
            return None
            
        # Convert time slots to list of time strings based on scheduling mode
        if scheduling_mode == "same_time":
            # For same_time, we just need one time slot that can accommodate all courts
            suitable_slots = [slot for slot in best_time_slots if slot.can_accommodate(courts_needed)]
            if not suitable_slots:
                return None
            # Use the first suitable slot. The MatchScheduling needs an array of times. For same_time,
            # we can just repeat the first time slot for all courts.
            selected_times = [suitable_slots[0].time] * courts_needed

        elif scheduling_mode == "split_times":
            # For split_times, we need at least 2 time slots that can accommodate half
            # of the courts each
            suitable_slots = [slot for slot in best_time_slots if slot.can_accommodate(ceil(courts_needed / 2))]
            if len(suitable_slots) < 2:
                return None
            # Use the first two available time slots, we need a selected time for each court
            selected_times = [suitable_slots[0].time, suitable_slots[1].time] * ceil(courts_needed / 2)
            # If we have more courts than slots, repeat the last time slot
            if len(selected_times) < courts_needed:
                selected_times += [suitable_slots[-1].time] * (courts_needed - len(selected_times))
                # If we still don't have enough times, we can't schedule
                if len(selected_times) < courts_needed:
                    return None

        elif scheduling_mode == "custom":
            # We need sum of available courts across all time slots to accommodate the required number of courts
            # For custom, use all available time slots
            selected_times = [slot.time for slot in best_time_slots]

        else:
            raise ValueError(f"Unknown scheduling mode: {scheduling_mode}")
        
        # Import here to avoid circular imports
        from usta_match import MatchScheduling
        
        return MatchScheduling(
            facility=self.facility,
            date=best_date_option.date,
            scheduled_times=selected_times,
            qscore=best_date_option.quality_score
        )
    
    def get_all_match_scheduling_options(self, limit: int = 10) -> List['MatchScheduling']:
        """
        Get multiple MatchScheduling objects for different dates/times.
        
        Args:
            limit: Maximum number of options to return
            
        Returns:
            List of MatchScheduling objects sorted by quality
        """
        match_scheduling_options = []
        
        # Get the best dates
        best_dates = self.get_best_dates(limit=limit)
        courts_needed = self.match.league.num_lines_per_match if self.match.league else 1
        
        from usta_match import MatchScheduling
        
        for date_option in best_dates:
            best_time_slots = date_option.get_best_time_slots(courts_needed, limit=3)
            
            for time_slot in best_time_slots:
                if time_slot.can_accommodate(courts_needed):
                    match_scheduling = MatchScheduling(
                        facility=self.facility,
                        date=date_option.date,
                        scheduled_times=[time_slot.time],
                        qscore=date_option.quality_score
                    )
                    match_scheduling_options.append(match_scheduling)
                    
                    # Stop if we've reached the limit
                    if len(match_scheduling_options) >= limit:
                        return match_scheduling_options
        
        return match_scheduling_options

    def __repr__(self) -> str:
        """String representation"""
        match_info = f"Match {self.match.id}" if self.match else "No match"
        facility_info = f" at {self.facility.name}" if self.facility else ""
        return f"SchedulingOptions({match_info}{facility_info}, {len(self.date_options)} dates)"