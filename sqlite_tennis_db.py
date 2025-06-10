"""
Updated SQLite Tennis Database Implementation

This is the main SQLite implementation that uses helper classes for better modularity.
All the complex logic has been moved to specialized helper classes.
"""

import sqlite3
import yaml
import os
from typing import List, Dict, Optional, Tuple, Any

# Import the interface
from tennis_db_interface import TennisDBInterface

# Import USTA classes
from usta import League, Team, Match, Facility, Line
from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS

# Import helper classes
from sql_team_manager import SQLTeamManager
from sql_league_manager import SQLLeagueManager
from sql_facility_manager import SQLFacilityManager
from sql_match_manager import SQLMatchManager
from sql_scheduling_manager import SQLSchedulingManager


class SQLiteTennisDB(TennisDBInterface):
    """SQLite implementation of the TennisDBInterface using modular helper classes"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize with configuration dictionary
        
        Args:
            config: Configuration dictionary containing 'db_path'
        """
        if not isinstance(config, dict):
            raise TypeError("Configuration must be a dictionary")
        
        if 'db_path' not in config:
            raise ValueError("Configuration must contain 'db_path'")
        
        self.db_path = config['db_path']
        
        if not isinstance(self.db_path, str) or not self.db_path.strip():
            raise ValueError("Database path must be a non-empty string")
        
        self.conn = None
        self.cursor = None
        
        # Initialize helper managers (will be set after database connection)
        self.team_manager = None
        self.league_manager = None
        self.facility_manager = None
        self.match_line_manager = None  # Combined match and line manager
        self.scheduling_manager = None
        
        try:
            self._initialize_schema()
            self._initialize_managers()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database: {e}")

    def _initialize_schema(self):
        """Initialize database schema with tables and constraints"""
        try:
            self.conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None
            )
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Enable foreign key constraints and optimize settings
            self.cursor.execute("PRAGMA foreign_keys = ON")
            self.cursor.execute("PRAGMA journal_mode = WAL")
            self.cursor.execute("PRAGMA synchronous = NORMAL")
            self.cursor.execute("PRAGMA busy_timeout = 30000")
            self.cursor.execute("PRAGMA cache_size = -64000")  # 64MB cache
            
            # REMOVED: self._check_and_migrate_schema() call
            
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                short_name TEXT,
                location TEXT,
                total_courts INTEGER NOT NULL DEFAULT 0
            );
    
            CREATE TABLE IF NOT EXISTS facility_schedules (
                facility_id INTEGER,
                day TEXT NOT NULL,
                time TEXT NOT NULL,
                available_courts INTEGER NOT NULL,
                PRIMARY KEY (facility_id, day, time),
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE CASCADE ON UPDATE CASCADE
            );
    
            CREATE TABLE IF NOT EXISTS facility_unavailable_dates (
                facility_id INTEGER,
                date TEXT NOT NULL,
                PRIMARY KEY (facility_id, date),
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE CASCADE ON UPDATE CASCADE
            );
    
            CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY,
                year INTEGER NOT NULL,
                section TEXT NOT NULL,
                region TEXT NOT NULL,
                age_group TEXT NOT NULL,
                division TEXT NOT NULL,
                name TEXT NOT NULL,
                num_lines_per_match INTEGER NOT NULL DEFAULT 3,
                num_matches INTEGER NOT NULL DEFAULT 10,
                allow_split_lines BOOLEAN NOT NULL DEFAULT 0,
                preferred_days TEXT NOT NULL DEFAULT '',
                backup_days TEXT NOT NULL DEFAULT '',
                start_date TEXT,
                end_date TEXT
            );
    
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                league_id INTEGER NOT NULL,
                home_facility_id INTEGER NOT NULL,
                captain TEXT,
                preferred_days TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (home_facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE
            );
    
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                league_id INTEGER NOT NULL,
                home_team_id INTEGER NOT NULL,
                visitor_team_id INTEGER NOT NULL,
                facility_id INTEGER,
                date TEXT,
                time TEXT,
                status TEXT NOT NULL DEFAULT 'unscheduled',
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (home_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (visitor_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE
            );
    
            CREATE TABLE IF NOT EXISTS lines (
                id INTEGER PRIMARY KEY,
                match_id INTEGER NOT NULL,
                line_number INTEGER NOT NULL,
                facility_id INTEGER,
                date TEXT,
                time TEXT,
                court_number INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                UNIQUE(match_id, line_number)
            );
    
            CREATE INDEX IF NOT EXISTS idx_lines_match_id ON lines(match_id);
            CREATE INDEX IF NOT EXISTS idx_lines_facility_date ON lines(facility_id, date);
            CREATE INDEX IF NOT EXISTS idx_lines_facility_date_time ON lines(facility_id, date, time);
            CREATE INDEX IF NOT EXISTS idx_matches_league_id ON matches(league_id);
            CREATE INDEX IF NOT EXISTS idx_teams_league_id ON teams(league_id);
            CREATE INDEX IF NOT EXISTS idx_facility_schedules_lookup ON facility_schedules(facility_id, day, time);
            CREATE INDEX IF NOT EXISTS idx_matches_team_date ON matches(home_team_id, visitor_team_id, date);
            CREATE INDEX IF NOT EXISTS idx_facilities_short_name ON facilities(short_name);
            CREATE INDEX IF NOT EXISTS idx_teams_home_facility ON teams(home_facility_id);
            """)
        
        except sqlite3.Error as e:
            raise RuntimeError(f"Database initialization failed: {e}")

    def _initialize_managers(self):
        """Initialize all helper manager classes"""
        self.team_manager = SQLTeamManager(self.cursor, self)
        self.league_manager = SQLLeagueManager(self.cursor)
        self.facility_manager = SQLFacilityManager(self.cursor)
        self.match_line_manager = SQLMatchManager(self.cursor, self)  # Combined manager
        self.scheduling_manager = SQLSchedulingManager(self.cursor, self)
    
    # ========== Connection Management ==========
    
    def connect(self) -> None:
        """Establish database connection"""
        if not self.conn:
            self._initialize_schema()
            self._initialize_managers()
    
    def disconnect(self) -> None:
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
                self.conn = None
                self.cursor = None
            except sqlite3.Error:
                pass

    def ping(self) -> bool:
        """Test if database connection is alive"""
        try:
            if self.cursor:
                self.cursor.execute("SELECT 1")
                return True
            return False
        except:
            return False

    def close(self):
        """Explicitly close the database connection (legacy method)"""
        self.disconnect()

    def __del__(self):
        """Ensure database connection is properly closed"""
        self.disconnect()

    # ========== Team Management (Delegated to TeamManager) ==========
    
    def add_team(self, team: Team) -> None:
        return self.team_manager.add_team(team)
    
    def get_team(self, team_id: int) -> Optional[Team]:
        return self.team_manager.get_team(team_id)
    
    def list_teams(self, league_id: Optional[int] = None) -> List[Team]:
        return self.team_manager.list_teams(league_id)

    def update_team(self, team: Team) -> None:
        return self.team_manager.update_team(team)

    def delete_team(self, team_id: int) -> None:
        return self.team_manager.delete_team(team_id)

    def get_teams_by_facility_name(self, facility_name: str, exact_match: bool = True) -> List[Team]:
        """Get all teams that use a specific facility name as their home"""
        return self.team_manager.get_teams_by_facility_name(facility_name, exact_match)    

    # ========== League Management (Delegated to LeagueManager) ==========
    
    def add_league(self, league: League) -> None:
        return self.league_manager.add_league(league)
    
    def get_league(self, league_id: int) -> Optional[League]:
        return self.league_manager.get_league(league_id)
    
    def list_leagues(self) -> List[League]:
        return self.league_manager.list_leagues()

    def update_league(self, league: League) -> None:
        return self.league_manager.update_league(league)

    def delete_league(self, league_id: int) -> None:
        return self.league_manager.delete_league(league_id)

    # ========== Match Management (Delegated to MatchLineManager) ==========
    
    def add_match(self, match: Match) -> None:
        return self.match_line_manager.add_match(match)

    def get_match(self, match_id: int) -> Optional[Match]:
        return self.match_line_manager.get_match(match_id)

    def get_match_with_lines(self, match_id: int) -> Optional[Match]:
        return self.match_line_manager.get_match_with_lines(match_id)

    def list_matches(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List[Match]:
        return self.match_line_manager.list_matches(league_id, include_unscheduled)

    def list_matches_with_lines(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List[Match]:
        return self.match_line_manager.list_matches_with_lines(league_id, include_unscheduled)

    def update_match(self, match: Match) -> None:
        return self.match_line_manager.update_match(match)

    def delete_match(self, match_id: int) -> None:
        return self.match_line_manager.delete_match(match_id)

    # ========== Facility Management (Delegated to FacilityManager) ==========
    
    def add_facility(self, facility: Facility) -> None:
        return self.facility_manager.add_facility(facility)

    def get_facility(self, facility_id: int) -> Optional[Facility]:
        return self.facility_manager.get_facility(facility_id)

    def list_facilities(self) -> List[Facility]:
        return self.facility_manager.list_facilities()

    def update_facility(self, facility: Facility) -> None:
        return self.facility_manager.update_facility(facility)

    def delete_facility(self, facility_id: int) -> None:
        return self.facility_manager.delete_facility(facility_id)

    # ========== Line Management (Delegated to MatchLineManager) ==========

    def add_line(self, line: Line) -> None:
        return self.match_line_manager.add_line(line)

    def get_line(self, line_id: int) -> Optional[Line]:
        return self.match_line_manager.get_line(line_id)

    def list_lines(self, match_id: Optional[int] = None, 
                   facility_id: Optional[int] = None,
                   date: Optional[str] = None) -> List[Line]:
        return self.match_line_manager.list_lines(match_id, facility_id, date)

    def update_line(self, line: Line) -> None:
        return self.match_line_manager.update_line(line)

    def delete_line(self, line_id: int) -> None:
        return self.match_line_manager.delete_line(line_id)

    # ========== Scheduling Operations (Delegated to SchedulingManager) ==========

    def schedule_match_all_lines_same_time(self, match_id: int, facility_id: int, date: str, time: str) -> bool:
        return self.scheduling_manager.schedule_match_all_lines_same_time(match_id, facility_id, date, time)

    def schedule_match_split_lines(self, match_id: int, date: str, 
                                 scheduling_plan: List[Tuple[str, int, int]]) -> bool:
        return self.scheduling_manager.schedule_match_split_lines(match_id, date, scheduling_plan)

    def unschedule_match(self, match_id: int) -> None:
        return self.scheduling_manager.unschedule_match(match_id)

    def check_court_availability(self, facility_id: int, date: str, time: str, 
                               courts_needed: int) -> bool:
        return self.facility_manager.check_court_availability(facility_id, date, time, courts_needed)

    def get_available_courts_count(self, facility_id: int, date: str, time: str) -> int:
        return self.facility_manager.get_available_courts_count(facility_id, date, time)

    # ========== Enhanced Scheduling Methods (Delegated to SchedulingManager) ==========
    
    def get_unscheduled_matches(self, league_id: Optional[int] = None) -> List[Match]:
        return self.match_line_manager.get_unscheduled_matches(league_id)

    def find_scheduling_options_for_match(self, match_id: int, preferred_dates: List[str], 
                                        facility_ids: Optional[List[int]] = None) -> Dict[str, List[Dict]]:
        return self.scheduling_manager.find_scheduling_options_for_match(match_id, preferred_dates, facility_ids)

    def auto_schedule_match(self, match_id: int, preferred_dates: List[str], 
                          prefer_home_facility: bool = True) -> bool:
        return self.scheduling_manager.auto_schedule_match(match_id, preferred_dates, prefer_home_facility)

    def auto_schedule_matches(self, matches: List[Match], dry_run: bool = False) -> Dict[str, Any]:
        return self.scheduling_manager.auto_schedule_matches(matches, dry_run)

    def auto_schedule_league_matches(self, league_id: int, dry_run: bool = False) -> Dict[str, Any]:
        return self.scheduling_manager.auto_schedule_league_matches(league_id, dry_run)

    def get_optimal_scheduling_dates(self, match: Match, 
                                   start_date: Optional[str] = None,
                                   end_date: Optional[str] = None,
                                   num_dates: int = 20) -> List[str]:
        return self.scheduling_manager.get_optimal_scheduling_dates(match, start_date, end_date, num_dates)

    def validate_league_scheduling_feasibility(self, league_id: int) -> Dict[str, Any]:
        return self.scheduling_manager.validate_league_scheduling_feasibility(league_id)

    def get_facility_utilization_detailed(self, facility_id: int, date: str) -> Dict[str, Any]:
        return self.facility_manager.get_facility_utilization_detailed(facility_id, date)

    def get_facility_availability_forecast(self, facility_id: int, 
                                         start_date: str, end_date: str) -> Dict[str, Dict]:
        return self.facility_manager.get_facility_availability_forecast(facility_id, start_date, end_date)

    def get_scheduling_conflicts(self, line_id: int) -> List[Dict]:
        return self.match_line_manager.get_scheduling_conflicts(line_id)

    def get_lines_by_time_slot(self, facility_id: int, date: str, time: str) -> List[Line]:
        return self.facility_manager.get_lines_by_time_slot(facility_id, date, time)

    # ========== Analytics (Delegated to appropriate managers) ==========

    def get_league_scheduling_status(self, league_id: int) -> Dict[str, int]:
        return self.league_manager.get_league_scheduling_status(league_id)

    def get_facility_utilization(self, facility_id: int, start_date: str, end_date: str) -> Dict[str, float]:
        return self.facility_manager.get_facility_utilization(facility_id, start_date, end_date)

    # ========== Bulk Operations (Delegated to MatchLineManager) ==========

    def bulk_create_matches_with_lines(self, league_id: int, teams: List[Team]) -> List[Match]:
        return self.match_line_manager.bulk_create_matches_with_lines(league_id, teams)

    def create_lines_for_match(self, match_id: int, league: League) -> List[Line]:
        return self.match_line_manager.create_lines_for_match(match_id, league)

    # ========== Additional Helper Methods ==========

    def get_teams_by_facility(self, facility_id: int) -> List[Team]:
        """Get all teams that use a specific facility as their home"""
        return self.team_manager.get_teams_by_facility(facility_id)

    def get_matches_by_team(self, team_id: int, include_unscheduled: bool = False) -> List[Match]:
        """Get all matches for a specific team"""
        return self.match_line_manager.get_matches_by_team(team_id, include_unscheduled)

    def get_matches_by_facility(self, facility_id: int, start_date: Optional[str] = None, 
                               end_date: Optional[str] = None) -> List[Match]:
        """Get all matches at a specific facility"""
        return self.match_line_manager.get_matches_by_facility(facility_id, start_date, end_date)

    def get_matches_by_date_range(self, start_date: str, end_date: str, 
                                 league_id: Optional[int] = None) -> List[Match]:
        """Get all matches within a date range"""
        return self.match_line_manager.get_matches_by_date_range(start_date, end_date, league_id)

    def get_scheduled_lines(self, facility_id: Optional[int] = None, 
                          date: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Line]:
        """Get all scheduled lines with filters"""
        return self.match_line_manager.get_scheduled_lines(facility_id, date, start_date, end_date)

    def get_unscheduled_lines(self, match_id: Optional[int] = None, 
                            league_id: Optional[int] = None) -> List[Line]:
        """Get all unscheduled lines with filters"""
        return self.match_line_manager.get_unscheduled_lines(match_id, league_id)

    def get_leagues_by_year(self, year: int) -> List[League]:
        """Get all leagues for a specific year"""
        return self.league_manager.get_leagues_by_year(year)

    def get_active_leagues(self, current_date: str = None) -> List[League]:
        """Get all currently active leagues"""
        return self.league_manager.get_active_leagues(current_date)

    def get_facilities_by_location(self, location: str) -> List[Facility]:
        """Get all facilities in a location"""
        return self.facility_manager.get_facilities_by_location(location)

    def reschedule_match(self, match_id: int, new_facility_id: int, 
                        new_date: str, new_time: str) -> bool:
        """Reschedule a match to new facility/date/time"""
        return self.scheduling_manager.reschedule_match(match_id, new_facility_id, new_date, new_time)

    def find_next_available_slot(self, facility_id: int, preferred_date: str, 
                                courts_needed: int = 1, 
                                search_days_ahead: int = 30) -> Optional[Dict[str, str]]:
        """Find next available time slot at a facility"""
        return self.scheduling_manager.find_next_available_slot(
            facility_id, preferred_date, courts_needed, search_days_ahead
        )

    def get_scheduling_statistics(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive scheduling statistics"""
        return self.scheduling_manager.get_scheduling_statistics(league_id)

    def get_court_usage_statistics(self, facility_id: int, date: str) -> Dict[str, Any]:
        """Get detailed court usage statistics for a facility on a date"""
        return self.match_line_manager.get_court_usage_statistics(facility_id, date)

    def get_match_and_line_statistics(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive statistics for both matches and lines"""
        return self.match_line_manager.get_match_and_line_statistics(league_id)

    # ========== Team Conflict Methods ==========

    def check_team_date_conflict(self, team_id: int, date: str, exclude_match_id: Optional[int] = None) -> bool:
        """Check if team has date conflict"""
        return self.team_manager.check_team_date_conflict(team_id, date, exclude_match_id)

    def get_team_date_conflicts(self, team_id: int, date: str, exclude_match_id: Optional[int] = None) -> List[dict]:
        """Get detailed team date conflict information"""
        return self.team_manager.get_team_date_conflicts(team_id, date, exclude_match_id)

    def check_team_facility_conflict(self, team_id: int, date: str, facility_id: int) -> bool:
        """Check if team has facility conflict"""
        return self.team_manager.check_team_facility_conflict(team_id, date, facility_id)

    # ========== Utility Methods ==========
    
    def load_yaml(self, table: str, yaml_path: str) -> None:
        """Load and insert data from a YAML file into specified table"""
        if not isinstance(table, str) or table not in ["teams", "leagues", "matches", "facilities"]:
            raise ValueError(f"Invalid table name: {table}. Must be one of: teams, leagues, matches, facilities")
        
        if not isinstance(yaml_path, str) or not yaml_path.strip():
            raise ValueError("YAML path must be a non-empty string")
        
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")
        
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {yaml_path}: {e}")
        except IOError as e:
            raise IOError(f"Failed to read YAML file {yaml_path}: {e}")
        
        if not isinstance(data, dict):
            raise ValueError(f"YAML file must contain a dictionary, got: {type(data)}")
        
        records = data.get(table, [])
        if not isinstance(records, list):
            raise ValueError(f"Table '{table}' in YAML must be a list, got: {type(records)}")
    
        method_map = {
            "teams": self.add_team,
            "leagues": self.add_league,
            "matches": self.add_match,
            "facilities": self.add_facility
        }
    
        insert_fn = method_map[table]
        
        for i, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"Record {i} in table '{table}' must be a dictionary, got: {type(record)}")
            
            try:
                # Convert dict to appropriate dataclass
                if table == "teams":
                    # For teams, we need to get the league and facility objects first
                    if 'league_id' not in record:
                        raise ValueError(f"Team record {i} missing required 'league_id' field")
                    if 'home_facility_id' not in record:
                        raise ValueError(f"Team record {i} missing required 'home_facility_id' field")
                    
                    league_id = record.pop('league_id')  # Remove league_id from record
                    home_facility_id = record.pop('home_facility_id')  # Remove home_facility_id from record
                    
                    league = self.get_league(league_id)
                    home_facility = self.get_facility(home_facility_id)
                    
                    if not league:
                        raise ValueError(f"League with ID {league_id} not found for team record {i}")
                    if not home_facility:
                        raise ValueError(f"Facility with ID {home_facility_id} not found for team record {i}")
                    
                    record['league'] = league
                    record['home_facility'] = home_facility
                    obj = Team(**record)
                elif table == "leagues":
                    obj = League(**record)
                elif table == "matches":
                    # For matches, handle optional scheduling fields
                    # Set defaults for missing fields to create unscheduled matches
                    if 'facility_id' not in record:
                        record['facility_id'] = None
                    if 'date' not in record:
                        record['date'] = None
                    if 'time' not in record:
                        record['time'] = None
                    if 'lines' not in record:
                        record['lines'] = []
                    obj = Match(**record)
                elif table == "facilities":
                    # For facilities, use the from_yaml_dict method to handle complex structure
                    obj = Facility.from_yaml_dict(record)
                
                insert_fn(obj)
                
            except Exception as e:
                raise ValueError(f"Failed to process record {i} in table '{table}': {e}")

    # Additional methods for listing USTA constants
    def list_sections(self) -> List[str]:
        return USTA_SECTIONS.copy()

    def list_regions(self) -> List[str]:
        return USTA_REGIONS.copy()

    def list_age_groups(self) -> List[str]:
        return USTA_AGE_GROUPS.copy()

    def list_divisions(self) -> List[str]:
        return USTA_DIVISIONS.copy()


# Test the implementation if run directly
if __name__ == "__main__":
    # Test the implementation
    config = {"db_path": "tennis.db"}
    db = SQLiteTennisDB(config)
    db.connect()
    print("✓ SQLite database connection successful")
    print(f"✓ Database ping: {db.ping()}")
    
    # Test basic functionality
    leagues = db.list_leagues()
    print(f"✓ Found {len(leagues)} leagues")
    
    db.disconnect()
    print("✓ Database disconnected successfully")