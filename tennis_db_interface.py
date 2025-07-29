"""
Tennis Database Interface - Updated with get_available_dates API

Clean abstract interface for tennis database backends.
This interface is backend-agnostic and defines the contract
that all database implementations must follow.

Updated to include get_available_dates API for facility availability checking.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any, TYPE_CHECKING
from datetime import date

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from usta import Team, League, Match, Facility, MatchType
    from usta_facility import FacilityAvailabilityInfo



class TennisDBInterface(ABC):
    """
    Abstract interface for tennis database backends.
    This interface is backend-agnostic and defines the contract
    that all database implementations must follow.
    
    Updated to remove Line class - scheduling is now handled at the Match level
    with scheduled_times arrays.
    """

    # ========== Connection Management ==========
    @abstractmethod
    def connect(self) -> bool:
        """Establish database connection"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Close database connection"""
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Test if database connection is alive"""
        pass


    # ========== Transaction Management ==========
    # ========== Transaction Management ==========
    @abstractmethod
    def begin_transaction(self, dry_run: bool = True):
        """Start a transaction with optional dry-run mode"""
        pass
    
    @abstractmethod
    def commit_transaction(self):
        """Commit the current transaction"""
        pass
    
    @abstractmethod
    def rollback_transaction(self):
        """Rollback the current transaction"""
        pass

    # ========== Team Management ==========
    @abstractmethod
    def add_team(self, team: 'Team') -> bool:
        """Add a new team to the database"""
        pass

    @abstractmethod
    def get_team(self, team_id: int) -> Optional['Team']:
        """Get a team by ID"""
        pass

    @abstractmethod
    def list_teams(self, league: Optional['League'] = None) -> List['Team']:
        """List teams, optionally filtered by league"""
        pass

    @abstractmethod
    def update_team(self, team: 'Team') -> bool:
        """Update an existing team"""
        pass

    @abstractmethod
    def delete_team(self, team: 'Team') -> bool:
        """Delete a team"""
        pass
        

    # ========== League Management ==========
    @abstractmethod
    def add_league(self, league: 'League') -> bool:
        """Add a new league to the database"""
        pass

    @abstractmethod
    def get_league(self, league_id: int) -> Optional['League']:
        """Get a league by ID"""
        pass

    @abstractmethod
    def list_leagues(self) -> List['League']:
        """List all leagues"""
        pass

    @abstractmethod
    def update_league(self, league: 'League') -> bool:
        """Update an existing league"""
        pass

    @abstractmethod
    def delete_league(self, league: 'League') -> bool:
        """Delete a league"""
        pass

    # ========== Match Management ==========
    @abstractmethod
    def add_match(self, match: 'Match') -> bool:
        """Add a match to the database"""
        pass

    @abstractmethod
    def get_match(self, match_id: int) -> Optional['Match']:
        """Get a match by ID with full object references"""
        pass

    from usta import MatchType, Match
    @abstractmethod
    def list_matches(
            self,
            facility: Optional["Facility"] = None,
            league: Optional["League"] = None,
            team: Optional["Team"] = None,
            date_str: Optional[str] = None,
            match_type: Optional["MatchType"] = MatchType.ALL,
        ) -> List[Match]:
        """List matches, optionally filtered by facility, league, team"""
        pass


    @abstractmethod
    def delete_match(self, match: 'Match') -> bool:
        """Delete a match"""
        pass

    @abstractmethod
    def update_match(self, match: Match) -> bool:
        """
        Update a tennis match.  This does not include any checks
        for scheduling conflicts or availability. It simply updates
        the match details in the database.

        Args:
            match (Match): The match object containing details of the match to be updated.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        pass

    @abstractmethod
    def get_matches_on_date(self, date: 'date') -> List['Match']:
        """Get all matches scheduled on a specific date, optionally at a specific facility"""
        pass

    # ========== Facility Management ==========
    @abstractmethod
    def add_facility(self, facility: 'Facility') -> bool:
        """Add a new facility to the database"""
        pass

    @abstractmethod
    def get_facility(self, facility_id: int) -> Optional['Facility']:
        """Get a facility by ID"""
        pass

    @abstractmethod
    def list_facilities(self) -> List['Facility']:
        """List all facilities"""
        pass

    @abstractmethod
    def update_facility(self, facility: 'Facility') -> bool:
        """Update an existing facility"""
        pass

    @abstractmethod
    def delete_facility(self, facility: 'Facility') -> bool:
        """Delete a facility"""
        pass

    @abstractmethod
    def get_facility_availability(self, 
                                  facility: 'Facility', 
                                  dates: List[date],
                                  max_days: int = 50) -> List['FacilityAvailabilityInfo']:
        """ Get availability information for a facility over a date range """
        pass

 
    # ========== Match Scheduling Operations ==========



    @abstractmethod
    def optimize_auto_schedule(self, matches: List['Match'], max_iterations: int = 10, 
                             progress_callback=None) -> Dict[str, Any]:
        """
        Run auto-schedule optimization with multiple iterations to find best scheduling
        
        Args:
            matches: List of matches to schedule
            max_iterations: Maximum number of iterations to run
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary with optimization results including best seed and quality metrics
        """
        pass

    @abstractmethod
    def unschedule_match(self, match: 'Match') -> bool:
        """
        Unschedule a match (remove facility, date, and all scheduled times)
        
        Args:
            match_id: ID of the match to unschedule
        """
        pass

    
    @abstractmethod
    def is_schedulable(self, match: Match, date_obj: date, 
                       facility: Optional['Facility'] = None,
                       allow_split_lines: Optional[bool]=False) -> bool:
        pass
        
    @abstractmethod
    def check_time_availability(self, facility: 'Facility', date: str, time: str, courts_needed: int = 1) -> bool:
        """
        Check if a specific time slot is available at a facility
        
        Args:
            facility_id: Facility to check
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            courts_needed: Number of courts needed
            
        Returns:
            True if available, False otherwise
        """
        pass

    @abstractmethod
    def get_available_times_at_facility(self, facility: 'Facility', date: str, courts_needed: int = 1) -> List[str]:
        """
        Get all available time slots at a facility for the specified number of courts
        
        Args:
            facility_id: Facility to check
            date: Date in YYYY-MM-DD format
            courts_needed: Number of courts needed
            
        Returns:
            List of available time strings in HH:MM format
        """
        pass

    # ========== Advanced Scheduling Operations ==========
 
    @abstractmethod
    def get_facility_conflicts(self, facility: 'Facility', date: str, time: str, duration_hours: int = 3, 
                             exclude_match_id: Optional[int] = None) -> List[Dict]:
        """
        Check for scheduling conflicts at a facility
        
        Args:
            facility_id: Facility to check
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            duration_hours: Duration of the event in hours
            exclude_match_id: Match ID to exclude from conflict checking
            
        Returns:
            List of conflict descriptions
        """
        pass


    @abstractmethod
    def get_scheduling_summary(self, league: Optional['League'] = None) -> Dict[str, Any]:
        """
        Get scheduling summary statistics
        
        Args:
            league_id: Optional league to filter by
            
        Returns:
            Dictionary with scheduling statistics
        """
        pass

    # ========== Statistics and Reporting ==========
    @abstractmethod
    def get_match_statistics(self, league: Optional['League'] = None) -> Dict[str, Any]:
        """
        Get statistics about matches
        
        Args:
            league_id: Optional league to filter by
            
        Returns:
            Dictionary with match statistics
        """
        pass

    @abstractmethod
    def get_facility_usage_report(self, facility: 'Facility', start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Get facility usage report for a date range
        
        Args:
            facility_id: Facility to analyze
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with usage statistics
        """
        pass

    @abstractmethod
    def get_scheduling_conflicts(self, facility: 'Facility', date: str) -> List[Dict[str, Any]]:
        """
        Find potential scheduling conflicts at a facility on a specific date
        
        Args:
            facility_id: Facility to check
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of conflict descriptions
        """
        pass


    # ========== Import/Export ==========
    @abstractmethod
    def export_to_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Export database to YAML file
        
        Args:
            filename: Path to output YAML file
        """
        pass

    @abstractmethod
    def import_from_yaml(self, filename: str, *, 
                        skip_existing: bool = True,
                        validate_only: bool = False) -> Dict[str, Any]:
        """
        Import data from YAML file
        
        Args:
            filename: Path to input YAML file
        """
        pass

    # ========== USTA Constants ==========
    @abstractmethod
    def list_sections(self) -> List[str]:
        """List valid USTA sections"""
        pass

    @abstractmethod
    def list_regions(self) -> List[str]:
        """List valid USTA regions"""
        pass

    @abstractmethod
    def list_age_groups(self) -> List[str]:
        """List valid USTA age groups"""
        pass

    @abstractmethod
    def list_divisions(self) -> List[str]:
        """List valid USTA divisions"""
        pass