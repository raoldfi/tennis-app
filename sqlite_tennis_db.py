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

"""
Clean YAML Import/Export Implementation for SQLiteTennisDB
No backward compatibility - integrated directly into the class
"""

import yaml
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class YAMLImportExportMixin:
    """Mixin class providing consistent YAML import/export functionality"""
    
    def export_to_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Export all database entities to YAML file
        
        Args:
            filename: Path to YAML file to create
            
        Returns:
            Dictionary with export statistics
            
        Raises:
            RuntimeError: If export fails
        """
        try:
            logger.info(f"Starting YAML export to {filename}")
            start_time = datetime.now()
            
            # Collect all data in dependency order
            export_data = {
                'metadata': {
                    'export_timestamp': start_time.isoformat(),
                    'format_version': '1.0'
                }
            }
            
            stats = {'exported': 0, 'errors': []}
            
            # 1. Export leagues (no dependencies)
            logger.debug("Exporting leagues...")
            leagues = self.list_leagues()
            export_data['leagues'] = [self._export_league(league) for league in leagues]
            stats['leagues'] = len(export_data['leagues'])
            stats['exported'] += len(export_data['leagues'])
            
            # 2. Export facilities (no dependencies)
            logger.debug("Exporting facilities...")
            facilities = self.list_facilities()
            export_data['facilities'] = [self._export_facility(facility) for facility in facilities]
            stats['facilities'] = len(export_data['facilities'])
            stats['exported'] += len(export_data['facilities'])
            
            # 3. Export teams (depends on leagues and facilities)
            logger.debug("Exporting teams...")
            teams = self.list_teams()
            export_data['teams'] = [self._export_team(team) for team in teams]
            stats['teams'] = len(export_data['teams'])
            stats['exported'] += len(export_data['teams'])
            
            # 4. Export matches (depends on all above)
            logger.debug("Exporting matches...")
            from usta_match import MatchType
            matches = self.list_matches(match_type=MatchType.ALL)
            export_data['matches'] = [self._export_match(match) for match in matches]
            stats['matches'] = len(export_data['matches'])
            stats['exported'] += len(export_data['matches'])
            
            # Write YAML file
            self._write_yaml_file(filename, export_data)
            
            # Calculate duration and finalize stats
            duration = (datetime.now() - start_time).total_seconds()
            stats.update({
                'filename': filename,
                'duration_seconds': round(duration, 2),
                'timestamp': start_time.isoformat()
            })
            
            logger.info(f"Export completed: {stats['exported']} total records in {duration:.2f}s")
            return stats
            
        except Exception as e:
            error_msg = f"YAML export failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    
    def import_from_yaml(self, filename: str, *, 
                        skip_existing: bool = True,
                        validate_only: bool = False) -> Dict[str, Any]:
        """
        Import entities from YAML file
        
        Args:
            filename: Path to YAML file to import
            skip_existing: If True, skip records that already exist (by ID)
            validate_only: If True, only validate without importing
            
        Returns:
            Dictionary with detailed import statistics
            
        Raises:
            FileNotFoundError: If YAML file doesn't exist
            ValueError: If YAML format/data is invalid
            RuntimeError: If import fails
        """
        self._validate_yaml_file(filename)
        
        try:
            logger.info(f"Starting YAML import from {filename}")
            start_time = datetime.now()
            
            # Load and validate YAML structure
            data = self._load_yaml_file(filename)
            self._validate_yaml_structure(data)
            
            # Initialize statistics
            stats = {
                'filename': filename,
                'timestamp': start_time.isoformat(),
                'skip_existing': skip_existing,
                'validate_only': validate_only,
                'leagues': {'processed': 0, 'imported': 0, 'skipped': 0, 'errors': []},
                'facilities': {'processed': 0, 'imported': 0, 'skipped': 0, 'errors': []},
                'teams': {'processed': 0, 'imported': 0, 'skipped': 0, 'errors': []},
                'matches': {'processed': 0, 'imported': 0, 'skipped': 0, 'errors': []},
                'total_processed': 0,
                'total_imported': 0,
                'total_skipped': 0,
                'total_errors': 0
            }
            
            # Import in dependency order
            if not validate_only:
                self._import_leagues(data.get('leagues', []), stats, skip_existing)
                self._import_facilities(data.get('facilities', []), stats, skip_existing)
                self._import_teams(data.get('teams', []), stats, skip_existing)
                self._import_matches(data.get('matches', []), stats, skip_existing)
            else:
                # Just validate structure without importing
                self._validate_leagues(data.get('leagues', []), stats)
                self._validate_facilities(data.get('facilities', []), stats)
                self._validate_teams(data.get('teams', []), stats)
                self._validate_matches(data.get('matches', []), stats)
            
            # Finalize statistics
            for entity_type in ['leagues', 'facilities', 'teams', 'matches']:
                entity_stats = stats[entity_type]
                stats['total_processed'] += entity_stats['processed']
                stats['total_imported'] += entity_stats['imported']
                stats['total_skipped'] += entity_stats['skipped']
                stats['total_errors'] += len(entity_stats['errors'])
            
            duration = (datetime.now() - start_time).total_seconds()
            stats['duration_seconds'] = round(duration, 2)
            
            action = "validated" if validate_only else "imported"
            logger.info(f"YAML {action}: {stats['total_processed']} processed, "
                       f"{stats['total_imported']} imported, {stats['total_errors']} errors")
            
            return stats
            
        except Exception as e:
            error_msg = f"YAML import failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    # ========== Export Helper Methods ==========
    
    def _export_league(self, league) -> Dict[str, Any]:
        """Export single league to dictionary"""
        return league.to_dict()
    
    def _export_facility(self, facility) -> Dict[str, Any]:
        """Export single facility to dictionary"""
        return facility.to_yaml_dict()
    
    def _export_team(self, team) -> Dict[str, Any]:
        """Export single team to dictionary"""
        return team.to_dict()
    
    def _export_match(self, match) -> Dict[str, Any]:
        """Export single match to dictionary"""
        return match.to_dict()
    
    def _write_yaml_file(self, filename: str, data: Dict[str, Any]) -> None:
        """Write data to YAML file with consistent formatting"""
        with open(filename, 'w', encoding='utf-8') as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                indent=2,
                width=120,
                default_style=None
            )
    
    # ========== Import Helper Methods ==========
    
    def _validate_yaml_file(self, filename: str) -> None:
        """Validate YAML file exists and is readable"""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"YAML file not found: {filename}")
        if not os.access(filename, os.R_OK):
            raise PermissionError(f"Cannot read YAML file: {filename}")
    
    def _load_yaml_file(self, filename: str) -> Dict[str, Any]:
        """Load and parse YAML file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                raise ValueError("YAML file must contain a dictionary at root level")
            
            return data
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {e}") from e
    
    def _validate_yaml_structure(self, data: Dict[str, Any]) -> None:
        """Validate basic YAML structure"""
        expected_sections = ['leagues', 'facilities', 'teams', 'matches']
        
        for section in data:
            if section not in expected_sections and section != 'metadata':
                logger.warning(f"Unexpected section in YAML: {section}")
        
        for section in expected_sections:
            if section in data and not isinstance(data[section], list):
                raise ValueError(f"Section '{section}' must be a list")
    
    def _import_leagues(self, leagues_data: List[Dict], stats: Dict, skip_existing: bool) -> None:
        """Import leagues from YAML data"""
        from usta_league import League
        
        for i, record in enumerate(leagues_data):
            stats['leagues']['processed'] += 1
            
            try:
                self._validate_required_fields(record, ['id', 'name', 'year', 'section', 'region', 'age_group', 'division'], 'league', i)
                
                # Check if exists
                if skip_existing and self.get_league(record['id']):
                    stats['leagues']['skipped'] += 1
                    continue
                
                league = League(**record)
                
                if self.add_league(league):
                    stats['leagues']['imported'] += 1
                    logger.debug(f"Imported league: {league.name}")
                else:
                    raise RuntimeError("Failed to add to database")
                    
            except Exception as e:
                error_msg = f"League record {i} (ID: {record.get('id', 'Unknown')}): {str(e)}"
                stats['leagues']['errors'].append(error_msg)
                logger.error(error_msg)
    
    def _import_facilities(self, facilities_data: List[Dict], stats: Dict, skip_existing: bool) -> None:
        """Import facilities from YAML data"""
        from usta_facility import Facility
        
        for i, record in enumerate(facilities_data):
            stats['facilities']['processed'] += 1
            
            try:
                self._validate_required_fields(record, ['id', 'name'], 'facility', i)
                
                # Check if exists
                if skip_existing and self.get_facility(record['id']):
                    stats['facilities']['skipped'] += 1
                    continue
                
                facility = Facility.from_yaml_dict(record)
                
                if self.add_facility(facility):
                    stats['facilities']['imported'] += 1
                    logger.debug(f"Imported facility: {facility.name}")
                else:
                    raise RuntimeError("Failed to add to database")
                    
            except Exception as e:
                error_msg = f"Facility record {i} (ID: {record.get('id', 'Unknown')}): {str(e)}"
                stats['facilities']['errors'].append(error_msg)
                logger.error(error_msg)
    
    def _import_teams(self, teams_data: List[Dict], stats: Dict, skip_existing: bool) -> None:
        """Import teams from YAML data"""
        from usta_team import Team
        
        for i, record in enumerate(teams_data):
            stats['teams']['processed'] += 1
            
            try:
                self._validate_required_fields(record, ['id', 'name', 'league_id', 'home_facility_id'], 'team', i)
                
                # Check if exists
                if skip_existing and self.get_team(record['id']):
                    stats['teams']['skipped'] += 1
                    continue
                
                # Resolve references
                league = self.get_league(record['league_id'])
                if not league:
                    raise ValueError(f"League ID {record['league_id']} not found")
                
                home_facility = self.get_facility(record['home_facility_id'])
                if not home_facility:
                    raise ValueError(f"Home facility ID {record['home_facility_id']} not found")
                
                # Create team with object references
                team_data = record.copy()
                team_data.update({
                    'league': league,
                    'home_facility': home_facility
                })
                team_data.pop('league_id')
                team_data.pop('home_facility_id')
                
                team = Team(**team_data)
                
                if self.add_team(team):
                    stats['teams']['imported'] += 1
                    logger.debug(f"Imported team: {team.name}")
                else:
                    raise RuntimeError("Failed to add to database")
                    
            except Exception as e:
                error_msg = f"Team record {i} (ID: {record.get('id', 'Unknown')}): {str(e)}"
                stats['teams']['errors'].append(error_msg)
                logger.error(error_msg)
    
    def _import_matches(self, matches_data: List[Dict], stats: Dict, skip_existing: bool) -> None:
        """Import matches from YAML data"""
        from usta_match import Match
        
        for i, record in enumerate(matches_data):
            stats['matches']['processed'] += 1
            
            try:
                self._validate_required_fields(record, ['id', 'league_id', 'home_team_id', 'visitor_team_id'], 'match', i)
                
                # Check if exists
                if skip_existing and self.get_match(record['id']):
                    stats['matches']['skipped'] += 1
                    continue
                
                # Resolve references
                league = self.get_league(record['league_id'])
                if not league:
                    raise ValueError(f"League ID {record['league_id']} not found")
                
                home_team = self.get_team(record['home_team_id'])
                if not home_team:
                    raise ValueError(f"Home team ID {record['home_team_id']} not found")
                
                visitor_team = self.get_team(record['visitor_team_id'])
                if not visitor_team:
                    raise ValueError(f"Visitor team ID {record['visitor_team_id']} not found")
                
                facility = None
                if record.get('facility_id'):
                    facility = self.get_facility(record['facility_id'])
                    # Don't fail if facility not found - just log warning
                    if not facility:
                        logger.warning(f"Facility ID {record['facility_id']} not found for match {record['id']}")
                
                # Create match with object references
                match_data = {
                    'id': record['id'],
                    'league': league,
                    'home_team': home_team,
                    'visitor_team': visitor_team,
                    'facility': facility,
                    'date': record.get('date'),
                    'scheduled_times': record.get('scheduled_times', [])
                }
                
                match = Match(**match_data)
                
                if self.add_match(match):
                    stats['matches']['imported'] += 1
                    logger.debug(f"Imported match: {match.id}")
                else:
                    raise RuntimeError("Failed to add to database")
                    
            except Exception as e:
                error_msg = f"Match record {i} (ID: {record.get('id', 'Unknown')}): {str(e)}"
                stats['matches']['errors'].append(error_msg)
                logger.error(error_msg)
    
    # ========== Validation Helper Methods ==========
    
    def _validate_required_fields(self, record: Dict, required_fields: List[str], 
                                 entity_type: str, record_index: int) -> None:
        """Validate that record contains all required fields"""
        if not isinstance(record, dict):
            raise ValueError(f"{entity_type.title()} record {record_index} must be a dictionary")
        
        missing_fields = [field for field in required_fields if field not in record]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
    
    def _validate_leagues(self, leagues_data: List[Dict], stats: Dict) -> None:
        """Validate league records without importing"""
        for i, record in enumerate(leagues_data):
            stats['leagues']['processed'] += 1
            try:
                self._validate_required_fields(record, ['id', 'name', 'year', 'section', 'region', 'age_group', 'division'], 'league', i)
                # Additional validation could go here
            except Exception as e:
                stats['leagues']['errors'].append(f"League record {i}: {str(e)}")
    
    def _validate_facilities(self, facilities_data: List[Dict], stats: Dict) -> None:
        """Validate facility records without importing"""
        for i, record in enumerate(facilities_data):
            stats['facilities']['processed'] += 1
            try:
                self._validate_required_fields(record, ['id', 'name'], 'facility', i)
                # Additional validation could go here
            except Exception as e:
                stats['facilities']['errors'].append(f"Facility record {i}: {str(e)}")
    
    def _validate_teams(self, teams_data: List[Dict], stats: Dict) -> None:
        """Validate team records without importing"""
        for i, record in enumerate(teams_data):
            stats['teams']['processed'] += 1
            try:
                self._validate_required_fields(record, ['id', 'name', 'league_id', 'home_facility_id'], 'team', i)
                # Additional validation could go here
            except Exception as e:
                stats['teams']['errors'].append(f"Team record {i}: {str(e)}")
    
    def _validate_matches(self, matches_data: List[Dict], stats: Dict) -> None:
        """Validate match records without importing"""
        for i, record in enumerate(matches_data):
            stats['matches']['processed'] += 1
            try:
                self._validate_required_fields(record, ['id', 'league_id', 'home_team_id', 'visitor_team_id'], 'match', i)
                # Additional validation could go here
            except Exception as e:
                stats['matches']['errors'].append(f"Match record {i}: {str(e)}")


# Update the SQLiteTennisDB class to inherit from the mixin
class SQLiteTennisDB(YAMLImportExportMixin, TennisDBInterface):
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