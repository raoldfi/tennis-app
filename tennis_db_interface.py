"""
Tennis Database Interface

Clean abstract interface for tennis database backends.
This interface is backend-agnostic and defines the contract
that all database implementations must follow.

This file has no dependencies on USTA classes to avoid circular imports.
Type hints use TYPE_CHECKING to avoid runtime import issues.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from usta import Team, League, Match, Facility, Line


class TennisDBInterface(ABC):
    """
    Abstract interface for tennis database backends.
    This interface is backend-agnostic and defines the contract
    that all database implementations must follow.
    """

    # ========== Connection Management ==========
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection"""
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Test if database connection is alive"""
        pass

    # ========== Team Management ==========
    @abstractmethod
    def add_team(self, team: 'Team') -> None:
        pass

    @abstractmethod
    def get_team(self, team_id: int) -> Optional['Team']:
        pass

    @abstractmethod
    def list_teams(self, league_id: Optional[int] = None) -> List['Team']:
        pass

    @abstractmethod
    def update_team(self, team: 'Team') -> None:
        pass

    @abstractmethod
    def delete_team(self, team_id: int) -> None:
        pass

    # ========== League Management ==========
    @abstractmethod
    def add_league(self, league: 'League') -> None:
        pass

    @abstractmethod
    def get_league(self, league_id: int) -> Optional['League']:
        pass

    @abstractmethod
    def list_leagues(self) -> List['League']:
        pass

    @abstractmethod
    def update_league(self, league: 'League') -> None:
        pass

    @abstractmethod
    def delete_league(self, league_id: int) -> None:
        pass

    # ========== Match Management ==========
    @abstractmethod
    def add_match(self, match: 'Match') -> None:
        pass

    @abstractmethod
    def get_match(self, match_id: int) -> Optional['Match']:
        pass

    @abstractmethod
    def get_match_with_lines(self, match_id: int) -> Optional['Match']:
        pass

    @abstractmethod
    def list_matches(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List['Match']:
        pass

    @abstractmethod
    def list_matches_with_lines(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List['Match']:
        pass

    @abstractmethod
    def update_match(self, match: 'Match') -> None:
        pass

    @abstractmethod
    def delete_match(self, match_id: int) -> None:
        pass

    # ========== Facility Management ==========
    @abstractmethod
    def add_facility(self, facility: 'Facility') -> None:
        pass

    @abstractmethod
    def get_facility(self, facility_id: int) -> Optional['Facility']:
        pass

    @abstractmethod
    def list_facilities(self) -> List['Facility']:
        pass

    @abstractmethod
    def update_facility(self, facility: 'Facility') -> None:
        pass

    @abstractmethod
    def delete_facility(self, facility_id: int) -> None:
        pass

    # ========== Line Management ==========
    @abstractmethod
    def add_line(self, line: 'Line') -> None:
        pass

    @abstractmethod
    def get_line(self, line_id: int) -> Optional['Line']:
        pass

    @abstractmethod
    def list_lines(self, match_id: Optional[int] = None, 
                   facility_id: Optional[int] = None,
                   date: Optional[str] = None) -> List['Line']:
        pass

    @abstractmethod
    def update_line(self, line: 'Line') -> None:
        pass

    @abstractmethod
    def delete_line(self, line_id: int) -> None:
        pass

    # ========== Scheduling Operations ==========
    @abstractmethod
    def schedule_match_all_lines_same_time(self, match_id: int, facility_id: int, date: str, time: str) -> bool:
        pass

    @abstractmethod
    def schedule_match_split_lines(self, match_id: int, date: str, 
                                 scheduling_plan: List[Tuple[str, int, int]]) -> bool:
        pass

    @abstractmethod
    def unschedule_match(self, match_id: int) -> None:
        pass

    @abstractmethod
    def check_court_availability(self, facility_id: int, date: str, time: str, courts_needed: int) -> bool:
        pass

    @abstractmethod
    def get_available_courts_count(self, facility_id: int, date: str, time: str) -> int:
        pass

    # ========== Enhanced Scheduling Methods ==========
    
    @abstractmethod
    def get_unscheduled_matches(self, league_id: Optional[int] = None) -> List['Match']:
        """Get all unscheduled matches, optionally filtered by league"""
        pass

    @abstractmethod
    def find_scheduling_options_for_match(self, match_id: int, preferred_dates: List[str], 
                                        facility_ids: Optional[List[int]] = None) -> Dict[str, List[Dict]]:
        """
        Find all possible scheduling options for a match
        
        Args:
            match_id: Match to schedule
            preferred_dates: List of preferred dates to check
            facility_ids: Optional list of facility IDs to check (if None, checks all)
            
        Returns:
            Dictionary mapping dates to scheduling options
        """
        pass

    @abstractmethod
    def auto_schedule_match(self, match_id: int, preferred_dates: List[str], 
                          prefer_home_facility: bool = True) -> bool:
        """
        Attempt to automatically schedule a single match
        
        Args:
            match_id: Match to schedule
            preferred_dates: List of dates to try (in order of preference)
            prefer_home_facility: Whether to prefer the home team's facility
            
        Returns:
            True if match was successfully scheduled
        """
        pass

    @abstractmethod
    def auto_schedule_matches(self, matches: List['Match'], dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule a list of matches
        
        Args:
            matches: List of matches to schedule
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        pass

    @abstractmethod
    def auto_schedule_league_matches(self, league_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule all unscheduled matches in a league
        
        Args:
            league_id: League to schedule matches for
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        pass

    @abstractmethod
    def get_optimal_scheduling_dates(self, match: 'Match', 
                                   start_date: Optional[str] = None,
                                   end_date: Optional[str] = None,
                                   num_dates: int = 20) -> List[str]:
        """
        Find optimal dates for scheduling a specific match, prioritizing team preferences
        
        Args:
            match: Match to find dates for
            start_date: Start date for search (defaults to league start_date)
            end_date: End date for search (defaults to league end_date)  
            num_dates: Number of dates to return
            
        Returns:
            List of date strings in YYYY-MM-DD format, ordered by preference
            (team preferred days first, then league preferred days, then backup days)
        """
        pass

    @abstractmethod
    def validate_league_scheduling_feasibility(self, league_id: int) -> Dict[str, Any]:
        """
        Analyze whether it's feasible to schedule all matches in a league
        
        Args:
            league_id: League to analyze
            
        Returns:
            Dictionary with feasibility analysis
        """
        pass

    @abstractmethod
    def get_facility_utilization_detailed(self, facility_id: int, date: str) -> Dict[str, Any]:
        """
        Get detailed utilization for a facility on a specific date
        
        Args:
            facility_id: Facility to analyze
            date: Date to check (YYYY-MM-DD format)
            
        Returns:
            Dictionary with detailed utilization information
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_scheduling_conflicts(self, line_id: int) -> List[Dict]:
        """
        Check if a line has any scheduling conflicts with other lines
        
        Args:
            line_id: Line to check for conflicts
            
        Returns:
            List of conflict descriptions
        """
        pass

    @abstractmethod
    def get_lines_by_time_slot(self, facility_id: int, date: str, time: str) -> List['Line']:
        """Get all lines scheduled at a facility on a specific date and time"""
        pass

    # ========== Analytics ==========
    @abstractmethod
    def get_league_scheduling_status(self, league_id: int) -> Dict[str, int]:
        pass

    @abstractmethod
    def get_facility_utilization(self, facility_id: int, start_date: str, end_date: str) -> Dict[str, float]:
        pass

    # ========== Bulk Operations ==========
    @abstractmethod
    def bulk_create_matches_with_lines(self, league_id: int, teams: List['Team']) -> List['Match']:
        pass

    @abstractmethod
    def create_lines_for_match(self, match_id: int, league: 'League') -> List['Line']:
        pass