"""
Updated Match Class - No Line Class with Immutable Core Fields

The Match class now contains an array of scheduled times instead of Line objects.
All lines for a match are scheduled on the same day at the same facility, but can
have different start times representing different time slots.

Core fields (id, league, home_team, visitor_team) are immutable after creation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, TYPE_CHECKING
from datetime import date, datetime, timedelta
from enum import Enum
import itertools
import re
from collections import defaultdict

# Use TYPE_CHECKING for all USTA classes to avoid circular imports
if TYPE_CHECKING:
    from usta_league import League
    from usta_team import Team
    from usta_facility import Facility


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

    The match contains an array of scheduled times instead of Line objects.
    All lines are assumed to be at the same facility and date, but can have different start times.

    Core fields (id, league, home_team, visitor_team) are immutable after creation.
    """

    id: int
    round: int  # Match round number (immutable)
    num_rounds: float  # Number of rounds for this league
    league: "League"  # Direct League object reference (IMMUTABLE)
    home_team: "Team"  # Direct Team object reference (IMMUTABLE)
    visitor_team: "Team"  # Direct Team object reference (IMMUTABLE)
    facility: Optional["Facility"] = None  # Direct Facility object reference (mutable)
    date: Optional[str] = None  # YYYY-MM-DD format (mutable)
    scheduled_times: List[str] = field(
        default_factory=list
    )  # Array of HH:MM times (mutable)

    # a score field to represent the match score
    score: int = 0  # Match score, default is 0 (mutable)

    # priority score for scheduled matches based on date assignment
    priority_score: int = (
        0  # Priority score based on date assignment, default is 0 (mutable)
    )

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

        # If the facility is None, set it to the home_team's facility
        if self.facility is None:
            if self.home_team and hasattr(self.home_team, "home_facility"):
                self.facility = self.home_team.home_facility
            else:
                raise ValueError(
                    "Facility must be provided or home_team must have a facility"
                )
        elif self.facility is not None:
            # Use duck typing instead of isinstance check to avoid circular import issues
            if not hasattr(self.facility, "id") or not hasattr(self.facility, "name"):
                raise TypeError(
                    f"Facility must be a Facility-like object with 'id' and 'name' attributes, got: {type(self.facility).__name__}"
                )

        # Validation
        if not isinstance(self.id, int) or self.id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {self.id}")

        # Validate date format if provided
        if self.date is not None:
            if not isinstance(self.date, str):
                raise ValueError("Date must be a string or None")
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
        return self.facility

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
        """Check if the match is scheduled (has facility, date, and at least one time)"""
        return all(
            [
                self.facility is not None,
                self.date is not None,
                len(self.scheduled_times) > 0,
            ]
        )

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

    def is_split(self) -> bool:
        """Check if the match is a split match or if all lines are scheduled for the same time"""
        if not self.scheduled_times:
            return True  # An empty list is not split
        first_time = self.scheduled_times[0]
        return all(t == first_time for t in self.scheduled_times)

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

    def get_prioritized_scheduling_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        num_dates: Optional[int] = 50,
        minimum_quality: int = 40,
    ) -> List[Tuple[str, int]]:
        """
        Find prioritized dates for scheduling a specific match, prioritizing team and league preferences.

        Args:
            start_date: Start date for search (defaults to league start_date)
            end_date: End date for search (defaults to league end_date)
            num_dates: Number of dates to return

        Returns:
            List of tuples (date_string, qscore) in YYYY-MM-DD format, ordered by qscore
            Uses the same quality scoring system as get_quality_score()

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

            # Create a set that includes both preferred and backup days
            preferred_days = set(self.league.preferred_days)
            backup_days = set(self.league.backup_days)
            all_allowed_days = preferred_days | backup_days

            # Verify that all_allowed_days is not empty
            if not all_allowed_days:
                raise ValueError(
                    "League must have preferred_days or backup_days set to calculate scheduling dates"
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

            candidate_dates = []
            current = start_dt

            # Iterate through each day in the date range
            while current <= end_dt:
                try:
                    day_name = current.strftime("%A")
                    date_str = current.strftime("%Y-%m-%d")

                    # Skip days that the league doesn't allow (DO WE WANT THIS TO BE AN OPTION)
                    if day_name not in all_allowed_days:
                        current += timedelta(days=1)
                        continue

                    # Calculate quality score for this date
                    qscore = self.get_quality_score(date_str)

                    # Skip dates with a quality score below the minimum
                    if qscore > minimum_quality:
                        candidate_dates.append((date_str, qscore))

                    current += timedelta(days=1)

                except Exception as date_error:
                    print(f"Error processing date {current}: {date_error}")
                    current += timedelta(days=1)
                    continue

            # If no candidate dates found, return empty list
            if not candidate_dates:
                return []

            # Sort by qscore (higher number = higher priority)
            candidate_dates.sort(key=lambda x: x[1], reverse=True)

            # Return the requested number of dates with their quality scores
            return candidate_dates[:num_dates]

        except Exception as e:
            # Catch any errors during date calculation and raise a runtime error
            raise RuntimeError(
                f"Error getting optimal scheduling dates for match {self.id}: {e}"
            )

    # ========== Match Line Management ==========

    def get_scheduled_times(self) -> List[str]:
        """
        Get the list of scheduled times for this match.

        Returns:
            List of scheduled time strings in HH:MM format, sorted chronologically.
            Returns empty list if no times are scheduled.
        """
        return self.scheduled_times if self.scheduled_times else []

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
        earliest_parts = earliest.split(":")
        latest_parts = latest.split(":")

        earliest_minutes = int(earliest_parts[0]) * 60 + int(earliest_parts[1])
        latest_minutes = int(latest_parts[0]) * 60 + int(latest_parts[1])

        duration_minutes = (
            latest_minutes - earliest_minutes + 180
        )  # Add 3 hours for last match
        return duration_minutes / 60.0

    # ========== Quality Scoring ==========

    def get_quality_score(self, date: Optional[str] = None) -> int:
        """
        Calculate a quality score for a match based on a date assignment.

        Args:
            date: Optional date string in YYYY-MM-DD format. If not provided, uses self.date.

        Returns:
            Quality score (higher number = higher quality):
            - 0: Unscheduled (no quality)
            - 100: Optimal - Teams' League preferred + Within round
            - 80: Good - Teams' League backup + Within round
            - 60: Fair - League preferred + Outside round
            - 40: Acceptable - League backup + Outside round
            - 20: Poor - Scheduled on a day not preferred by anyone
        """
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

            # Calculate base quality
            base_quality = 20  # Default: not preferred by anyone

            # Deal with preferred and backup days first
            if day_name in self.league.preferred_days:
                base_quality = 100  # League prefers this day
            elif day_name in self.league.backup_days:
                base_quality = 80  # League backup day

            # Add penalty if outside round
            if not in_round:
                base_quality -= 40

            # if there are team preferred days and this day is not in them return 20
            if team_preferred_days is not None:
                # If the day is not in team preferred days, set to optimal quality
                if day_name not in team_preferred_days:
                    return 20

            return base_quality

        except (ValueError, AttributeError) as e:
            # If there's an error calculating, return lowest quality
            return 20

    def update_quality_score(self) -> None:
        """Update the quality_score field based on current scheduling"""
        self.quality_score = self.get_quality_score()

    @staticmethod
    def get_quality_score_description(score: int = None) -> str:
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

    def schedule_lines_split_times(
        self, facility: "Facility", date: str, scheduled_times: List[str]
    ) -> bool:
        """
        Schedule lines using an array of scheduled times (split times mode)

        Args:
            facility: Facility where match will be played
            date: Date in YYYY-MM-DD format
            scheduled_times: List of times for each line (e.g., ["09:00", "09:00", "12:00"])
                            Length must match league.num_lines_per_match

        Examples:
            # 3-line match with 2 lines at 9:00 AM, 1 line at 12:00 PM
            match.schedule_lines_split_times(facility, "2025-06-25", ["09:00", "09:00", "12:00"])

            # 4-line match with 2 lines at each time
            match.schedule_lines_split_times(facility, "2025-06-25", ["09:00", "09:00", "12:00", "12:00"])

            # 5-line match with 3 lines at first time, 2 at second
            match.schedule_lines_split_times(facility, "2025-06-25", ["09:00", "09:00", "09:00", "12:00", "12:00"])
        """
        # Validate that we have the correct number of times
        expected_lines = self.league.num_lines_per_match
        if len(scheduled_times) != expected_lines:
            raise ValueError(
                f"Must provide exactly {expected_lines} scheduled times, got {len(scheduled_times)}"
            )

        # Validate each time format
        for i, time_str in enumerate(scheduled_times):
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

        # Set match details
        self.facility = facility
        self.date = date
        self.scheduled_times = sorted(scheduled_times.copy())  # Sort to maintain order
        return True

    def schedule_all_lines_same_time(
        self, facility: "Facility", date: str, time: str
    ) -> bool:
        """Schedule all lines at the same time slot"""
        self.facility = facility
        self.date = date
        self.scheduled_times = [time] * self.league.num_lines_per_match
        return True

    def schedule_lines_custom_times(
        self, facility: "Facility", date: str, times: List[str]
    ) -> bool:
        """
        Schedule match lines with custom times for each line

        Args:
            facility: Facility where match will be played
            date: Date in YYYY-MM-DD format
            times: List of time strings, one for each line

        Returns:
            True if successful
        """
        if not isinstance(times, list):
            raise ValueError("Times must be a list")

        expected_lines = self.get_expected_lines()
        if len(times) != expected_lines:
            raise ValueError(
                f"Custom mode requires exactly {expected_lines} time slots, got {len(times)}"
            )

        # Update match properties
        self.facility = facility
        self.date = date
        self.scheduled_times = times.copy()  # Make a copy to avoid reference issues

        return True

    def unschedule(self) -> bool:
        """Unschedule the match (remove facility, date, and all times)"""
        self.facility = None
        self.date = None
        self.scheduled_times.clear()
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
