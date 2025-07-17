"""
Updated Match Class - No Line Class with Immutable Core Fields

The Match class now contains an array of scheduled times instead of Line objects.
All lines for a match are scheduled on the same day at the same facility, but can
have different start times representing different time slots.

Core fields (id, league, home_team, visitor_team) are immutable after creation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from turtle import pen
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from datetime import date, datetime, timedelta
from enum import Enum
import itertools
import re
from collections import defaultdict

from click import Option

# Use TYPE_CHECKING for all USTA classes to avoid circular imports
if TYPE_CHECKING:
    from usta_league import League
    from usta_team import Team
    from usta_facility import Facility




@dataclass
class MatchScheduling:
    """
    Encapsulates scheduling information for a tennis match
    
    Contains facility, date, and scheduled times with validation.
    Either all data is present (complete scheduling) or the object shouldn't exist.
    """
    
    facility: "Facility"  # Direct Facility object reference
    date: str  # YYYY-MM-DD format
    scheduled_times: List[str] = field(default_factory=list)  # Array of HH:MM times

    qscore: int = 0  # Quality score for scheduling, default is 0

    def __post_init__(self) -> None:
        """Validate scheduling data"""
        # Validate facility
        if self.facility is None:
            raise ValueError("Facility cannot be None in MatchScheduling")
        
        # Use duck typing to avoid circular import issues
        if not hasattr(self.facility, "id") or not hasattr(self.facility, "name"):
            raise TypeError(
                f"Facility must be a Facility-like object with 'id' and 'name' attributes, got: {type(self.facility).__name__}"
            )
        
        # Validate date format
        if not isinstance(self.date, str):
            raise ValueError("Date must be a string")
        
        try:
            parts = self.date.split("-")
            if len(parts) != 3:
                raise ValueError("Invalid date format")
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
                raise ValueError("Invalid date values")
        except (ValueError, IndexError):
            raise ValueError(
                f"Invalid date format: '{self.date}'. Expected YYYY-MM-DD format"
            )
        
        # Validate scheduled_times
        if not isinstance(self.scheduled_times, list):
            raise ValueError("scheduled_times must be a list")
        
        for i, time_str in enumerate(self.scheduled_times):
            if not isinstance(time_str, str):
                raise ValueError(
                    f"All scheduled times must be strings, item {i} is {type(time_str)}"
                )
            try:
                parts = time_str.split(":")
                if len(parts) != 2:
                    raise ValueError("Invalid time format")
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time values")
            except (ValueError, IndexError):
                raise ValueError(
                    f"Invalid time format: '{time_str}'. Expected HH:MM format"
                )
        
        # Sort times to maintain order
        self.scheduled_times.sort()
    
    @property
    def is_complete(self) -> bool:
        """Check if scheduling has all required data"""
        return (
            self.facility is not None 
            and self.date is not None 
            and len(self.scheduled_times) > 0
        )
    
    def get_earliest_time(self) -> Optional[str]:
        """Get the earliest scheduled time, or None if no times scheduled"""
        return min(self.scheduled_times) if self.scheduled_times else None
    
    def get_latest_time(self) -> Optional[str]:
        """Get the latest scheduled time, or None if no times scheduled"""
        return max(self.scheduled_times) if self.scheduled_times else None
    
    def get_duration_hours(self) -> float:
        """Estimate total duration in hours based on earliest and latest times"""
        if len(self.scheduled_times) < 2:
            return 3.0  # Default 3 hours for single time or no times
        
        earliest = self.get_earliest_time()
        latest = self.get_latest_time()
        
        if not earliest or not latest:
            return 3.0
        
        # Parse times and calculate difference
        earliest_parts = earliest.split(":")
        latest_parts = latest.split(":")
        
        earliest_minutes = int(earliest_parts[0]) * 60 + int(earliest_parts[1])
        latest_minutes = int(latest_parts[0]) * 60 + int(latest_parts[1])
        
        duration_minutes = (
            latest_minutes - earliest_minutes + 180
        )  # Add 3 hours for last match
        return duration_minutes / 60.0
    
    def add_scheduled_time(self, time: str) -> None:
        """Add a scheduled time and maintain sorted order"""
        # Validate time format
        try:
            parts = time.split(":")
            if len(parts) != 2:
                raise ValueError("Invalid time format")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time values")
        except (ValueError, IndexError):
            raise ValueError(f"Invalid time format: '{time}'. Expected HH:MM format")
        
        if time not in self.scheduled_times:
            self.scheduled_times.append(time)
            self.scheduled_times.sort()
    
    def remove_scheduled_time(self, time: str) -> bool:
        """Remove a scheduled time. Returns True if time was found and removed."""
        if time in self.scheduled_times:
            self.scheduled_times.remove(time)
            return True
        return False
    
    def clear_scheduled_times(self) -> None:
        """Clear all scheduled times"""
        self.scheduled_times.clear()
    
    def get_date_time_strings(self) -> List[str]:
        """Get combined date and time strings for all scheduled lines"""
        return [f"{self.date} {time}" for time in self.scheduled_times]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "facility_id": self.facility.id,
            "facility_name": self.facility.name,
            "date": self.date,
            "scheduled_times": self.scheduled_times.copy(),
            "num_times": len(self.scheduled_times),
            "earliest_time": self.get_earliest_time(),
            "latest_time": self.get_latest_time(),
            "duration_hours": self.get_duration_hours()
        }


class MatchType(Enum):
    """Enumeration of match filtering types for list_matches function"""

    ALL = "all"
    SCHEDULED = "scheduled"
    UNSCHEDULED = "unscheduled"

    def __str__(self) -> str:
        """String representation returns the value for easy printing"""
        return self.value

    @property
    def description(self) -> str:
        """Human-readable description of the match type"""
        descriptions: Dict[str, str] = {
            "all": "All matches (scheduled and unscheduled)",
            "scheduled": "Only fully scheduled matches",
            "unscheduled": "Only unscheduled matches",
        }
        return descriptions[self.value]

    @classmethod
    def from_string(cls, value: str) -> "MatchType":
        """Create MatchType from string value, case-insensitive"""
        value = value.lower().strip()
        for match_type in cls:
            if match_type.value == value:
                return match_type
        raise ValueError(
            f"Invalid match type: '{value}'. Valid options: {[mt.value for mt in cls]}"
        )


@dataclass
class Match:
    """
    Represents a tennis match with direct object references

    The match uses a MatchScheduling object to contain facility, date, and scheduled times.
    All lines are assumed to be at the same facility and date, but can have different start times.

    Core fields (id, league, home_team, visitor_team) are immutable after creation.
    """

    id: int
    round: int  # Match round number (immutable)
    num_rounds: float  # Number of rounds for this league
    league: "League"  # Direct League object reference (IMMUTABLE)
    home_team: "Team"  # Direct Team object reference (IMMUTABLE)
    visitor_team: "Team"  # Direct Team object reference (IMMUTABLE)
    scheduling: Optional[MatchScheduling] = None  # Scheduling information (mutable)

    # a score field to represent the match score
    score: int = 0  # Match score, default is 0 (mutable)

    # quality score for scheduled matches based on date assignment
    qscore: int = (
        0  # Quality score based on date assignment, default is 0 (mutable)
    )
    qscore_penalties: List[str] = field(default_factory=list)  # List of penalties applied during quality scoring (mutable)

    # Private storage for immutable fields - use different names to avoid conflicts
    _immutable_id: Optional[int] = field(init=False, repr=False, default=None)
    _immutable_league: Optional["League"] = field(init=False, repr=False, default=None)
    _immutable_home_team: Optional["Team"] = field(init=False, repr=False, default=None)
    _immutable_visitor_team: Optional["Team"] = field(
        init=False, repr=False, default=None
    )
    _initialized: bool = field(init=False, repr=False, default=False)

    def __post_init__(self) -> None:
        """Validate match data and set up immutable fields"""

        # Store immutable values in private fields
        self._immutable_id = self.id
        self._immutable_round = self.round
        self._immutable_num_rounds = self.num_rounds
        self._immutable_league = self.league
        self._immutable_home_team = self.home_team
        self._immutable_visitor_team = self.visitor_team

        # Validation
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {self.id}")

        # Validate scheduling if provided
        if self.scheduling is not None:
            if not isinstance(self.scheduling, MatchScheduling):
                raise TypeError("scheduling must be a MatchScheduling object or None")

        # Mark as initialized
        self._initialized = True

    # ========== IMMUTABLE PROPERTY PROTECTION ==========

    def get_id(self) -> int:
        """Get the match ID (immutable)"""
        result = self._immutable_id if self._initialized else self.id
        if result is None:
            raise ValueError("Match ID is not initialized")
        return result

    def get_league(self) -> "League":
        """Get the league object (immutable)"""
        result = self._immutable_league if self._initialized else self.league
        if result is None:
            raise ValueError("League is not initialized")
        return result

    def get_round(self) -> int:
        """Get the match round number (immutable)"""
        return self._immutable_round if self._initialized else self.round

    def get_num_rounds(self) -> float:
        """Get the number of rounds for this league (immutable)"""
        return self._immutable_num_rounds if self._initialized else self.num_rounds

    def get_home_team(self) -> "Team":
        """Get the home team object (immutable)"""
        result = self._immutable_home_team if self._initialized else self.home_team
        if result is None:
            raise ValueError("Home team is not initialized")
        return result

    def get_visitor_team(self) -> "Team":
        """Get the visitor team object (immutable)"""
        result = (
            self._immutable_visitor_team if self._initialized else self.visitor_team
        )
        if result is None:
            raise ValueError("Visitor team is not initialized")
        return result

    def get_facility(self) -> Optional["Facility"]:
        """Get the facility object (mutable)"""
        return self.scheduling.facility if self.scheduling else None


    def __setattr__(self, name: str, value: Any) -> None:
        """Override setattr to protect immutable fields after initialization"""
        if hasattr(self, "_initialized") and self._initialized:
            if name in ("id", "league", "home_team", "visitor_team"):
                raise AttributeError(
                    f"Match {name} is immutable and cannot be changed after creation"
                )
        super().__setattr__(name, value)

    # ========== IMMUTABILITY VERIFICATION METHODS ==========

    def verify_immutable_fields(self) -> bool:
        """Verify that immutable fields haven't been tampered with"""
        try:
            return (
                self._immutable_id == self.id
                and self._immutable_league is self.league
                and self._immutable_home_team is self.home_team
                and self._immutable_visitor_team is self.visitor_team
            )
        except AttributeError:
            return False

    def get_immutable_field_info(self) -> Dict[str, Any]:
        """Get information about immutable fields for debugging"""
        return {
            "id": {
                "value": self._immutable_id,
                "type": type(self._immutable_id).__name__,
                "is_protected": self._initialized,
            },
            "league": {
                "value": (
                    getattr(self._immutable_league, "name", "Unknown")
                    if self._immutable_league
                    else None
                ),
                "id": (
                    getattr(self._immutable_league, "id", None)
                    if self._immutable_league
                    else None
                ),
                "type": (
                    type(self._immutable_league).__name__
                    if self._immutable_league
                    else None
                ),
                "is_protected": self._initialized,
            },
            "home_team": {
                "value": (
                    getattr(self._immutable_home_team, "name", "Unknown")
                    if self._immutable_home_team
                    else None
                ),
                "id": (
                    getattr(self._immutable_home_team, "id", None)
                    if self._immutable_home_team
                    else None
                ),
                "type": (
                    type(self._immutable_home_team).__name__
                    if self._immutable_home_team
                    else None
                ),
                "is_protected": self._initialized,
            },
            "visitor_team": {
                "value": (
                    getattr(self._immutable_visitor_team, "name", "Unknown")
                    if self._immutable_visitor_team
                    else None
                ),
                "id": (
                    getattr(self._immutable_visitor_team, "id", None)
                    if self._immutable_visitor_team
                    else None
                ),
                "type": (
                    type(self._immutable_visitor_team).__name__
                    if self._immutable_visitor_team
                    else None
                ),
                "is_protected": self._initialized,
            },
        }

    # ========== Match Scheduling Status ==========

    def is_scheduled(self) -> bool:
        """Check if the match is scheduled (has complete scheduling information)"""
        return self.scheduling is not None and self.scheduling.is_complete

    def is_unscheduled(self) -> bool:
        """Check if the match is unscheduled"""
        return self.scheduling is None

    def is_partially_scheduled(self) -> bool:
        """Check if the match is partially scheduled (has some but not all required lines)"""
        if self.is_unscheduled():
            return False
        expected_lines = self.league.num_lines_per_match
        actual_lines = len(self.scheduling.scheduled_times)
        return 0 < actual_lines < expected_lines

    def is_fully_scheduled(self) -> bool:
        """Check if the match is fully scheduled (has all required lines)"""
        if self.is_unscheduled():
            return False
        expected_lines = self.league.num_lines_per_match
        actual_lines = len(self.scheduling.scheduled_times)
        return actual_lines == expected_lines

    def is_split(self) -> bool:
        """Check if the match is a split match or if all lines are scheduled for the same time"""
        if self.is_unscheduled():
            return False  # An empty list is not split
        scheduled_times = self.scheduling.scheduled_times
        if not scheduled_times:
            return False
        first_time = scheduled_times[0]
        return not all(t == first_time for t in scheduled_times)

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

    # ========== Match Scheduling Options ==========
    
    def get_prioritized_scheduling_options(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        num_dates: Optional[int] = 50,
        minimum_quality: int = 1,
    ) -> List[MatchScheduling]:
        """
        Find prioritized options for scheduling a specific match, prioritizing team and league preferences.

        Args:
            start_date: Start date for search (defaults to league start_date)
            end_date: End date for search (defaults to league end_date)
            num_dates: Maximum number of dates to return

        Returns:
            List of MatchScheduling objects, ordered by qscore
            Uses the same quality scoring system as calculate_quality_score()

        Raises:
            ValueError: If any validation fails
            RuntimeError: If an error occurs during date calculation
        """

        try:
            # Validate league requirements
            if not self.league.start_date or not self.league.end_date:
                raise ValueError(
                    "League start_date and end_date must be set to calculate scheduling dates"
                )

            # Use league dates or reasonable defaults for search range
            search_start = (
                start_date
                or self.league.start_date
                or datetime.now().strftime("%Y-%m-%d")
            )
            search_end = end_date or self.league.end_date

            if not search_end:
                # Default to 16 weeks from start
                start_dt = datetime.strptime(search_start, "%Y-%m-%d")
                end_dt = start_dt + timedelta(weeks=16)
                search_end = end_dt.strftime("%Y-%m-%d")

            # Generate candidate dates using the priority calculation logic
            start_dt = datetime.strptime(search_start, "%Y-%m-%d")
            end_dt = datetime.strptime(search_end, "%Y-%m-%d")

            candidate_options = []
            current = start_dt

            # Iterate through each day in the date range
            while current <= end_dt:
                try:
                    day_name = current.strftime("%A")
                    date_str = current.strftime("%Y-%m-%d")

                    # iterate through facilities
                    facilities = self.home_team.preferred_facilities

                    for facility in facilities:
                        if not facility:
                            raise ValueError(
                                f"Home team {self.home_team.name} has no preferred facilities set"
                            )
                        
                        # if the facility is not available on this date, skip it
                        if not facility.is_available_on_date(date_str):
                            continue
                        
                        # Calculate quality score for this date
                        qscore, _ = self.calculate_quality_score(date=date_str, facility=facility)

                        # Skip dates with a quality score below the minimum
                        if qscore >= minimum_quality:
                            
                            scheduling = MatchScheduling(
                                facility=facility,
                                date=date_str,
                                qscore=qscore
                            )
                            candidate_options.append(scheduling)

                    current += timedelta(days=1)

                except Exception as date_error:
                    print(f"Error processing date {current}: {date_error}")
                    current += timedelta(days=1)
                    continue

            # If no candidate dates found, return empty list
            if not candidate_options:
                return []

            # Sort by qscore (higher number = higher priority)
            candidate_options.sort(key=lambda x: x.qscore, reverse=True)

            # Return the requested number of options with their quality scores
            return candidate_options[:num_dates]

        except Exception as e:
            # Catch any errors during date calculation and raise a runtime error
            raise RuntimeError(
                f"Error getting optimal scheduling dates for match {self.id}: {e}"
            )

    # ========== Match Line Management ==========


    def get_num_scheduled_lines(self) -> int:
        """Get the number of scheduled lines (times)"""
        return len(self.scheduling.scheduled_times) if self.scheduling else 0
    
    def get_scheduled_times(self) -> List[str]:
        """Get the list of scheduled times for this match"""
        return self.scheduling.scheduled_times.copy() if self.scheduling else []
    
    def get_date_time_strings(self) -> List[str]:
        """Get combined date and time strings for all scheduled lines"""
        return self.scheduling.get_date_time_strings() if self.scheduling else []
    
    def get_earliest_time(self) -> Optional[str]:
        """Get the earliest scheduled time, or None if no times scheduled"""
        return self.scheduling.get_earliest_time() if self.scheduling else None
    
    def get_latest_time(self) -> Optional[str]:
        """Get the latest scheduled time, or None if no times scheduled"""
        return self.scheduling.get_latest_time() if self.scheduling else None
    
    def get_match_duration_hours(self) -> float:
        """Estimate match duration in hours based on earliest and latest times"""
        return self.scheduling.get_duration_hours() if self.scheduling else 3.0
    
    def add_scheduled_time(self, time: str) -> None:
        """Add a scheduled time for a new line"""
        if self.scheduling is None:
            raise ValueError("Cannot add scheduled time to unscheduled match. Use a scheduling method first.")
        self.scheduling.add_scheduled_time(time)

    def remove_scheduled_time(self, time: str) -> bool:
        """Remove a scheduled time. Returns True if time was found and removed."""
        if self.scheduling is None:
            return False
        return self.scheduling.remove_scheduled_time(time)

    def clear_scheduled_times(self) -> None:
        """Clear all scheduled times (unschedule all lines)"""
        if self.scheduling is not None:
            self.scheduling.clear_scheduled_times()

    def get_expected_lines(self) -> int:
        """Get the expected number of lines from the league configuration"""
        return self.league.num_lines_per_match

    def get_missing_lines_count(self) -> int:
        """Get the number of lines still needed to be scheduled"""
        return max(0, self.get_expected_lines() - self.get_num_scheduled_lines())


    # ========== Convenience Properties ==========
    
    @property
    def facility(self) -> Optional["Facility"]:
        """Get the facility object through MatchScheduling delegation"""
        return self.scheduling.facility if self.scheduling else None
    
    @property  
    def date(self) -> Optional[str]:
        """Get the scheduled date through MatchScheduling delegation"""
        return self.scheduling.date if self.scheduling else None
    
    @property
    def scheduled_times(self) -> List[str]:
        """Get the scheduled times through MatchScheduling delegation"""
        return self.scheduling.scheduled_times.copy() if self.scheduling else []

    # ========== Match Information ==========


    # ========== Quality Scoring ==========

    def calculate_quality_score(self, 
                                date: Optional[str] = None,
                                facility: Optional["Facility"] = None) -> Tuple[int, Optional[List[str]]]:
        """
        Calculate a quality score for a match based on a date assignment.

        Args:
            date: Optional date string in YYYY-MM-DD format. If not provided, uses self.date.
            facility: Optional Facility object. If provided, checks against home team's preferred facilities.

        Returns a quality score as an integer and a list of penalties applied:
            Quality score (higher number = higher quality) and a string describing penalties:
            - 100: Optimal - Teams' League preferred + Within round + Preferred facility
            - 80-100: Good - Teams' League backup + Within round
            - 60-80: Fair - League preferred + Outside round
            - 40-60: Acceptable - League backup + Outside round
            - 20-40: Poor - Scheduled on a day not preferred by anyone
            - 0-20: Worst - No quality
        """
        # get penalty constants from league
        if not self.league:
            raise ValueError("League must be set to calculate quality score")
        
        TEAM_PENALTY = self.league.TEAM_PENALTY
        LEAGUE_PENALTY = self.league.LEAGUE_PENALTY
        ROUND_PENALTY = self.league.ROUND_PENALTY
        FACILITY_PENALTY = self.league.FACILITY_PENALTY

        # Initialize penalties to empty list
        penalties = []

        # Use provided date or fall back to match's current date
        target_date = date or self.date

        if not target_date:
            return 0  # No date to evaluate

        try:
            # Get the day of week for the target date
            match_date = datetime.strptime(target_date, "%Y-%m-%d")
            day_name = match_date.strftime("%A")

            # Determine team requirements
            hp = set(self.home_team.preferred_days)
            vp = set(self.visitor_team.preferred_days)

            team_preferred_days = None
            if hp and vp:
                team_preferred_days = hp & vp  # Intersection if both have preferences
            elif hp or vp:
                team_preferred_days = hp | vp  # Union if only one has preferences

            # Check if the date is within the match's round
            if not self.league.start_date or not self.league.end_date:
                return 99  # Cannot calculate without league dates
            league_start = datetime.strptime(self.league.start_date, "%Y-%m-%d")
            league_end = datetime.strptime(self.league.end_date, "%Y-%m-%d")
            league_days = (league_end - league_start).days
            days_per_round = league_days // self.num_rounds
            if league_days % self.num_rounds != 0:
                days_per_round += 1

            round_start = league_start + timedelta(
                days=(self.round - 1) * days_per_round
            )
            round_end = round_start + timedelta(days=days_per_round)
            in_round = round_start.date() <= match_date.date() <= round_end.date()

            # Start at 100
            quality = 100  # Default: not preferred by anyone

            # if there are team preferred days and this day is not in them return 20
            if team_preferred_days is not None:
                if day_name in team_preferred_days:
                    quality -= 0  # No penalty for team preferred day
                else:
                    quality -= TEAM_PENALTY  # Severe penalty for not preferred day for teams
                    penalties.append(f"team_penalty:{TEAM_PENALTY}")

            # Deal with preferred and backup days first
            if day_name in self.league.preferred_days:
                quality -= 0  # No penalty for league preferred day
            elif day_name in self.league.backup_days:
                quality -= LEAGUE_PENALTY  # League backup day
                penalties.append(f"league_penalty:{LEAGUE_PENALTY}")
            else:
                quality -= 3 * LEAGUE_PENALTY  # outside all preferred and backup days
                penalties.append(f"league_penalty:{3 * LEAGUE_PENALTY}")

            # Make sure the facility is one of the home team's preferred facilities
            if facility is not None and facility not in self.home_team.preferred_facilities:
                raise ValueError(
                    f"Facility {facility.name} is not preferred by home team {self.home_team.name}"
                )
            
            # Deal with facility preferences
            if facility is None and self.scheduling and self.scheduling.facility:
                facility = self.scheduling.facility

            # the facility is provided, iterate through the home team's preferred facilities
            if facility is not None and self.home_team.preferred_facilities:
                facilities = self.home_team.preferred_facilities
                for i, pref_facility in enumerate(facilities):
                    if facility.id == pref_facility.id:
                        quality -= i * FACILITY_PENALTY  # Penalty based on index in preferred facilities
                        if i > 0:
                            penalties.append(f"facility_penalty:{i * FACILITY_PENALTY}")
                        break

            # Add penalty if outside round
            if not in_round:
                quality -= ROUND_PENALTY
                penalties.append(f"round_penalty:{ROUND_PENALTY}")

            return (quality, penalties)

        except (ValueError, AttributeError) as e:
            # Raise error if there's an issue calculating quality score
            raise RuntimeError(f"Error calculating quality score for match {self.id}: {e}")

    def update_quality_score(self) -> None:
        """Update the quality_score field based on current scheduling"""
        result = self.calculate_quality_score()
        self.qscore = result[0]
        self.qscore_penalties = result[1]

    @staticmethod
    def calculate_quality_score_description(score: int = None) -> str:
        """Get a human-readable description of quality scores (static method)"""
        descriptions = {
            0: "Unscheduled (no quality)",
            20: "Poor - Scheduled on a day not preferred by anyone",
            40: "Acceptable - League backup + Outside round",
            60: "Fair - League preferred + Outside round",
            80: "Good - Teams' League backup + Within round",
            100: "Optimal - Teams' League preferred + Within round",
        }
        if score is None:
            return "Quality scores: " + ", ".join(
                [f"{k} = {v.lower()}" for k, v in descriptions.items() if k > 0]
            )
        return descriptions.get(score, f"Unknown priority score: {score}")

    # ========== Match Scheduling Operations ==========

    def assign_scheduling(self, scheduling: MatchScheduling) -> bool:
        """
        Assign a MatchScheduling object to this match.

        Args:
            scheduling: MatchScheduling object containing facility, date, and times

        Returns:
            True if successful, raises ValueError if scheduling is invalid
        """
        if not isinstance(scheduling, MatchScheduling):
            raise ValueError("scheduling must be a MatchScheduling object")
        
        # Validate the scheduling data
        if not scheduling.is_complete:
            raise ValueError("MatchScheduling must have complete data (facility, date, times)")

        self.scheduling = scheduling
        return True
    
    
    # def schedule_lines_split_times(
    #     self, facility: "Facility", date: str, scheduled_times: List[str]
    # ) -> bool:
    #     """
    #     Schedule lines using an array of scheduled times (split times mode)

    #     Args:
    #         facility: Facility where match will be played
    #         date: Date in YYYY-MM-DD format
    #         scheduled_times: List of times for each line (e.g., ["09:00", "09:00", "12:00"])
    #                         Length must match league.num_lines_per_match

    #     Examples:
    #         # 3-line match with 2 lines at 9:00 AM, 1 line at 12:00 PM
    #         match.schedule_lines_split_times(facility, "2025-06-25", ["09:00", "09:00", "12:00"])

    #         # 4-line match with 2 lines at each time
    #         match.schedule_lines_split_times(facility, "2025-06-25", ["09:00", "09:00", "12:00", "12:00"])

    #         # 5-line match with 3 lines at first time, 2 at second
    #         match.schedule_lines_split_times(facility, "2025-06-25", ["09:00", "09:00", "09:00", "12:00", "12:00"])
    #     """
    #     # Validate that we have the correct number of times
    #     expected_lines = self.league.num_lines_per_match
    #     if len(scheduled_times) != expected_lines:
    #         raise ValueError(
    #             f"Must provide exactly {expected_lines} scheduled times, got {len(scheduled_times)}"
    #         )

    #     # Validate each time format
    #     for i, time_str in enumerate(scheduled_times):
    #         if not isinstance(time_str, str):
    #             raise ValueError(
    #                 f"All scheduled times must be strings, item {i} is {type(time_str)}"
    #             )
    #         try:
    #             parts = time_str.split(":")
    #             if len(parts) != 2:
    #                 raise ValueError("Invalid time format")
    #             hour, minute = int(parts[0]), int(parts[1])
    #             if not (0 <= hour <= 23 and 0 <= minute <= 59):
    #                 raise ValueError("Invalid time values")
    #         except (ValueError, IndexError):
    #             raise ValueError(
    #                 f"Invalid time format: '{time_str}'. Expected HH:MM format"
    #             )

    #     # Create MatchScheduling object
    #     self.scheduling = MatchScheduling(
    #         facility=facility,
    #         date=date,
    #         scheduled_times=sorted(scheduled_times.copy())  # Sort to maintain order
    #     )
    #     return True

    # def schedule_all_lines_same_time(
    #     self, facility: "Facility", date: str, time: str
    # ) -> bool:
    #     """Schedule all lines at the same time slot"""
    #     self.scheduling = MatchScheduling(
    #         facility=facility,
    #         date=date,
    #         scheduled_times=[time] * self.league.num_lines_per_match
    #     )
    #     return True

    # def schedule_lines_custom_times(
    #     self, facility: "Facility", date: str, times: List[str]
    # ) -> bool:
    #     """
    #     Schedule match lines with custom times for each line

    #     Args:
    #         facility: Facility where match will be played
    #         date: Date in YYYY-MM-DD format
    #         times: List of time strings, one for each line

    #     Returns:
    #         True if successful
    #     """
    #     if not isinstance(times, list):
    #         raise ValueError("Times must be a list")

    #     expected_lines = self.get_expected_lines()
    #     if len(times) != expected_lines:
    #         raise ValueError(
    #             f"Custom mode requires exactly {expected_lines} time slots, got {len(times)}"
    #         )

    #     # Create MatchScheduling object
    #     self.scheduling = MatchScheduling(
    #         facility=facility,
    #         date=date,
    #         scheduled_times=times.copy()  # Make a copy to avoid reference issues
    #     )
    #     return True

    def unschedule(self) -> bool:
        """Unschedule the match (remove facility, date, and all times)"""
        self.scheduling = None
        return True

    # ========== Convenience Properties ==========

    @property
    def facility_name(self) -> str:
        """Get facility name or 'Unscheduled' if no facility"""
        return self.facility.name if self.facility else "Unscheduled"

    @property
    def facility_short_name(self) -> str:
        """Get facility short name or 'N/A' if no facility"""
        return (
            self.facility.short_name
            if self.facility and self.facility.short_name
            else "N/A"
        )

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
            "id": self.id,
            "league_id": self.league.id,
            "league_name": self.league.name,
            "home_team_id": self.home_team.id,
            "home_team_name": self.home_team.name,
            "visitor_team_id": self.visitor_team.id,
            "visitor_team_name": self.visitor_team.name,
            "facility_id": self.facility.id if self.facility else None,
            "facility_name": self.facility_name,
            "date": self.date,
            "scheduled_times": self.scheduled_times.copy(),
            "status": self.get_status(),
            "num_scheduled_lines": self.get_num_scheduled_lines(),
            "expected_lines": self.get_expected_lines(),
        }
