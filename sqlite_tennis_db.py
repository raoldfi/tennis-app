"""
Updated SQLite Tennis Database Implementation - Updated for Object-Based Interface

This version updates the implementation to match the new TennisDBInterface
that uses actual object instances instead of IDs for many operations.

Added get_available_dates API for finding available dates at facilities.
"""

import sqlite3
import yaml
import os
from typing import List, Dict, Optional, Tuple, Any

# Import the interface
from tennis_db_interface import TennisDBInterface

from usta import League, Team, Match, Facility, MatchType

from usta_constants import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS

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
        self.match_manager = None
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
            self.cursor.execute("PRAGMA cache_size = 10000")
            self.cursor.execute("PRAGMA temp_store = memory")
            
            # Create all tables with proper constraints
            self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                section TEXT NOT NULL,
                region TEXT NOT NULL,
                age_group TEXT NOT NULL,
                division TEXT NOT NULL,
                num_lines_per_match INTEGER NOT NULL DEFAULT 3,
                num_matches INTEGER NOT NULL DEFAULT 10,
                allow_split_lines BOOLEAN NOT NULL DEFAULT 0,
                preferred_days TEXT,
                backup_days TEXT,
                start_date TEXT,
                end_date TEXT
            );
    
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                short_name TEXT NOT NULL,
                location TEXT,
                total_courts INTEGER NOT NULL DEFAULT 0
            );
    
            CREATE TABLE IF NOT EXISTS facility_schedules (
                id INTEGER PRIMARY KEY,
                facility_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                time TEXT NOT NULL,
                available_courts INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE CASCADE ON UPDATE CASCADE,
                UNIQUE(facility_id, day, time)
            );
    
            CREATE TABLE IF NOT EXISTS facility_unavailable_dates (
                id INTEGER PRIMARY KEY,
                facility_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE CASCADE ON UPDATE CASCADE,
                UNIQUE(facility_id, date)
            );
    
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                league_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                captain TEXT,
                home_facility_id INTEGER,
                preferred_days TEXT,
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
                scheduled_times TEXT,  -- JSON array of time strings ["09:00", "12:00", "15:00"]
                status TEXT NOT NULL DEFAULT 'unscheduled',
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (home_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (visitor_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE
            );
    
            CREATE INDEX IF NOT EXISTS idx_matches_league_id ON matches(league_id);
            CREATE INDEX IF NOT EXISTS idx_matches_facility_date ON matches(facility_id, date);
            CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
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
        self.match_manager = SQLMatchManager(self.cursor, self)
        self.scheduling_manager = SQLSchedulingManager(self.cursor, self)
    
    # ========== Connection Management ==========
    
    def connect(self) -> bool:
        """Establish database connection"""
        if not self.conn:
            self._initialize_schema()
            self._initialize_managers()
        return True
    
    def disconnect(self) -> bool:
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
                self.conn = None
                self.cursor = None
            except sqlite3.Error:
                pass
        return True

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
        return self.disconnect()

    def __del__(self):
        """Ensure database connection is properly closed"""
        return self.disconnect()

    # ========== Team Management ==========
    
    def add_team(self, team: Team) -> bool:
        return self.team_manager.add_team(team)
    
    def get_team(self, team_id: int) -> Optional[Team]:
        return self.team_manager.get_team(team_id)
    
    def list_teams(self, league: Optional[League] = None) -> List[Team]:
        league_id = league.id if league else None
        return self.team_manager.list_teams(league_id)

    def update_team(self, team: Team) -> bool:
        return self.team_manager.update_team(team)

    def delete_team(self, team: Team) -> bool:
        return self.team_manager.delete_team(team.id)

    # ========== League Management ==========
    
    def add_league(self, league: League) -> bool:
        return self.league_manager.add_league(league)
    
    def get_league(self, league_id: int) -> Optional[League]:
        return self.league_manager.get_league(league_id)
    
    def list_leagues(self) -> List[League]:
        return self.league_manager.list_leagues()

    def update_league(self, league: League) -> bool:
        return self.league_manager.update_league(league)

    def delete_league(self, league: League) -> bool:
        return self.league_manager.delete_league(league.id)

    # ========== Facility Management ==========
    
    def add_facility(self, facility: Facility) -> bool:
        return self.facility_manager.add_facility(facility)
    
    def get_facility(self, facility_id: int) -> Optional[Facility]:
        return self.facility_manager.get_facility(facility_id)
    
    def list_facilities(self) -> List[Facility]:
        return self.facility_manager.list_facilities()

    def update_facility(self, facility: Facility) -> bool:
        return self.facility_manager.update_facility(facility)

    def delete_facility(self, facility: Facility) -> bool:
        return self.facility_manager.delete_facility(facility.id)

    def get_facility_availability(self, facility: Facility, date: str) -> Dict[str, Any]:
        return self.facility_manager.get_facility_availability(facility.id, date)

    def get_available_dates(self, facility: Facility, num_lines: int, 
                           allow_split_lines: bool = False, 
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           max_dates: int = 50) -> List[str]:
        """
        Get available dates for a facility that can accommodate the required number of lines
        
        Args:
            facility: Facility object to check availability for
            num_lines: Number of lines (courts) needed
            allow_split_lines: Whether lines can be split across different time slots
            start_date: Start date for search (YYYY-MM-DD format). If None, uses today's date
            end_date: End date for search (YYYY-MM-DD format). If None, searches 16 weeks from start
            max_dates: Maximum number of dates to return
            
        Returns:
            List of available date strings in YYYY-MM-DD format, ordered by preference
        """
        return self.facility_manager.get_available_dates(
            facility, num_lines, allow_split_lines, start_date, end_date, max_dates
        )

    # ========== Match Management ==========
    
    def add_match(self, match: Match) -> bool:
        return self.match_manager.add_match(match)
    
    def get_match(self, match_id: int) -> Optional[Match]:
        return self.match_manager.get_match(match_id)

    def list_matches(self, 
                     facility: Optional['Facility'] = None,
                     league: Optional['League'] = None,
                     team: Optional['Team'] = None,
                    match_type: Optional['MatchType'] = MatchType.ALL) -> List[Match]:
        return self.match_manager.list_matches(facility=facility,
                                               league=league,
                                               team=team,
                                               match_type=match_type)

    def update_match(self, match: Match) -> bool:
        return self.match_manager.update_match(match)

    def delete_match(self, match: Match) -> bool:
        return self.match_manager.delete_match(match.id)

    def get_matches_on_date(self, date: str) -> List[Match]:
        return self.match_manager.get_matches_on_date(date)

    # ========== Match Scheduling Operations ==========
    
    def schedule_match_all_lines_same_time(self, match: Match, 
                                           date: str, time: str, 
                                           facility: Optional[Facility] = None) -> bool:
        facility_to_use = facility or match.home_team.home_facility
        return self.match_manager.schedule_match_all_lines_same_time(
            match, facility_to_use, date, time
        )
    
    def schedule_match_sequential_times(self, match: Match, 
                                        date: str, start_time: str, interval_minutes: int = 180, 
                                        facility: Optional[Facility] = None) -> bool:
        facility_to_use = facility or match.home_team.home_facility
        return self.match_manager.schedule_match_sequential_times(
            match, facility_to_use, date, start_time, interval_minutes
        )


    def auto_schedule_matches(self, matches: List['Match']) -> Dict[str, Any]:
        return self.scheduling_manager.auto_schedule_matches(matches)

    def unschedule_match(self, match: Match) -> bool:
        return self.match_manager.unschedule_match(match)
    
    def check_time_availability(self, facility: Facility, date: str, time: str, courts_needed: int = 1) -> bool:
        return self.match_manager.check_time_availability(facility, date, time, courts_needed)
    
    def get_available_times_at_facility(self, facility: Facility, date: str, courts_needed: int = 1) -> List[str]:
        return self.match_manager.get_available_times_at_facility(facility, date, courts_needed)

    # ========== Advanced Scheduling Operations ==========
    
    def get_team_conflicts(self, team: Team, date: str, time: str, duration_hours: int = 3) -> List[Dict]:
        return self.scheduling_manager.get_team_conflicts(team.id, date, time, duration_hours)

    def get_facility_conflicts(self, facility: Facility, date: str, time: str, duration_hours: int = 3, 
                             exclude_match_id: Optional[int] = None) -> List[Dict]:
        return self.scheduling_manager.get_facility_conflicts(
            facility.id, date, time, duration_hours, exclude_match_id
        )

    def get_scheduling_summary(self, league: Optional[League] = None) -> Dict[str, Any]:
        league_id = league.id if league else None
        return self.scheduling_manager.get_scheduling_summary(league_id)

    # ========== Statistics and Reporting ==========
    
    def get_match_statistics(self, league: Optional[League] = None) -> Dict[str, Any]:
        league_id = league.id if league else None
        return self.match_manager.get_match_statistics(league_id)
    
    def get_facility_usage_report(self, facility: Facility, start_date: str, end_date: str) -> Dict[str, Any]:
        return self.match_manager.get_facility_usage_report(facility, start_date, end_date)
    
    def get_scheduling_conflicts(self, facility: Facility, date: str) -> List[Dict[str, Any]]:
        return self.match_manager.get_scheduling_conflicts(facility, date)

    # ========== Import/Export Methods ==========
    
    def export_to_yaml(self, filename: str) -> bool:
        """Export database to YAML file"""
        try:
            data = {
                'leagues': [league.to_dict() if hasattr(league, 'to_dict') else league.__dict__ for league in self.list_leagues()],
                'facilities': [facility.to_yaml_dict() for facility in self.list_facilities()],
                'teams': [team.to_dict() if hasattr(team, 'to_dict') else team.__dict__ for team in self.list_teams()],
                'matches': [match.to_dict() for match in self.list_matches(include_unscheduled=True)]
            }
            
            with open(filename, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise RuntimeError(f"Failed to export to YAML: {e}")
        return True

    def import_from_yaml(self, filename: str) -> bool:
        """Import data from YAML file with proper object reference resolution"""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"YAML file not found: {filename}")
        
        try:
            with open(filename, 'r') as f:
                data = yaml.safe_load(f)
            
            # Import in dependency order: leagues -> facilities -> teams -> matches
            for table, records in data.items():
                if not isinstance(records, list):
                    continue
                
                for i, record in enumerate(records):
                    try:
                        obj = None
                        if table == "leagues":
                            obj = League(**record)
                            self.add_league(obj)
                        elif table == "facilities":
                            obj = Facility.from_yaml_dict(record)
                            self.add_facility(obj)
                        elif table == "teams":
                            # Resolve object references for Team
                            league = self.get_league(record['league_id'])
                            home_facility = self.get_facility(record['home_facility_id'])
                            
                            if not league:
                                raise ValueError(f"League with ID {record['league_id']} not found")
                            if not home_facility:
                                raise ValueError(f"Facility with ID {record['home_facility_id']} not found")
                            
                            team_data = record.copy()
                            team_data['league'] = league
                            team_data['home_facility'] = home_facility
                            # Remove ID fields since we're passing objects
                            team_data.pop('league_id', None)
                            team_data.pop('home_facility_id', None)
                            
                            obj = Team(**team_data)
                            self.add_team(obj)
                        elif table == "matches":
                            # Resolve object references for Match
                            league = self.get_league(record['league_id'])
                            home_team = self.get_team(record['home_team_id'])
                            visitor_team = self.get_team(record['visitor_team_id'])
                            facility = None
                            if record.get('facility_id'):
                                facility = self.get_facility(record['facility_id'])
                            
                            if not all([league, home_team, visitor_team]):
                                raise ValueError(f"Missing references for match {record.get('id', 'Unknown')}")
                            
                            match_data = {
                                'id': record['id'],
                                'league': league,
                                'home_team': home_team,
                                'visitor_team': visitor_team,
                                'facility': facility,
                                'date': record.get('date'),
                                'scheduled_times': record.get('scheduled_times', [])
                            }
                            
                            obj = Match(**match_data)
                            self.add_match(obj)
                            
                    except Exception as e:
                        raise ValueError(f"Failed to process record {i} in table '{table}': {e}")
    
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to import from YAML: {e}")
        return True

    # ========== USTA Constants ==========
    
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
    
    # Test get_available_dates if we have facilities
    facilities = db.list_facilities()
    if facilities:
        facility = facilities[0]
        print(f"✓ Testing get_available_dates for {facility.name}")
        
        # Test with 3 lines, no split lines allowed
        available_dates = db.get_available_dates(facility, 3, allow_split_lines=False, max_dates=10)
        print(f"✓ Found {len(available_dates)} available dates (no split lines)")
        if available_dates:
            print(f"✓ Sample dates: {available_dates[:3]}")
        
        # Test with split lines allowed
        available_dates_split = db.get_available_dates(facility, 3, allow_split_lines=True, max_dates=10)
        print(f"✓ Found {len(available_dates_split)} available dates (split lines allowed)")
        if available_dates_split:
            print(f"✓ Sample dates: {available_dates_split[:3]}")
    
    db.disconnect()
    print("✓ Database disconnected successfully")