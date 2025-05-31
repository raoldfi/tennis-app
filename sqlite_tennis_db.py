from tennis_db import TennisDB
from usta import League, Team, Match, Facility, WeeklySchedule, DaySchedule, TimeSlot
import sqlite3
import argparse
import json
import yaml
import os
import sys
from typing import List, Dict, Optional
from datetime import date

# Predefined USTA categories used for validation
from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS


# SQLite implementation of the TennisDB
class SQLiteTennisDB(TennisDB):
    def _dictify(self, row) -> dict:
        return dict(row) if row else {}

    def __init__(self, db_path: str):
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("Database path must be a non-empty string")
        
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        try:
            self._initialize_schema()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database: {e}")

    # Updated schema initialization method for SQLiteTennisDB class
    def _initialize_schema(self):
        try:
            # Add check_same_thread=False to allow multi-threading
            # Add timeout to prevent deadlocks
            self.conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=20.0,
                isolation_level=None  # Autocommit mode for better concurrency
            )
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Enable foreign key constraints
            self.cursor.execute("PRAGMA foreign_keys = ON")
            
            # Enable WAL mode for better concurrent access
            self.cursor.execute("PRAGMA journal_mode = WAL")
            
            # Set synchronous mode for better performance
            self.cursor.execute("PRAGMA synchronous = NORMAL")
            
            # Set busy timeout for concurrent access
            self.cursor.execute("PRAGMA busy_timeout = 30000")
            
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT
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
                name TEXT NOT NULL,
                id INTEGER PRIMARY KEY,
                league_id INTEGER NOT NULL,
                home_facility_id INTEGER NOT NULL,
                captain TEXT,
                preferred_days TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (home_facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE
            );
    
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                league_id INTEGER NOT NULL,
                home_team_id INTEGER NOT NULL,
                visitor_team_id INTEGER NOT NULL,
                facility_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (home_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (visitor_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE
            );
            """)
            
            # Migration: Add new league columns if they don't exist
            new_league_columns = [
                ('num_lines_per_match', 'INTEGER NOT NULL DEFAULT 3'),
                ('num_matches', 'INTEGER NOT NULL DEFAULT 10'),
                ('allow_split_lines', 'BOOLEAN NOT NULL DEFAULT 0'),
                ('preferred_days', 'TEXT NOT NULL DEFAULT ""'),
                ('backup_days', 'TEXT NOT NULL DEFAULT ""'),
                ('start_date', 'TEXT'),
                ('end_date', 'TEXT')
            ]
            
            for column_name, column_def in new_league_columns:
                try:
                    self.cursor.execute(f"SELECT {column_name} FROM leagues LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, add it
                    print(f"Adding {column_name} column to leagues table...")
                    self.cursor.execute(f"ALTER TABLE leagues ADD COLUMN {column_name} {column_def}")
                    print(f"Migration for {column_name} completed.")
            
            # Migration: Add preferred_days column to teams table if it doesn't exist
            try:
                self.cursor.execute("SELECT preferred_days FROM teams LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                print("Adding preferred_days column to teams table...")
                self.cursor.execute("ALTER TABLE teams ADD COLUMN preferred_days TEXT NOT NULL DEFAULT ''")
                print("Migration for teams.preferred_days completed.")
            
            # Note: We're using autocommit mode, so no explicit commit needed
        except sqlite3.Error as e:
            raise RuntimeError(f"Database initialization failed: {e}")

    
    
    def close(self):
        """Explicitly close the database connection"""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
                self.conn = None
                self.cursor = None
            except sqlite3.Error:
                pass  # Ignore errors during cleanup

    def __del__(self):
        """Ensure database connection is properly closed"""
        self.close()

    # Load and insert data from a YAML file into specified table
    def load_yaml(self, table: str, yaml_path: str) -> None:
        if not isinstance(table, str) or table not in ["teams", "leagues", "matches", "facilities"]:
            raise ValueError(f"Invalid table name: {table}. Must be one of: teams, leagues, matches, facilities")
        
        if not isinstance(yaml_path, str) or not yaml_path.strip():
            raise ValueError("YAML path must be a non-empty string")
        
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")
        
        print(f"DEBUG: Loading {table} from {yaml_path}")
        
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {yaml_path}: {e}")
        except IOError as e:
            raise IOError(f"Failed to read YAML file {yaml_path}: {e}")
        
        print(f"DEBUG: YAML data loaded: {data}")
        
        if not isinstance(data, dict):
            raise ValueError(f"YAML file must contain a dictionary, got: {type(data)}")
        
        records = data.get(table, [])
        if not isinstance(records, list):
            raise ValueError(f"Table '{table}' in YAML must be a list, got: {type(records)}")

        print(f"DEBUG: Found {len(records)} records in '{table}' section")

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
            
            print(f"DEBUG: Processing record {i}: {record}")
            
            try:
                # Convert dict to appropriate dataclass
                if table == "teams":
                    # For teams, we need to get the league object first
                    if 'league_id' not in record:
                        raise ValueError(f"Team record {i} missing required 'league_id' field")
                    
                    league_id = record.pop('league_id')  # Remove league_id from record
                    league = self.get_league(league_id)
                    if not league:
                        raise ValueError(f"League with ID {league_id} not found for team record {i}")
                    record['league'] = league
                    obj = Team(**record)
                elif table == "leagues":
                    obj = League(**record)
                elif table == "matches":
                    obj = Match(**record)
                elif table == "facilities":
                    print(f"DEBUG: Creating Facility object with: {record}")
                    # For facilities, use the from_yaml_dict method to handle complex structure
                    obj = Facility.from_yaml_dict(record)
                    print(f"DEBUG: Created Facility: {obj}")
                
                print(f"DEBUG: Calling {insert_fn.__name__} with {obj}")
                insert_fn(obj)
                print(f"DEBUG: Successfully added record {i}")
                
            except Exception as e:
                print(f"DEBUG: Error processing record {i}: {e}")
                raise ValueError(f"Failed to process record {i} in table '{table}': {e}")
        
        print(f"DEBUG: Completed loading {len(records)} records")

    # Calculate pairings for teams in a league
    def calculate_pairings(self, league_id: int) -> List[tuple]:
        """
        Calculate pairings for all teams in a specified league
        
        Args:
            league_id: ID of the league to calculate pairings for
            
        Returns:
            List of tuples (home_team, visitor_team) representing all matches
            
        Raises:
            ValueError: If league doesn't exist or has insufficient teams
        """
        if not isinstance(league_id, int) or league_id <= 0:
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        # Get the league
        league = self.get_league(league_id)
        if not league:
            raise ValueError(f"League with ID {league_id} not found")
        
        # Get all teams in the league
        teams = self.list_teams(league_id=league_id)
        if len(teams) < 2:
            raise ValueError(f"League '{league.name}' has only {len(teams)} team(s). Need at least 2 teams to generate pairings.")
        
        # Use the league's calculate_pairings method
        try:
            pairings = league.calculate_pairings(teams)
            return pairings
        except Exception as e:
            raise ValueError(f"Failed to calculate pairings for league '{league.name}': {e}")

    # Insert a team into the database
    def add_team(self, team: Team) -> None:
        if not isinstance(team, Team):
            raise TypeError(f"Expected Team object, got: {type(team)}")
        
        try:
            # Check if team ID already exists
            existing = self.get_team(team.id)
            if existing:
                raise ValueError(f"Team with ID {team.id} already exists")
            
            # Verify league exists
            if not self.get_league(team.league.id):
                raise ValueError(f"League with ID {team.league.id} does not exist")
            
            # Verify facility exists
            if not self.get_facility(team.home_facility_id):
                raise ValueError(f"Facility with ID {team.home_facility_id} does not exist")
            
            # Convert preferred_days list to comma-separated string for storage
            preferred_days_str = ','.join(team.preferred_days)
            
            self.cursor.execute("""
                INSERT INTO teams (id, name, league_id, home_facility_id, captain, preferred_days)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                team.id,
                team.name,
                team.league.id,
                team.home_facility_id,
                team.captain,
                preferred_days_str
            ))
            # No explicit commit needed in autocommit mode
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding team: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding team: {e}")
    
    # Updated get_team method
    def get_team(self, team_id: int) -> Optional[Team]:
        if not isinstance(team_id, int) or team_id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {team_id}")
        
        try:
            self.cursor.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            team_data = self._dictify(row)
            # Get the league object
            league = self.get_league(team_data['league_id'])
            if not league:
                raise RuntimeError(f"Data integrity error: League with ID {team_data['league_id']} not found for team {team_id}")
            
            # Convert comma-separated string back to list
            preferred_days = []
            if team_data.get('preferred_days'):
                preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
            
            # Remove league_id and preferred_days string, add league object and preferred_days list
            team_data.pop('league_id')
            team_data.pop('preferred_days', None)
            team_data['league'] = league
            team_data['preferred_days'] = preferred_days
            
            return Team(**team_data)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving team {team_id}: {e}")
    
    # Updated list_teams method
    def list_teams(self, league_id: Optional[int] = None) -> List[Team]:
        if league_id is not None and (not isinstance(league_id, int) or league_id <= 0):
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            if league_id:
                # Verify league exists
                if not self.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                self.cursor.execute("SELECT * FROM teams WHERE league_id = ?", (league_id,))
            else:
                self.cursor.execute("SELECT * FROM teams")
            
            teams = []
            for row in self.cursor.fetchall():
                team_data = self._dictify(row)
                # Get the league object
                league = self.get_league(team_data['league_id'])
                if not league:
                    raise RuntimeError(f"Data integrity error: League with ID {team_data['league_id']} not found")
                
                # Convert comma-separated string back to list
                preferred_days = []
                if team_data.get('preferred_days'):
                    preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
                
                # Remove league_id and preferred_days string, add league object and preferred_days list
                team_data.pop('league_id')
                team_data.pop('preferred_days', None)
                team_data['league'] = league
                team_data['preferred_days'] = preferred_days
                
                teams.append(Team(**team_data))
            return teams
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing teams: {e}")

    # Updated add_league method
    def add_league(self, league: League) -> None:
        if not isinstance(league, League):
            raise TypeError(f"Expected League object, got: {type(league)}")
        
        try:
            # Check if league ID already exists
            existing = self.get_league(league.id)
            if existing:
                raise ValueError(f"League with ID {league.id} already exists")
            
            # Convert day lists to comma-separated strings for storage
            preferred_days_str = ','.join(league.preferred_days)
            backup_days_str = ','.join(league.backup_days)
            
            self.cursor.execute("""
                INSERT INTO leagues (id, year, section, region, age_group, division, name, 
                                   num_lines_per_match, num_matches, allow_split_lines, 
                                   preferred_days, backup_days, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                league.id,
                league.year,
                league.section,
                league.region,
                league.age_group,
                league.division,
                league.name,
                league.num_lines_per_match,
                league.num_matches,
                league.allow_split_lines,
                preferred_days_str,
                backup_days_str,
                league.start_date,
                league.end_date
            ))
            # No explicit commit needed in autocommit mode
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding league: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding league: {e}")
    
    # Updated get_league method
    def get_league(self, league_id: int) -> Optional[League]:
        if not isinstance(league_id, int) or league_id <= 0:
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            self.cursor.execute("SELECT * FROM leagues WHERE id = ?", (league_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            league_data = self._dictify(row)
            
            # Convert comma-separated strings back to lists
            preferred_days = []
            if league_data.get('preferred_days'):
                preferred_days = [day.strip() for day in league_data['preferred_days'].split(',') if day.strip()]
            
            backup_days = []
            if league_data.get('backup_days'):
                backup_days = [day.strip() for day in league_data['backup_days'].split(',') if day.strip()]
            
            # Handle potential missing columns (for backward compatibility)
            league_data.setdefault('num_matches', 10)
            league_data.setdefault('allow_split_lines', False)
            league_data.setdefault('start_date', None)
            league_data.setdefault('end_date', None)
            
            # Remove the string versions and add the list versions
            league_data.pop('preferred_days', None)
            league_data.pop('backup_days', None)
            league_data['preferred_days'] = preferred_days
            league_data['backup_days'] = backup_days
            
            # Convert allow_split_lines from integer to boolean
            league_data['allow_split_lines'] = bool(league_data.get('allow_split_lines', 0))
            
            return League(**league_data)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving league {league_id}: {e}")
    
    # Updated list_leagues method
    def list_leagues(self) -> List[League]:
        try:
            self.cursor.execute("SELECT * FROM leagues")
            leagues = []
            
            for row in self.cursor.fetchall():
                league_data = self._dictify(row)
                
                # Convert comma-separated strings back to lists
                preferred_days = []
                if league_data.get('preferred_days'):
                    preferred_days = [day.strip() for day in league_data['preferred_days'].split(',') if day.strip()]
                
                backup_days = []
                if league_data.get('backup_days'):
                    backup_days = [day.strip() for day in league_data['backup_days'].split(',') if day.strip()]
                
                # Handle potential missing columns (for backward compatibility)
                league_data.setdefault('num_matches', 10)
                league_data.setdefault('allow_split_lines', False)
                league_data.setdefault('start_date', None)
                league_data.setdefault('end_date', None)
                
                # Remove the string versions and add the list versions
                league_data.pop('preferred_days', None)
                league_data.pop('backup_days', None)
                league_data['preferred_days'] = preferred_days
                league_data['backup_days'] = backup_days
                
                # Convert allow_split_lines from integer to boolean
                league_data['allow_split_lines'] = bool(league_data.get('allow_split_lines', 0))
                
                leagues.append(League(**league_data))
            
            return leagues
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing leagues: {e}")
    

    def add_match(self, match: Match) -> None:
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        try:
            # Check if match ID already exists
            existing = self.get_match(match.id)
            if existing:
                raise ValueError(f"Match with ID {match.id} already exists")
            
            # Verify league exists
            if not self.get_league(match.league_id):
                raise ValueError(f"League with ID {match.league_id} does not exist")
            
            # Verify teams exist
            if not self.get_team(match.home_team_id):
                raise ValueError(f"Home team with ID {match.home_team_id} does not exist")
            if not self.get_team(match.visitor_team_id):
                raise ValueError(f"Visitor team with ID {match.visitor_team_id} does not exist")
            
            # Verify facility exists
            if not self.get_facility(match.facility_id):
                raise ValueError(f"Facility with ID {match.facility_id} does not exist")
            
            # Verify teams are in the same league
            home_team = self.get_team(match.home_team_id)
            visitor_team = self.get_team(match.visitor_team_id)
            if home_team.league.id != match.league_id:
                raise ValueError(f"Home team {match.home_team_id} is not in league {match.league_id}")
            if visitor_team.league.id != match.league_id:
                raise ValueError(f"Visitor team {match.visitor_team_id} is not in league {match.league_id}")
            
            self.cursor.execute("""
                INSERT INTO matches (id, league_id, home_team_id, visitor_team_id, facility_id, date, time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                match.id,
                match.league_id,
                match.home_team_id,
                match.visitor_team_id,
                match.facility_id,
                match.date,
                match.time
            ))
            # No explicit commit needed in autocommit mode
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding match: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding match: {e}")

    def get_match(self, match_id: int) -> Optional[Match]:
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            self.cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
            row = self.cursor.fetchone()
            return Match(**self._dictify(row)) if row else None
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")

    def list_matches(self, league_id: Optional[int] = None) -> List[Match]:
        if league_id is not None and (not isinstance(league_id, int) or league_id <= 0):
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            if league_id:
                # Verify league exists
                if not self.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                self.cursor.execute("SELECT * FROM matches WHERE league_id = ?", (league_id,))
            else:
                self.cursor.execute("SELECT * FROM matches")

            return [Match(**self._dictify(row)) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing matches: {e}")

    def add_facility(self, facility: Facility) -> None:
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            # Check if facility ID already exists
            existing = self.get_facility(facility.id)
            if existing:
                raise ValueError(f"Facility with ID {facility.id} already exists")
            
            # Insert basic facility info
            self.cursor.execute("""
                INSERT INTO facilities (id, name, location)
                VALUES (?, ?, ?)
            """, (
                facility.id,
                facility.name,
                facility.location
            ))
            
            # Insert schedule data
            self._insert_facility_schedule(facility.id, facility.schedule)
            
            # Insert unavailable dates
            self._insert_facility_unavailable_dates(facility.id, facility.unavailable_dates)
            
            # No explicit commit needed in autocommit mode
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding facility: {e}")

    def _insert_facility_schedule(self, facility_id: int, schedule: WeeklySchedule) -> None:
        """Insert facility schedule data into the database"""
        try:
            # Clear existing schedule data for this facility
            self.cursor.execute("DELETE FROM facility_schedules WHERE facility_id = ?", (facility_id,))
            
            # Insert schedule for each day
            for day_name, day_schedule in schedule.get_all_days().items():
                for time_slot in day_schedule.start_times:
                    self.cursor.execute("""
                        INSERT INTO facility_schedules (facility_id, day, time, available_courts)
                        VALUES (?, ?, ?, ?)
                    """, (facility_id, day_name, time_slot.time, time_slot.available_courts))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error inserting facility schedule: {e}")

    def _insert_facility_unavailable_dates(self, facility_id: int, unavailable_dates: List[str]) -> None:
        """Insert facility unavailable dates into the database"""
        try:
            # Clear existing unavailable dates for this facility
            self.cursor.execute("DELETE FROM facility_unavailable_dates WHERE facility_id = ?", (facility_id,))
            
            # Insert unavailable dates
            for date_str in unavailable_dates:
                self.cursor.execute("""
                    INSERT INTO facility_unavailable_dates (facility_id, date)
                    VALUES (?, ?)
                """, (facility_id, date_str))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error inserting facility unavailable dates: {e}")

    def get_facility(self, facility_id: int) -> Optional[Facility]:
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Get basic facility info
            self.cursor.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            facility_data = self._dictify(row)
            
            # Create basic facility
            facility = Facility(
                id=facility_data['id'],
                name=facility_data['name'],
                location=facility_data['location']
            )
            
            # Load schedule data
            facility.schedule = self._load_facility_schedule(facility_id)
            
            # Load unavailable dates
            facility.unavailable_dates = self._load_facility_unavailable_dates(facility_id)
            
            return facility
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving facility {facility_id}: {e}")

    def _load_facility_schedule(self, facility_id: int) -> WeeklySchedule:
        """Load facility schedule from the database"""
        try:
            self.cursor.execute("""
                SELECT day, time, available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? 
                ORDER BY day, time
            """, (facility_id,))
            
            schedule = WeeklySchedule()
            
            for row in self.cursor.fetchall():
                day_name = row['day']
                time_slot = TimeSlot(
                    time=row['time'],
                    available_courts=row['available_courts']
                )
                
                day_schedule = schedule.get_day_schedule(day_name)
                day_schedule.start_times.append(time_slot)
            
            return schedule
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error loading facility schedule: {e}")

    def _load_facility_unavailable_dates(self, facility_id: int) -> List[str]:
        """Load facility unavailable dates from the database"""
        try:
            self.cursor.execute("""
                SELECT date 
                FROM facility_unavailable_dates 
                WHERE facility_id = ? 
                ORDER BY date
            """, (facility_id,))
            
            return [row['date'] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error loading facility unavailable dates: {e}")

    def list_facilities(self) -> List[Facility]:
        try:
            self.cursor.execute("SELECT * FROM facilities")
            facilities = []
            
            for row in self.cursor.fetchall():
                facility_data = self._dictify(row)
                
                # Create basic facility
                facility = Facility(
                    id=facility_data['id'],
                    name=facility_data['name'],
                    location=facility_data['location']
                )
                
                # Load schedule and unavailable dates
                facility.schedule = self._load_facility_schedule(facility.id)
                facility.unavailable_dates = self._load_facility_unavailable_dates(facility.id)
                
                facilities.append(facility)
            
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing facilities: {e}")

    def update_facility(self, facility: Facility) -> None:
        """Update an existing facility"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            # Check if facility exists
            existing = self.get_facility(facility.id)
            if not existing:
                raise ValueError(f"Facility with ID {facility.id} does not exist")
            
            # Update basic facility info
            self.cursor.execute("""
                UPDATE facilities 
                SET name = ?, location = ?
                WHERE id = ?
            """, (facility.name, facility.location, facility.id))
            
            # Update schedule data
            self._insert_facility_schedule(facility.id, facility.schedule)
            
            # Update unavailable dates
            self._insert_facility_unavailable_dates(facility.id, facility.unavailable_dates)
            
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating facility: {e}")

    def delete_facility(self, facility_id: int) -> None:
        """Delete a facility and all its related data"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Check if facility exists
            existing = self.get_facility(facility_id)
            if not existing:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Check if facility is referenced by teams
            self.cursor.execute("SELECT COUNT(*) as count FROM teams WHERE home_facility_id = ?", (facility_id,))
            team_count = self.cursor.fetchone()['count']
            if team_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {team_count} team(s)")
            
            # Check if facility is referenced by matches
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE facility_id = ?", (facility_id,))
            match_count = self.cursor.fetchone()['count']
            if match_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {match_count} match(es)")
            
            # Delete related data (CASCADE will handle this automatically due to foreign key constraints)
            self.cursor.execute("DELETE FROM facilities WHERE id = ?", (facility_id,))
            
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error deleting facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting facility: {e}")

    # Additional methods for listing USTA constants
    def list_sections(self) -> List[str]:
        return USTA_SECTIONS.copy()  # Return a copy to prevent modification

    def list_regions(self) -> List[str]:
        return USTA_REGIONS.copy()

    def list_age_groups(self) -> List[str]:
        return USTA_AGE_GROUPS.copy()

    def list_divisions(self) -> List[str]:
        return USTA_DIVISIONS.copy()


# Command-line interface for interacting with the SQLiteTennisDB
def main():
    parser = argparse.ArgumentParser(
        description="Manage and explore a tennis scheduling database",
        epilog="""
EXAMPLES:

Database Creation:
  # Create a new database or connect to existing one
  python sqlite_tennis_db.py --db tennis.db

Loading Data:
  # Load facilities first (required for teams)
  python sqlite_tennis_db.py --db tennis.db load facilities --file facilities.yaml
  
  # Load leagues (required for teams)
  python sqlite_tennis_db.py --db tennis.db load leagues --file leagues.yaml
  
  # Load teams (requires facilities and leagues to exist)
  python sqlite_tennis_db.py --db tennis.db load teams --file teams.yaml
  
  # Load matches (requires teams, leagues, and facilities)
  python sqlite_tennis_db.py --db tennis.db load matches --file matches.yaml

Listing Data:
  # List all entities
  python sqlite_tennis_db.py --db tennis.db list facilities
  python sqlite_tennis_db.py --db tennis.db list leagues
  python sqlite_tennis_db.py --db tennis.db list teams
  python sqlite_tennis_db.py --db tennis.db list matches
  
  # List USTA constants
  python sqlite_tennis_db.py --db tennis.db list sections
  python sqlite_tennis_db.py --db tennis.db list regions
  python sqlite_tennis_db.py --db tennis.db list age-groups
  python sqlite_tennis_db.py --db tennis.db list divisions

Calculate Pairings:
  # Calculate team pairings for a specific league
  python sqlite_tennis_db.py --db tennis.db calculate-pairings --league-id 101
  python sqlite_tennis_db.py --db tennis.db calculate-pairings --league-id 205

Filtering Data:
  # List teams in a specific league
  python sqlite_tennis_db.py --db tennis.db list teams --league-id 101
  python sqlite_tennis_db.py --db tennis.db list teams --league-id 205
  
  # List matches in a specific league
  python sqlite_tennis_db.py --db tennis.db list matches --league-id 101
  python sqlite_tennis_db.py --db tennis.db list matches --league-id 205

YAML File Formats:

facilities.yaml:
  facilities:
    - id: 1
      name: "Tennis Center North"
      location: "123 Tennis Dr, Albuquerque, NM"
      schedule:
        Monday:
          start_times:
            - time: "18:00"
              available_courts: 12
        Tuesday:
          start_times:
            - time: "18:00"
              available_courts: 12
        Wednesday:
          start_times:
            - time: "18:00"
              available_courts: 12
        Thursday:
          start_times:
            - time: "18:00"
              available_courts: 12
        Friday:
          start_times: []
        Saturday:
          start_times:
            - time: "10:00"
              available_courts: 5
            - time: "12:00"
              available_courts: 12
            - time: "14:00"
              available_courts: 12
        Sunday:
          start_times:
            - time: "10:00"
              available_courts: 5
            - time: "12:00"
              available_courts: 12
            - time: "14:00"
              available_courts: 12
      unavailable_dates:
        - "2025-03-01"
        - "2025-03-02"
        - "2025-03-07"
        - "2025-03-08"
        - "2025-03-09"

leagues.yaml:
  leagues:
    - id: 101
      name: "2025 Adult 18+ 3.0 Women"
      year: 2025
      section: "Southwest"
      region: "Northern New Mexico"
      age_group: "18 & Over"
      division: "3.0 Women"
      num_lines_per_match: 3
    - id: 102
      name: "2025 Adult 18+ 4.0 Mixed"
      year: 2025
      section: "Southwest"
      region: "Northern New Mexico"
      age_group: "18 & Over"
      division: "8.0 Mixed"
      num_lines_per_match: 3

teams.yaml:
  teams:
    - id: 1001
      name: "Smith - Tennis Center North"
      league_id: 101
      home_facility_id: 1
      captain: "Jane Smith"
    - id: 1002
      name: "Johnson - Westside Club"
      league_id: 101
      home_facility_id: 2
      captain: "Mary Johnson"

matches.yaml:
  matches:
    - id: 2001
      league_id: 101
      home_team_id: 1001
      visitor_team_id: 1002
      facility_id: 1
      date: "2025-03-15"
      time: "10:00"

Common Workflows:
  # 1. Set up a new tennis database
  python sqlite_tennis_db.py --db tennis.db load facilities --file facilities.yaml
  python sqlite_tennis_db.py --db tennis.db load leagues --file leagues.yaml
  python sqlite_tennis_db.py --db tennis.db load teams --file teams.yaml
  python sqlite_tennis_db.py --db tennis.db load matches --file matches.yaml
  
  # 2. View all teams in a league
  python sqlite_tennis_db.py --db tennis.db list teams --league-id 101
  
  # 3. Calculate optimal pairings for teams in a league
  python sqlite_tennis_db.py --db tennis.db calculate-pairings --league-id 101
  
  # 4. Check what matches are scheduled for a league
  python sqlite_tennis_db.py --db tennis.db list matches --league-id 101
  
  # 5. Get valid USTA values for creating leagues
  python sqlite_tennis_db.py --db tennis.db list sections
  python sqlite_tennis_db.py --db tennis.db list divisions

Tips:
  - Load entities in dependency order: facilities → leagues → teams → matches
  - Use --league-id to filter teams by league
  - Use --league-id to filter matches by league
  - Use calculate-pairings to generate balanced match schedules for league teams
  - YAML files must follow the exact format shown above
  - All IDs must be positive integers
  - Dates must be in YYYY-MM-DD format
  - Times must be in HH:MM format (24-hour)
  - Schedule times follow the same HH:MM format
  - Unavailable dates use YYYY-MM-DD format
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add database argument as a required option
    parser.add_argument("--db", "--database", 
                       dest="db_path",
                       required=True,
                       help="Path to SQLite database file")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create the 'list' command parser
    list_parser = subparsers.add_parser("list", help="List entities from the database")
    list_parser.add_argument("table", 
                           choices=["teams", "leagues", "matches", "sections", "regions", "age-groups", "facilities", "divisions"], 
                           help="Type of entity to list")
    list_parser.add_argument("--league-id", 
                           type=int, 
                           help="Filter teams or matches by league ID")

    # Create the 'load' command parser  
    load_parser = subparsers.add_parser("load", help="Load entities from YAML file")
    load_parser.add_argument("table", 
                           choices=["teams", "leagues", "matches", "facilities"], 
                           help="Type of entity to load")
    load_parser.add_argument("--file", "-f",
                           dest="yaml_path",
                           required=True,
                           help="Path to the YAML file containing data")

    # Create the 'calculate-pairings' command parser
    pairings_parser = subparsers.add_parser("calculate-pairings", help="Calculate team pairings for a league")
    pairings_parser.add_argument("--league-id",
                               type=int,
                               required=True,
                               help="League ID to calculate pairings for")

    try:
        args = parser.parse_args()
        
        # Validate arguments
        if not args.db_path or not args.db_path.strip():
            print("Error: Database path cannot be empty", file=sys.stderr)
            sys.exit(1)
        
        # Initialize database connection
        try:
            db = SQLiteTennisDB(args.db_path)
        except Exception as e:
            print(f"Error: Failed to connect to database: {e}", file=sys.stderr)
            sys.exit(1)

        if args.command == "list":
            try:
                # Handle constant lists
                if args.table == "sections":
                    results = db.list_sections()
                elif args.table == "regions":
                    results = db.list_regions()
                elif args.table == "age-groups":
                    results = db.list_age_groups()
                elif args.table == "divisions":
                    results = db.list_divisions()
                else:
                    # Handle database tables
                    if args.table == "teams":
                        # Validate league_id if provided
                        if args.league_id is not None and args.league_id <= 0:
                            print("Error: League ID must be a positive integer", file=sys.stderr)
                            sys.exit(1)
                        results = db.list_teams(league_id=args.league_id)
                    elif args.table == "matches":
                        # Validate league_id if provided
                        if args.league_id is not None and args.league_id <= 0:
                            print("Error: League ID must be a positive integer", file=sys.stderr)
                            sys.exit(1)
                        results = db.list_matches(league_id=args.league_id)
                    else:
                        method = getattr(db, f"list_{args.table}")
                        results = method()

                # Enhance readability by resolving foreign key names for matches
                if args.table == "matches":
                    enhanced_results = []
                    for match in results:
                        match_dict = {
                            'id': match.id,
                            'league_id': match.league_id,
                            'home_team_id': match.home_team_id,
                            'visitor_team_id': match.visitor_team_id,
                            'facility_id': match.facility_id,
                            'date': match.date,
                            'time': match.time
                        }
                        
                        # Add human-readable names (with error handling)
                        try:
                            home_team = db.get_team(match.home_team_id)
                            if home_team:
                                match_dict['home_team'] = home_team.name
                        except Exception as e:
                            print(f"Warning: Could not retrieve home team {match.home_team_id}: {e}", file=sys.stderr)
                        
                        try:
                            visitor_team = db.get_team(match.visitor_team_id)
                            if visitor_team:
                                match_dict['visitor_team'] = visitor_team.name
                        except Exception as e:
                            print(f"Warning: Could not retrieve visitor team {match.visitor_team_id}: {e}", file=sys.stderr)
                        
                        try:
                            facility = db.get_facility(match.facility_id)
                            if facility:
                                match_dict['facility'] = facility.name
                        except Exception as e:
                            print(f"Warning: Could not retrieve facility {match.facility_id}: {e}", file=sys.stderr)
                        
                        enhanced_results.append(match_dict)
                    results = enhanced_results
                elif args.table == "teams":
                    # For teams, flatten the league information for better readability
                    enhanced_results = []
                    for team in results:
                        try:
                            team_dict = {
                                'id': team.id,
                                'name': team.name,
                                'league_id': team.league.id,
                                'league_name': team.league.name,
                                'year': team.league.year,
                                'section': team.league.section,
                                'region': team.league.region,
                                'age_group': team.league.age_group,
                                'division': team.league.division,
                                'home_facility_id': team.home_facility_id,
                                'captain': team.captain,
                                'preferred_days': team.preferred_days
                            }
                            enhanced_results.append(team_dict)
                        except Exception as e:
                            print(f"Warning: Could not process team {team.id}: {e}", file=sys.stderr)
                    results = enhanced_results
                elif args.table == "facilities":
                    # For facilities, include schedule and unavailable dates info
                    enhanced_results = []
                    for facility in results:
                        try:
                            facility_dict = facility.to_yaml_dict()
                            enhanced_results.append(facility_dict)
                        except Exception as e:
                            print(f"Warning: Could not process facility {facility.id}: {e}", file=sys.stderr)
                    results = enhanced_results
                else:
                    # Convert dataclass objects to dicts for JSON serialization
                    try:
                        results = [obj.__dict__ if hasattr(obj, '__dict__') else obj for obj in results]
                    except Exception as e:
                        print(f"Warning: Could not serialize results: {e}", file=sys.stderr)

                # Output results as JSON
                try:
                    print(json.dumps(results, indent=2))
                except Exception as e:
                    print(f"Error: Could not format output as JSON: {e}", file=sys.stderr)
                    sys.exit(1)
                    
            except Exception as e:
                print(f"Error: Failed to list {args.table}: {e}", file=sys.stderr)
                sys.exit(1)
                
        elif args.command == "load":
            # Validate arguments
            if not args.yaml_path or not args.yaml_path.strip():
                print("Error: YAML path cannot be empty", file=sys.stderr)
                sys.exit(1)
            
            try:
                db.load_yaml(args.table, args.yaml_path)
                print(f"Successfully loaded {args.table} from {args.yaml_path}")
            except FileNotFoundError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            except ValueError as e:
                print(f"Error: Invalid data format - {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error: Failed to load YAML - {e}", file=sys.stderr)
                sys.exit(1)
                
        elif args.command == "calculate-pairings":
            # Validate league_id
            if args.league_id <= 0:
                print("Error: League ID must be a positive integer", file=sys.stderr)
                sys.exit(1)
            
            try:
                # Get league information first
                league = db.get_league(args.league_id)
                if not league:
                    print(f"Error: League with ID {args.league_id} not found", file=sys.stderr)
                    sys.exit(1)
                
                # Get teams in the league
                teams = db.list_teams(league_id=args.league_id)
                if len(teams) < 2:
                    print(f"Error: League '{league.name}' has only {len(teams)} team(s). Need at least 2 teams to generate pairings.", file=sys.stderr)
                    sys.exit(1)
                
                print(f"Calculating pairings for league: {league.name}")
                print(f"League settings: {league.num_matches} matches per team, {league.num_lines_per_match} lines per match")
                print(f"Teams in league: {len(teams)}")
                print()
                
                # Calculate pairings
                pairings = db.calculate_pairings(args.league_id)
                
                # Format and display results
                pairing_results = []
                match_count_by_team = {}
                home_count_by_team = {}
                away_count_by_team = {}
                
                # Initialize counters
                for team in teams:
                    match_count_by_team[team.id] = 0
                    home_count_by_team[team.id] = 0
                    away_count_by_team[team.id] = 0
                
                for i, (home_team, away_team) in enumerate(pairings, 1):
                    pairing_dict = {
                        'match_number': i,
                        'home_team_id': home_team.id,
                        'home_team_name': home_team.name,
                        'visitor_team_id': away_team.id,
                        'visitor_team_name': away_team.name
                    }
                    pairing_results.append(pairing_dict)
                    
                    # Update counters
                    match_count_by_team[home_team.id] += 1
                    match_count_by_team[away_team.id] += 1
                    home_count_by_team[home_team.id] += 1
                    away_count_by_team[away_team.id] += 1
                
                # Display summary statistics
                print("PAIRING SUMMARY:")
                print(f"Total matches generated: {len(pairings)}")
                print(f"Expected matches per team: {league.num_matches}")
                print()
                
                print("TEAM STATISTICS:")
                print(f"{'Team ID':<8} {'Team Name':<30} {'Total':<7} {'Home':<6} {'Away':<6}")
                print("-" * 60)
                
                for team in teams:
                    total = match_count_by_team[team.id]
                    home = home_count_by_team[team.id]
                    away = away_count_by_team[team.id]
                    print(f"{team.id:<8} {team.name[:29]:<30} {total:<7} {home:<6} {away:<6}")
                
                print()
                print("DETAILED PAIRINGS:")
                print(json.dumps(pairing_results, indent=2))
                
                # Check for balance issues
                print()
                print("BALANCE ANALYSIS:")
                
                # Check if all teams have the expected number of matches
                teams_with_wrong_count = []
                for team in teams:
                    if match_count_by_team[team.id] != league.num_matches:
                        teams_with_wrong_count.append((team, match_count_by_team[team.id]))
                
                if teams_with_wrong_count:
                    print("⚠️  WARNING: Some teams don't have the expected number of matches:")
                    for team, actual_count in teams_with_wrong_count:
                        print(f"   Team {team.name} (ID: {team.id}): {actual_count} matches (expected {league.num_matches})")
                else:
                    print("✅ All teams have the expected number of matches")
                
                # Check home/away balance
                max_imbalance = 0
                imbalanced_teams = []
                for team in teams:
                    home = home_count_by_team[team.id]
                    away = away_count_by_team[team.id]
                    imbalance = abs(home - away)
                    if imbalance > max_imbalance:
                        max_imbalance = imbalance
                    if imbalance > 1:  # More than 1 match difference is noteworthy
                        imbalanced_teams.append((team, home, away, imbalance))
                
                if imbalanced_teams:
                    print(f"⚠️  Some teams have home/away imbalance (max imbalance: {max_imbalance}):")
                    for team, home, away, imbalance in imbalanced_teams:
                        print(f"   Team {team.name} (ID: {team.id}): {home} home, {away} away (difference: {imbalance})")
                else:
                    print("✅ Good home/away balance across all teams")
                
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error: Failed to calculate pairings - {e}", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()