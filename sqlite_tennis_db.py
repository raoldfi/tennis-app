"""
Complete SQLite Tennis Database Implementation

This is the full SQLite implementation of the TennisDBInterface with all enhanced
features including line management, scheduling, analytics, and bulk operations.
Now includes all database-level scheduling methods that were moved from USTA classes.

Updated to remove backward compatibility code and assume current schema.
"""

import sqlite3
import argparse
import json
import yaml
import os
import sys
from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime, timedelta
from collections import defaultdict

# Import the interface first
from tennis_db_interface import TennisDBInterface

# Import USTA classes
from usta import League, Team, Match, Facility, WeeklySchedule, DaySchedule, TimeSlot, Line
from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS


class SQLiteTennisDB(TennisDBInterface):
    """SQLite implementation of the TennisDBInterface with enhanced line management"""
    
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
        
        try:
            self._initialize_schema()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database: {e}")

    
    def _dictify(self, row) -> dict:
        """Convert sqlite Row object to dictionary"""
        return dict(row) if row else {}

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
            
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
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
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE RESTRICT ON UPDATE CASCADE,
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
            """)
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database initialization failed: {e}")
    
    # ========== Connection Management ==========
    
    def connect(self) -> None:
        """Establish database connection"""
        if not self.conn:
            self._initialize_schema()
    
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

    # ========== Team Management ==========
    
    def add_team(self, team: Team) -> None:
        """Add a new team to the database"""
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
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding team: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding team: {e}")
    
    def get_team(self, team_id: int) -> Optional[Team]:
        """Get a team by ID"""
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
    
    def list_teams(self, league_id: Optional[int] = None) -> List[Team]:
        """List all teams, optionally filtered by league"""
        if league_id is not None and (not isinstance(league_id, int) or league_id <= 0):
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            if league_id:
                # Verify league exists
                if not self.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                self.cursor.execute("SELECT * FROM teams WHERE league_id = ? ORDER BY name", (league_id,))
            else:
                self.cursor.execute("SELECT * FROM teams ORDER BY name")
            
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

    def update_team(self, team: Team) -> None:
        """Update an existing team in the database"""
        if not isinstance(team, Team):
            raise TypeError(f"Expected Team object, got: {type(team)}")
        
        try:
            # Check if team exists
            existing_team = self.get_team(team.id)
            if not existing_team:
                raise ValueError(f"Team with ID {team.id} does not exist")
            
            # Verify related entities exist
            if not self.get_league(team.league.id):
                raise ValueError(f"League with ID {team.league.id} does not exist")
            if not self.get_facility(team.home_facility_id):
                raise ValueError(f"Facility with ID {team.home_facility_id} does not exist")
            
            # Convert preferred_days list to comma-separated string for storage
            preferred_days_str = ','.join(team.preferred_days)
            
            self.cursor.execute("""
                UPDATE teams 
                SET name = ?, league_id = ?, home_facility_id = ?, captain = ?, preferred_days = ?
                WHERE id = ?
            """, (
                team.name,
                team.league.id,
                team.home_facility_id,
                team.captain,
                preferred_days_str,
                team.id
            ))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update team {team.id}")
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating team: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating team: {e}")

    def delete_team(self, team_id: int) -> None:
        """Delete a team from the database"""
        if not isinstance(team_id, int) or team_id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {team_id}")
        
        try:
            # Check if team exists
            existing_team = self.get_team(team_id)
            if not existing_team:
                raise ValueError(f"Team with ID {team_id} does not exist")
            
            # Check if team is referenced by matches
            self.cursor.execute("""
                SELECT COUNT(*) as count 
                FROM matches 
                WHERE home_team_id = ? OR visitor_team_id = ?
            """, (team_id, team_id))
            match_count = self.cursor.fetchone()['count']
            if match_count > 0:
                raise ValueError(f"Cannot delete team {team_id}: it is referenced by {match_count} match(es)")
            
            # Delete the team
            self.cursor.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete team {team_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting team {team_id}: {e}")

    # ========== League Management ==========
    
    def add_league(self, league: League) -> None:
        """Add a new league to the database"""
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
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding league: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding league: {e}")
    
    def get_league(self, league_id: int) -> Optional[League]:
        """Get a league by ID"""
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
    
    def list_leagues(self) -> List[League]:
        """List all leagues"""
        try:
            self.cursor.execute("SELECT * FROM leagues ORDER BY year DESC, name")
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

    def update_league(self, league: League) -> None:
        """Update an existing league in the database"""
        if not isinstance(league, League):
            raise TypeError(f"Expected League object, got: {type(league)}")
        
        try:
            # Check if league exists
            existing_league = self.get_league(league.id)
            if not existing_league:
                raise ValueError(f"League with ID {league.id} does not exist")
            
            # Convert day lists to comma-separated strings for storage
            preferred_days_str = ','.join(league.preferred_days)
            backup_days_str = ','.join(league.backup_days)
            
            self.cursor.execute("""
                UPDATE leagues 
                SET year = ?, section = ?, region = ?, age_group = ?, division = ?, name = ?, 
                    num_lines_per_match = ?, num_matches = ?, allow_split_lines = ?, 
                    preferred_days = ?, backup_days = ?, start_date = ?, end_date = ?
                WHERE id = ?
            """, (
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
                league.end_date,
                league.id
            ))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update league {league.id}")
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating league: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating league: {e}")

    def delete_league(self, league_id: int) -> None:
        """Delete a league from the database"""
        if not isinstance(league_id, int) or league_id <= 0:
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            # Check if league exists
            existing_league = self.get_league(league_id)
            if not existing_league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Check if league is referenced by teams
            self.cursor.execute("SELECT COUNT(*) as count FROM teams WHERE league_id = ?", (league_id,))
            team_count = self.cursor.fetchone()['count']
            if team_count > 0:
                raise ValueError(f"Cannot delete league {league_id}: it is referenced by {team_count} team(s)")
            
            # Check if league is referenced by matches
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE league_id = ?", (league_id,))
            match_count = self.cursor.fetchone()['count']
            if match_count > 0:
                raise ValueError(f"Cannot delete league {league_id}: it is referenced by {match_count} match(es)")
            
            # Delete the league
            self.cursor.execute("DELETE FROM leagues WHERE id = ?", (league_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete league {league_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting league {league_id}: {e}")

    # ========== Match Management ==========
    
    def add_match(self, match: Match) -> None:
        """Add a new match to the database"""
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
            
            # Verify teams are in the same league
            home_team = self.get_team(match.home_team_id)
            visitor_team = self.get_team(match.visitor_team_id)
            if home_team.league.id != match.league_id:
                raise ValueError(f"Home team {match.home_team_id} is not in league {match.league_id}")
            if visitor_team.league.id != match.league_id:
                raise ValueError(f"Visitor team {match.visitor_team_id} is not in league {match.league_id}")
            
            # Determine if match is scheduled or unscheduled
            is_scheduled = all([match.facility_id, match.date, match.time])
            status = 'scheduled' if is_scheduled else 'unscheduled'
            
            # Verify facility exists if provided
            if match.facility_id and not self.get_facility(match.facility_id):
                raise ValueError(f"Facility with ID {match.facility_id} does not exist")
            
            self.cursor.execute("""
                INSERT INTO matches (id, league_id, home_team_id, visitor_team_id, facility_id, date, time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match.id,
                match.league_id,
                match.home_team_id,
                match.visitor_team_id,
                match.facility_id,
                match.date,
                match.time,
                status
            ))
            
            # Add lines if they exist
            for line in match.lines:
                self.add_line(line)
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding match: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding match: {e}")

    def get_match(self, match_id: int) -> Optional[Match]:
        """Get a match by ID without its lines"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            self.cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            match_data = self._dictify(row)
            # Remove status field as it's not part of the Match dataclass
            match_data.pop('status', None)
            # Initialize with empty lines list
            match_data['lines'] = []
            return Match(**match_data)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")

    def get_match_with_lines(self, match_id: int) -> Optional[Match]:
        """Get a match populated with all its lines"""
        match = self.get_match(match_id)
        if not match:
            return None
        
        # Load the lines for this match
        match.lines = self.list_lines(match_id=match_id)
        return match

    def list_matches(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List[Match]:
        """List matches without lines (for performance)"""
        if league_id is not None and (not isinstance(league_id, int) or league_id <= 0):
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            # Build query based on filters
            where_conditions = []
            params = []
            
            if league_id:
                # Verify league exists
                if not self.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                where_conditions.append("league_id = ?")
                params.append(league_id)
            
            if not include_unscheduled:
                where_conditions.append("status = 'scheduled'")
            
            query = "SELECT * FROM matches"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY date, time"
            
            self.cursor.execute(query, params)
            
            matches = []
            for row in self.cursor.fetchall():
                match_data = self._dictify(row)
                # Remove status field as it's not part of the Match dataclass
                match_data.pop('status', None)
                # Initialize with empty lines list
                match_data['lines'] = []
                matches.append(Match(**match_data))
            
            return matches
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing matches: {e}")

    def list_matches_with_lines(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List[Match]:
        """List matches populated with all their lines"""
        matches = self.list_matches(league_id=league_id, include_unscheduled=include_unscheduled)
        
        # Load lines for each match in a batch for efficiency
        if matches:
            match_ids = [match.id for match in matches]
            
            # Get all lines for these matches in one query
            placeholders = ','.join('?' * len(match_ids))
            query = f"SELECT * FROM lines WHERE match_id IN ({placeholders}) ORDER BY match_id, line_number"
            self.cursor.execute(query, match_ids)
            
            lines_by_match = defaultdict(list)
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                line = Line(**line_data)
                lines_by_match[line.match_id].append(line)
            
            # Assign lines to matches
            for match in matches:
                match.lines = lines_by_match.get(match.id, [])
        
        return matches

    def update_match(self, match: Match) -> None:
        """Update match metadata (does not update lines)"""
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        try:
            # Check if match exists
            existing_match = self.get_match(match.id)
            if not existing_match:
                raise ValueError(f"Match with ID {match.id} does not exist")
            
            # Verify related entities exist
            if not self.get_league(match.league_id):
                raise ValueError(f"League with ID {match.league_id} does not exist")
            if not self.get_team(match.home_team_id):
                raise ValueError(f"Home team with ID {match.home_team_id} does not exist")
            if not self.get_team(match.visitor_team_id):
                raise ValueError(f"Visitor team with ID {match.visitor_team_id} does not exist")
            
            # Verify facility exists if provided
            if match.facility_id and not self.get_facility(match.facility_id):
                raise ValueError(f"Facility with ID {match.facility_id} does not exist")
            
            # Determine if match is scheduled or unscheduled
            is_scheduled = all([match.facility_id, match.date, match.time])
            status = 'scheduled' if is_scheduled else 'unscheduled'
            
            # Update the match
            self.cursor.execute("""
                UPDATE matches 
                SET league_id = ?, home_team_id = ?, visitor_team_id = ?, 
                    facility_id = ?, date = ?, time = ?, status = ?
                WHERE id = ?
            """, (
                match.league_id,
                match.home_team_id,
                match.visitor_team_id,
                match.facility_id,
                match.date,
                match.time,
                status,
                match.id
            ))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update match {match.id}")
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating match: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating match: {e}")

    def delete_match(self, match_id: int) -> None:
        """Delete a match and all its lines"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            # Check if match exists
            existing_match = self.get_match(match_id)
            if not existing_match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Delete all lines for this match (CASCADE should handle this, but be explicit)
            self.cursor.execute("DELETE FROM lines WHERE match_id = ?", (match_id,))
            
            # Delete the match
            self.cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete match {match_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting match {match_id}: {e}")

    # ========== Facility Management ==========
    
    def add_facility(self, facility: Facility) -> None:
        """Add a new facility to the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            # Check if facility ID already exists
            existing = self.get_facility(facility.id)
            if existing:
                raise ValueError(f"Facility with ID {facility.id} already exists")
            
            # Insert basic facility info
            self.cursor.execute("""
                INSERT INTO facilities (id, name, location, total_courts)
                VALUES (?, ?, ?, ?)
            """, (
                facility.id,
                facility.name,
                facility.location,
                facility.total_courts
            ))
            
            # Insert schedule data
            self._insert_facility_schedule(facility.id, facility.schedule)
            
            # Insert unavailable dates
            self._insert_facility_unavailable_dates(facility.id, facility.unavailable_dates)
            
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding facility: {e}")

    def get_facility(self, facility_id: int) -> Optional[Facility]:
        """Get a facility by ID"""
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
                location=facility_data['location'],
                total_courts=facility_data.get('total_courts', 0)
            )
            
            # Load schedule data
            facility.schedule = self._load_facility_schedule(facility_id)
            
            # Load unavailable dates
            facility.unavailable_dates = self._load_facility_unavailable_dates(facility_id)
            
            return facility
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving facility {facility_id}: {e}")

    def update_facility(self, facility: Facility) -> None:
        """Update an existing facility in the database"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            # Check if facility exists
            existing_facility = self.get_facility(facility.id)
            if not existing_facility:
                raise ValueError(f"Facility with ID {facility.id} does not exist")
            
            # Update basic facility info
            self.cursor.execute("""
                UPDATE facilities 
                SET name = ?, location = ?, total_courts = ?
                WHERE id = ?
            """, (
                facility.name,
                facility.location,
                facility.total_courts,
                facility.id
            ))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update facility {facility.id}")
            
            # Update schedule data (clear and re-insert)
            self._insert_facility_schedule(facility.id, facility.schedule)
            
            # Update unavailable dates (clear and re-insert)
            self._insert_facility_unavailable_dates(facility.id, facility.unavailable_dates)
            
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating facility: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating facility: {e}")
    
    def delete_facility(self, facility_id: int) -> None:
        """Delete a facility from the database"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Check if facility exists
            existing_facility = self.get_facility(facility_id)
            if not existing_facility:
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
            
            # Check if facility is referenced by lines
            self.cursor.execute("SELECT COUNT(*) as count FROM lines WHERE facility_id = ?", (facility_id,))
            line_count = self.cursor.fetchone()['count']
            if line_count > 0:
                raise ValueError(f"Cannot delete facility {facility_id}: it is referenced by {line_count} line(s)")
            
            # Delete the facility (CASCADE will delete schedule and unavailable_dates)
            self.cursor.execute("DELETE FROM facilities WHERE id = ?", (facility_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete facility {facility_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting facility {facility_id}: {e}")
        
    def list_facilities(self) -> List[Facility]:
        """List all facilities"""
        try:
            self.cursor.execute("SELECT * FROM facilities ORDER BY name")
            facilities = []
            
            for row in self.cursor.fetchall():
                facility_data = self._dictify(row)
                
                # Create basic facility
                facility = Facility(
                    id=facility_data['id'],
                    name=facility_data['name'],
                    location=facility_data['location'],
                    total_courts=facility_data.get('total_courts', 0)
                )
                
                # Load schedule and unavailable dates
                facility.schedule = self._load_facility_schedule(facility.id)
                facility.unavailable_dates = self._load_facility_unavailable_dates(facility.id)
                
                facilities.append(facility)
            
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing facilities: {e}")

    # ========== Helper Methods for Facilities ==========
    
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

    # ========== Line Management ==========

    def add_line(self, line: Line) -> None:
        """Add a line to the database"""
        if not isinstance(line, Line):
            raise TypeError(f"Expected Line object, got: {type(line)}")
        
        try:
            # Check if line ID already exists
            existing = self.get_line(line.id)
            if existing:
                raise ValueError(f"Line with ID {line.id} already exists")
            
            # Verify match exists
            if not self.get_match(line.match_id):
                raise ValueError(f"Match with ID {line.match_id} does not exist")
            
            # Verify facility exists if provided
            if line.facility_id and not self.get_facility(line.facility_id):
                raise ValueError(f"Facility with ID {line.facility_id} does not exist")
            
            self.cursor.execute("""
                INSERT INTO lines (id, match_id, line_number, facility_id, date, time, court_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                line.id,
                line.match_id,
                line.line_number,
                line.facility_id,
                line.date,
                line.time,
                line.court_number
            ))
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding line: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding line: {e}")

    def get_line(self, line_id: int) -> Optional[Line]:
        """Get a specific line"""
        if not isinstance(line_id, int) or line_id <= 0:
            raise ValueError(f"Line ID must be a positive integer, got: {line_id}")
        
        try:
            self.cursor.execute("SELECT * FROM lines WHERE id = ?", (line_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            line_data = self._dictify(row)
            return Line(**line_data)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving line {line_id}: {e}")

    def list_lines(self, match_id: Optional[int] = None, 
                   facility_id: Optional[int] = None,
                   date: Optional[str] = None) -> List[Line]:
        """List lines with optional filters"""
        try:
            where_conditions = []
            params = []
            
            if match_id is not None:
                where_conditions.append("match_id = ?")
                params.append(match_id)
            
            if facility_id is not None:
                where_conditions.append("facility_id = ?")
                params.append(facility_id)
            
            if date is not None:
                where_conditions.append("date = ?")
                params.append(date)
            
            query = "SELECT * FROM lines"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY match_id, line_number"
            
            self.cursor.execute(query, params)
            
            lines = []
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                lines.append(Line(**line_data))
            
            return lines
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing lines: {e}")

    def update_line(self, line: Line) -> None:
        """Update a line"""
        if not isinstance(line, Line):
            raise TypeError(f"Expected Line object, got: {type(line)}")
        
        try:
            # Check if line exists
            existing_line = self.get_line(line.id)
            if not existing_line:
                raise ValueError(f"Line with ID {line.id} does not exist")
            
            # Verify related entities exist
            if not self.get_match(line.match_id):
                raise ValueError(f"Match with ID {line.match_id} does not exist")
            
            if line.facility_id and not self.get_facility(line.facility_id):
                raise ValueError(f"Facility with ID {line.facility_id} does not exist")
            
            self.cursor.execute("""
                UPDATE lines 
                SET match_id = ?, line_number = ?, facility_id = ?, date = ?, time = ?, court_number = ?
                WHERE id = ?
            """, (
                line.match_id,
                line.line_number,
                line.facility_id,
                line.date,
                line.time,
                line.court_number,
                line.id
            ))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update line {line.id}")
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating line: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating line: {e}")

    def delete_line(self, line_id: int) -> None:
        """Delete a line"""
        if not isinstance(line_id, int) or line_id <= 0:
            raise ValueError(f"Line ID must be a positive integer, got: {line_id}")
        
        try:
            # Check if line exists
            existing_line = self.get_line(line_id)
            if not existing_line:
                raise ValueError(f"Line with ID {line_id} does not exist")
            
            # Delete the line
            self.cursor.execute("DELETE FROM lines WHERE id = ?", (line_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete line {line_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting line {line_id}: {e}")

    # ========== Scheduling Operations ==========

    def schedule_match_all_lines_same_time(
        self,
        match_id: int,
        facility_id: int,
        date: str,
        time: str
    ) -> bool:
        """
        Schedule all lines of a match at the same facility, date, and time.
        Returns True if successful, False if there is not enough capacity.
        Raises on invalid match or facility IDs.
        """
        print(f"DEBUG: schedule_match_all_lines_same_time called with:")
        print(f"  match_id={match_id}, facility_id={facility_id}, date='{date}', time='{time}'")
        
        try:
            # 1) Verify that the match exists (and load its lines)
            print(f"DEBUG: Step 1 - Loading match {match_id}")
            match = self.get_match_with_lines(match_id)
            if not match:
                print(f"DEBUG: ERROR - Match {match_id} does not exist")
                raise ValueError(f"Match with ID {match_id} does not exist")
            print(f"DEBUG: Match {match_id} loaded successfully with {len(match.lines)} lines")
    
            # 2) Verify that the facility exists (and load its weekly schedule + unavailable dates)
            print(f"DEBUG: Step 2 - Loading facility {facility_id}")
            facility = self.get_facility(facility_id)
            if not facility:
                print(f"DEBUG: ERROR - Facility {facility_id} does not exist")
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            print(f"DEBUG: Facility {facility_id} ('{facility.name}') loaded successfully")
    
            # 3) Count how many "lines" we need to place
            # After loading the match, ensure lines exist
            if not match.lines:
                league = self.get_league(match.league_id)
                self.create_lines_for_match(match_id, league)
                match = self.get_match_with_lines(match_id)  # Reload with lines
            
            courts_needed = len(match.lines)
            print(f"DEBUG: Step 3 - Courts needed: {courts_needed}")
    
            # 4) Check if the facility is open on that date & time, and has enough available courts
            print(f"DEBUG: Step 4 - Checking court availability...")
            
            # Get day of week for debugging
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
                print(f"DEBUG: Date {date} is a {day_name}")
            except ValueError:
                print(f"DEBUG: ERROR - Invalid date format: {date}")
            
            # Check if facility is available on this date
            is_facility_available = facility.is_available_on_date(date)
            print(f"DEBUG: Facility available on {date}: {is_facility_available}")
            if not is_facility_available:
                print(f"DEBUG: Facility unavailable dates: {facility.unavailable_dates}")
            
            # Get detailed availability info
            available_courts_count = self.get_available_courts_count(facility_id, date, time)
            print(f"DEBUG: Available courts at {time}: {available_courts_count}")
            print(f"DEBUG: Courts needed: {courts_needed}")
            
            availability_check = self.check_court_availability(facility_id, date, time, courts_needed)
            print(f"DEBUG: Court availability check result: {availability_check}")
            
            if not availability_check:
                print(f"DEBUG: FAILED - Not enough courts available or facility/time unavailable")
                print(f"DEBUG: Returning False")
                return False
    
            print(f"DEBUG: Step 5 - Updating match record...")
            # 5) Mark the entire match as scheduled
            self.cursor.execute("""
                UPDATE matches
                   SET facility_id = ?,
                       date        = ?,
                       time        = ?,
                       status      = 'scheduled'
                 WHERE id = ?
            """, (facility_id, date, time, match_id))
            
            match_rows_updated = self.cursor.rowcount
            print(f"DEBUG: Match update affected {match_rows_updated} rows")
    
            print(f"DEBUG: Step 6 - Updating {len(match.lines)} line records...")
            # 6) "Schedule" each line row in the lines table to point to this facility/date/time
            lines_updated = 0
            for i, line in enumerate(match.lines):
                print(f"DEBUG: Updating line {i+1}/{len(match.lines)} (ID: {line.id})")
                self.cursor.execute("""
                    UPDATE lines
                       SET facility_id = ?,
                           date        = ?,
                           time        = ?
                     WHERE id = ?
                """, (facility_id, date, time, line.id))
                
                line_rows_updated = self.cursor.rowcount
                if line_rows_updated > 0:
                    lines_updated += 1
                print(f"DEBUG: Line {line.id} update affected {line_rows_updated} rows")
    
            print(f"DEBUG: Successfully updated {lines_updated}/{len(match.lines)} lines")
            print(f"DEBUG: SUCCESS - Match {match_id} scheduled successfully")
            return True
    
        except sqlite3.Error as e:
            print(f"DEBUG: SQLite ERROR in schedule_match_all_lines_same_time: {e}")
            raise RuntimeError(f"Database error scheduling match {match_id}: {e}")
        except Exception as e:
            print(f"DEBUG: GENERAL ERROR in schedule_match_all_lines_same_time: {e}")
            raise

    

    def schedule_match_split_lines(
        self,
        match_id: int,
        date: str,
        scheduling_plan: List[Tuple[str, int, int]]
    ) -> bool:
        """
        Schedule the lines of a single match across multiple (time, facility, num_lines) slots.

        scheduling_plan is a list of tuples `(time_str, facility_id, num_lines_at_time)` such that
        the sum of all `num_lines_at_time` equals the total number of lines in the match.  The
        first row in scheduling_plan determines the "primary" facility/time that gets stored at
        the match‐level; all others are simply per‐line assignments.

        Returns True if all lines can be scheduled exactly as requested; returns False (with NO
        partial writes) if any individual timeslot does not have enough courts.  Raises if:
        - the match_id is invalid,
        - or the league to which this match belongs does not allow split‐line scheduling,
        - or the scheduling_plan's total number of lines does not match the match's actual lines.
        """
        try:
            # Verify that the match exists (and load its lines)
            match = self.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")

            # Verify that the parent league allows split‐line scheduling
            league = self.get_league(match.league_id)
            if not league.allow_split_lines:
                raise ValueError(f"League {league.name} does not allow split‐line scheduling")

            # Ensure the plan covers exactly as many lines as the match has
            total_planned_lines = sum(num_lines for _, _, num_lines in scheduling_plan)
            if total_planned_lines != len(match.lines):
                raise ValueError(
                    f"Scheduling plan covers {total_planned_lines} lines, "
                    f"but match {match_id} has {len(match.lines)} lines"
                )

            # Check if this match is already scheduled
            for line in match.lines:
                if line.date is not None or line.facility_id is not None:
                    raise RuntimeError(f"Match {match_id} is already scheduled. Unschedule it first.")

            # Verify all timeslots have enough capacity before making any changes
            for (slot_time, slot_facility_id, num_lines_at_time) in scheduling_plan:
                if not self.check_court_availability(slot_facility_id, date, slot_time, num_lines_at_time):
                    return False

            # All checks passed, now schedule the lines
            line_index = 0
            primary_facility = None
            primary_time = None

            for (slot_time, slot_facility_id, num_lines_at_time) in scheduling_plan:
                # On the very first timeslot, remember it as the "primary"
                if primary_facility is None:
                    primary_facility = slot_facility_id
                    primary_time = slot_time

                # Schedule each line for this time slot
                for _ in range(num_lines_at_time):
                    if line_index >= len(match.lines):
                        break
                    this_line = match.lines[line_index]
                    self.cursor.execute("""
                        UPDATE lines
                           SET facility_id = ?,
                               date        = ?,
                               time        = ?
                         WHERE id = ?
                    """, (slot_facility_id, date, slot_time, this_line.id))
                    line_index += 1

            # Update the match row to reflect the "primary" slot
            self.cursor.execute("""
                UPDATE matches
                   SET facility_id = ?,
                       date        = ?,
                       time        = ?,
                       status      = 'scheduled'
                 WHERE id = ?
            """, (primary_facility, date, primary_time, match_id))

            return True

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error scheduling split lines for match {match_id}: {e}")
        except Exception:
            # If we hit any ValueError / RuntimeError above, let it percolate
            raise

    def unschedule_match(self, match_id: int) -> None:
        """Unschedule a match and all its lines"""
        try:
            # Check if match exists
            existing_match = self.get_match(match_id)
            if not existing_match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Update the match to unscheduled state
            self.cursor.execute("""
                UPDATE matches 
                SET facility_id = NULL, date = NULL, time = NULL, status = 'unscheduled'
                WHERE id = ?
            """, (match_id,))
            
            # Unschedule all lines
            self.cursor.execute("""
                UPDATE lines 
                SET facility_id = NULL, date = NULL, time = NULL, court_number = NULL
                WHERE match_id = ?
            """, (match_id,))
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error unscheduling match {match_id}: {e}")

    def check_court_availability(self, facility_id: int, date: str, time: str, 
                               courts_needed: int) -> bool:
        """Check if enough courts are available at a facility for a given date/time"""
        available_courts = self.get_available_courts_count(facility_id, date, time)
        return available_courts >= courts_needed

    def get_available_courts_count(self, facility_id: int, date: str, time: str) -> int:
        """Get the number of courts available at a facility for a given date/time"""
        try:
            # Get facility to check availability
            facility = self.get_facility(facility_id)
            if not facility or not facility.is_available_on_date(date):
                return 0
            
            # Get day of week
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return 0
            
            # Get total courts available at this time
            self.cursor.execute("""
                SELECT available_courts 
                FROM facility_schedules 
                WHERE facility_id = ? AND day = ? AND time = ?
            """, (facility_id, day_name, time))
            
            row = self.cursor.fetchone()
            if not row:
                return 0
            
            total_courts = row['available_courts']
            
            # Get courts already scheduled
            scheduled_lines = self.get_lines_by_time_slot(facility_id, date, time)
            used_courts = len(scheduled_lines)
            
            return max(0, total_courts - used_courts)
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error checking court availability: {e}")

    def get_lines_by_time_slot(self, facility_id: int, date: str, time: str) -> List[Line]:
        """Get all lines scheduled at a facility on a specific date and time"""
        try:
            self.cursor.execute("""
                SELECT * FROM lines 
                WHERE facility_id = ? AND date = ? AND time = ?
                ORDER BY line_number
            """, (facility_id, date, time))
            
            lines = []
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                lines.append(Line(**line_data))
            
            return lines
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting lines by time slot: {e}")

    # ========== Enhanced Scheduling Methods ==========
    
    def get_unscheduled_matches(self, league_id: Optional[int] = None) -> List[Match]:
        """Get all unscheduled matches, optionally filtered by league"""
        return self.list_matches(league_id=league_id, include_unscheduled=True)

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
        try:
            # Get the match and verify it exists
            match = self.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Get the league
            league = self.get_league(match.league_id)
            if not league:
                raise ValueError(f"League with ID {match.league_id} does not exist")
            
            # Get facility list
            if facility_ids is None:
                all_facilities = self.list_facilities()
                facility_ids = [f.id for f in all_facilities]
            
            options = {}
            
            for date in preferred_dates:
                date_options = []
                
                for facility_id in facility_ids:
                    facility = self.get_facility(facility_id)
                    if not facility:
                        continue
                    
                    # Get scheduling options for this facility/date
                    facility_options = facility.get_scheduling_options_for_match(league, date)
                    
                    if facility_options:
                        # Check if we have enough courts
                        day_name = list(facility_options.keys())[0]
                        available_times = facility_options[day_name]
                        
                        valid_times = []
                        for time in available_times:
                            if self.check_court_availability(facility_id, date, time, league.get_total_courts_needed()):
                                valid_times.append(time)
                        
                        if valid_times:
                            date_options.append({
                                'facility_id': facility_id,
                                'facility_name': facility.name,
                                'day': day_name,
                                'times': valid_times,
                                'type': 'same_time'
                            })
                        
                        # Also check split line options if allowed
                        if league.allow_split_lines:
                            split_options = facility.find_scheduling_slots_for_split_lines(
                                day_name, league.get_total_courts_needed()
                            )
                            if split_options:
                                # Validate each split option against actual availability
                                valid_split_options = []
                                for option in split_options:
                                    is_valid = True
                                    for time_str, courts_needed in option:
                                        if not self.check_court_availability(facility_id, date, time_str, courts_needed):
                                            is_valid = False
                                            break
                                    if is_valid:
                                        valid_split_options.append(option)
                                
                                if valid_split_options:
                                    date_options.append({
                                        'facility_id': facility_id,
                                        'facility_name': facility.name,
                                        'day': day_name,
                                        'split_options': valid_split_options,
                                        'type': 'split_lines'
                                    })
                
                if date_options:
                    options[date] = date_options
            
            return options
            
        except Exception as e:
            raise RuntimeError(f"Error finding scheduling options for match {match_id}: {e}")

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
        try:
            # Get the match and ensure it has lines
            match = self.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Ensure lines exist
            if not match.lines:
                league = self.get_league(match.league_id)
                self.create_lines_for_match(match_id, league)
                match = self.get_match_with_lines(match_id)  # Reload with lines
            
            # Get home team's facility if preferring home facility
            facility_ids = None
            if prefer_home_facility:
                home_team = self.get_team(match.home_team_id)
                if home_team:
                    facility_ids = [home_team.home_facility_id]
            
            # Find scheduling options
            options_by_date = self.find_scheduling_options_for_match(match_id, preferred_dates, facility_ids)
            
            # Try each date in order
            for date in preferred_dates:
                if date in options_by_date:
                    # Try the first available option
                    for option in options_by_date[date]:
                        try:
                            if option['type'] == 'same_time' and option['times']:
                                # Schedule all lines at the same time
                                time = option['times'][0]  # Use first available time
                                success = self.schedule_match_all_lines_same_time(
                                    match_id, option['facility_id'], date, time
                                )
                                if success:
                                    return True
                            
                            elif option['type'] == 'split_lines' and option['split_options']:
                                # Schedule lines across different times
                                split_option = option['split_options'][0]  # Use first split option
                                # Convert to the format expected by the database method
                                plan_tuples = [
                                    (time, option['facility_id'], courts) 
                                    for time, courts in split_option
                                ]
                                success = self.schedule_match_split_lines(match_id, date, plan_tuples)
                                if success:
                                    return True
                        except Exception:
                            # If this specific option fails, try the next one
                            continue
            
            return False
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling match {match_id}: {e}")


    def auto_schedule_matches(self, matches: List[Match], dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule a list of matches
        
        Args:
            matches: List of matches to schedule
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        try:
            results = {
                'total_matches': len(matches),
                'scheduled_successfully': 0,
                'failed_to_schedule': 0,
                'scheduling_details': [],
                'dry_run': dry_run
            }
            
            for match in matches:
                # Get optimal dates for this specific match (prioritizing team preferences)
                optimal_dates = self.get_optimal_scheduling_dates(match)
                
                if not dry_run:
                    success = self.auto_schedule_match(match.id, optimal_dates[:10])  # Try first 10 dates
                else:
                    # For dry run, just check if options exist
                    options = self.find_scheduling_options_for_match(match.id, optimal_dates[:5])
                    success = len(options) > 0
                
                if success:
                    results['scheduled_successfully'] += 1
                    results['scheduling_details'].append({
                        'match_id': match.id,
                        'status': 'scheduled',
                        'home_team_id': match.home_team_id,
                        'visitor_team_id': match.visitor_team_id
                    })
                else:
                    results['failed_to_schedule'] += 1
                    results['scheduling_details'].append({
                        'match_id': match.id,
                        'status': 'failed',
                        'home_team_id': match.home_team_id,
                        'visitor_team_id': match.visitor_team_id,
                        'reason': 'No available time slots found'
                    })
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling matches: {e}")



    def auto_schedule_league_matches(self, league_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule all unscheduled matches in a league
        
        Args:
            league_id: League to schedule matches for
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        try:
            # Get the league
            league = self.get_league(league_id)
            if not league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Get unscheduled matches
            all_matches = self.list_matches_with_lines(league_id=league_id, include_unscheduled=True)
            unscheduled_matches = [m for m in all_matches if m.is_unscheduled()]
            
            # Use the new auto_schedule_matches function
            results = self.auto_schedule_matches(unscheduled_matches, dry_run=dry_run)
            
            # Add league-specific information to results
            results['league_id'] = league_id
            results['total_unscheduled'] = results['total_matches']  # Backward compatibility
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling league matches: {e}")



    # Replace the existing get_optimal_scheduling_dates method:
    def get_optimal_scheduling_dates(self, match: Match, 
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
        try:
            # Get the league
            league = self.get_league(match.league_id)
            if not league:
                raise ValueError(f"League with ID {match.league_id} does not exist")
            
            # Get teams to understand their preferences
            home_team = self.get_team(match.home_team_id)
            visitor_team = self.get_team(match.visitor_team_id)
            
            if not home_team or not visitor_team:
                raise ValueError(f"Teams not found for match {match.id}")
            
            # Use league dates or reasonable defaults
            search_start = start_date or league.start_date or datetime.now().strftime('%Y-%m-%d')
            search_end = end_date or league.end_date
            
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
            home_preferred = set(home_team.preferred_days)
            visitor_preferred = set(visitor_team.preferred_days)
            
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
                if not league.can_schedule_on_day(day_name):
                    current += timedelta(days=1)
                    continue
                
                # Determine priority based on team and league preferences
                priority = 5  # Default: allowed but not preferred
                
                if day_name in home_preferred and day_name in visitor_preferred:
                    priority = 1  # Both teams prefer this day
                elif day_name in home_preferred or day_name in visitor_preferred:
                    priority = 2  # One team prefers this day
                elif day_name in league.preferred_days:
                    priority = 3  # League prefers this day
                elif day_name in league.backup_days:
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

    def validate_league_scheduling_feasibility(self, league_id: int) -> Dict[str, Any]:
        """
        Analyze whether it's feasible to schedule all matches in a league
        
        Args:
            league_id: League to analyze
            
        Returns:
            Dictionary with feasibility analysis
        """
        try:
            # Get the league
            league = self.get_league(league_id)
            if not league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Get facilities and teams
            facilities = self.list_facilities()
            teams = self.list_teams(league_id=league_id)
            
            # Calculate total court-hours needed
            total_matches = len(teams) * league.num_matches // 2  # Each match involves 2 teams
            total_court_hours = total_matches * league.num_lines_per_match * (league.get_match_duration_estimate() / 60)
            
            # Calculate available court-hours at facilities
            available_court_hours = 0
            facility_analysis = []
            
            for facility in facilities:
                facility_hours = self._calculate_facility_weekly_hours(facility, league)
                weeks_available = league.get_season_duration_weeks() or 16  # Default to 16 weeks
                facility_total_hours = facility_hours * weeks_available
                available_court_hours += facility_total_hours
                
                facility_analysis.append({
                    'facility_id': facility.id,
                    'facility_name': facility.name,
                    'weekly_court_hours': facility_hours,
                    'total_season_hours': facility_total_hours
                })
            
            utilization_percentage = (total_court_hours / available_court_hours * 100) if available_court_hours > 0 else float('inf')
            
            return {
                'feasible': utilization_percentage < 80,  # Consider feasible if under 80% utilization
                'total_court_hours_needed': round(total_court_hours, 1),
                'total_court_hours_available': round(available_court_hours, 1),
                'utilization_percentage': round(utilization_percentage, 1),
                'total_matches': total_matches,
                'courts_per_match': league.num_lines_per_match,
                'facility_breakdown': facility_analysis,
                'recommendations': self._get_feasibility_recommendations(utilization_percentage, league)
            }
            
        except Exception as e:
            raise RuntimeError(f"Error validating league scheduling feasibility: {e}")

    def _calculate_facility_weekly_hours(self, facility: Facility, league: League) -> float:
        """Calculate total court-hours available per week at a facility for a specific league"""
        total_hours = 0
        
        for day_name, day_schedule in facility.schedule.get_all_days().items():
            # Only count days that work for this league
            if not league.can_schedule_on_day(day_name):
                continue
            
            for time_slot in day_schedule.start_times:
                # Each time slot contributes: courts * hours_per_slot
                # Assuming each time slot represents a 2-hour block
                hours_per_slot = 2.0
                total_hours += time_slot.available_courts * hours_per_slot
        
        return total_hours

    def _get_feasibility_recommendations(self, utilization_percentage: float, league: League) -> List[str]:
        """Get recommendations based on utilization analysis"""
        recommendations = []
        
        if utilization_percentage > 100:
            recommendations.append("CRITICAL: Not enough court availability. Consider reducing matches or adding facilities.")
        elif utilization_percentage > 80:
            recommendations.append("WARNING: High utilization. Scheduling may be difficult.")
            recommendations.append("Consider allowing split-line scheduling if not already enabled.")
        elif utilization_percentage > 60:
            recommendations.append("Moderate utilization. Should be schedulable with some flexibility.")
        else:
            recommendations.append("Good availability. Scheduling should be straightforward.")
        
        if not league.allow_split_lines and utilization_percentage > 50:
            recommendations.append("Consider enabling split-line scheduling for more flexibility.")
        
        if len(league.preferred_days) < 2:
            recommendations.append("Consider adding more preferred scheduling days for flexibility.")
        
        return recommendations

    def get_facility_utilization_detailed(self, facility_id: int, date: str) -> Dict[str, Any]:
        """
        Get detailed utilization for a facility on a specific date
        
        Args:
            facility_id: Facility to analyze
            date: Date to check (YYYY-MM-DD format)
            
        Returns:
            Dictionary with detailed utilization information
        """
        try:
            # Get the facility
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Get scheduled lines for this facility/date
            scheduled_lines = self.list_lines(facility_id=facility_id, date=date)
            
            # Get day of week
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return {'error': 'Invalid date format'}
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            # Calculate utilization by time slot
            utilization_by_time = {}
            total_available_slots = 0
            total_used_slots = 0
            
            for time_slot in day_schedule.start_times:
                time = time_slot.time
                available_courts = time_slot.available_courts
                
                # Count lines scheduled at this time
                lines_at_time = [line for line in scheduled_lines if line.time == time]
                used_courts = len(lines_at_time)
                
                utilization_by_time[time] = {
                    'available_courts': available_courts,
                    'used_courts': used_courts,
                    'remaining_courts': available_courts - used_courts,
                    'utilization_percentage': (used_courts / available_courts * 100) if available_courts > 0 else 0,
                    'scheduled_lines': [{'line_id': line.id, 'match_id': line.match_id} for line in lines_at_time]
                }
                
                total_available_slots += available_courts
                total_used_slots += used_courts
            
            overall_utilization = (total_used_slots / total_available_slots * 100) if total_available_slots > 0 else 0
            
            return {
                'facility_id': facility_id,
                'facility_name': facility.name,
                'date': date,
                'day_of_week': day_name,
                'overall_utilization_percentage': round(overall_utilization, 1),
                'total_available_court_slots': total_available_slots,
                'total_used_court_slots': total_used_slots,
                'total_remaining_court_slots': total_available_slots - total_used_slots,
                'utilization_by_time': utilization_by_time,
                'scheduled_lines_count': len(scheduled_lines),
                'facility_available': facility.is_available_on_date(date)
            }
            
        except Exception as e:
            raise RuntimeError(f"Error getting facility utilization: {e}")

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
        try:
            # Get the facility
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            forecast = {}
            current = start_dt
            
            while current <= end_dt:
                date_str = current.strftime('%Y-%m-%d')
                
                if facility.is_available_on_date(date_str):
                    utilization = self.get_facility_utilization_detailed(facility_id, date_str)
                    forecast[date_str] = utilization
                else:
                    forecast[date_str] = {
                        'facility_id': facility_id,
                        'facility_name': facility.name,
                        'date': date_str,
                        'status': 'facility_unavailable',
                        'reason': 'Facility marked as unavailable'
                    }
                
                current += timedelta(days=1)
            
            return forecast
            
        except Exception as e:
            raise RuntimeError(f"Error getting facility availability forecast: {e}")

    def get_scheduling_conflicts(self, line_id: int) -> List[Dict]:
        """
        Check if a line has any scheduling conflicts with other lines
        
        Args:
            line_id: Line to check for conflicts
            
        Returns:
            List of conflict descriptions
        """
        try:
            # Get the line
            line = self.get_line(line_id)
            if not line:
                raise ValueError(f"Line with ID {line_id} does not exist")
            
            if not line.is_scheduled():
                return []
            
            # Get other lines scheduled at same facility/date/time
            conflicting_lines = self.get_lines_by_time_slot(
                line.facility_id, line.date, line.time
            )
            
            # Remove this line from conflicts
            conflicts = [conflict_line for conflict_line in conflicting_lines if conflict_line.id != line.id]
            
            conflict_descriptions = []
            for conflict_line in conflicts:
                conflict_descriptions.append({
                    'conflicting_line_id': conflict_line.id,
                    'conflicting_match_id': conflict_line.match_id,
                    'facility_id': line.facility_id,
                    'date': line.date,
                    'time': line.time,
                    'court_number': conflict_line.court_number
                })
            
            return conflict_descriptions
            
        except Exception as e:
            raise RuntimeError(f"Error checking scheduling conflicts: {e}")

    # ========== Analytics ==========

    def get_league_scheduling_status(self, league_id: int) -> Dict[str, int]:
        """Get scheduling statistics for a league"""
        try:
            # Verify league exists
            if not self.get_league(league_id):
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Get match counts
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE league_id = ?", (league_id,))
            total_matches = self.cursor.fetchone()['count']
            
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE league_id = ? AND status = 'scheduled'", (league_id,))
            scheduled_matches = self.cursor.fetchone()['count']
            
            unscheduled_matches = total_matches - scheduled_matches
            
            # Get line counts
            self.cursor.execute("""
                SELECT COUNT(*) as count 
                FROM lines l 
                JOIN matches m ON l.match_id = m.id 
                WHERE m.league_id = ?
            """, (league_id,))
            total_lines = self.cursor.fetchone()['count']
            
            self.cursor.execute("""
                SELECT COUNT(*) as count 
                FROM lines l 
                JOIN matches m ON l.match_id = m.id 
                WHERE m.league_id = ? AND l.facility_id IS NOT NULL
            """, (league_id,))
            scheduled_lines = self.cursor.fetchone()['count']
            
            unscheduled_lines = total_lines - scheduled_lines
            
            # Get partially scheduled matches
            self.cursor.execute("""
                SELECT COUNT(DISTINCT m.id) as count
                FROM matches m
                WHERE m.league_id = ? 
                AND m.id IN (
                    SELECT match_id FROM lines WHERE facility_id IS NOT NULL
                )
                AND m.id IN (
                    SELECT match_id FROM lines WHERE facility_id IS NULL
                )
            """, (league_id,))
            partially_scheduled_matches = self.cursor.fetchone()['count']
            
            return {
                'total_matches': total_matches,
                'scheduled_matches': scheduled_matches,
                'unscheduled_matches': unscheduled_matches,
                'total_lines': total_lines,
                'scheduled_lines': scheduled_lines,
                'unscheduled_lines': unscheduled_lines,
                'partially_scheduled_matches': partially_scheduled_matches
            }
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting league scheduling status: {e}")

    def get_facility_utilization(self, facility_id: int, start_date: str, end_date: str) -> Dict[str, float]:
        """Get facility utilization statistics for a date range"""
        try:
            # Verify facility exists
            facility = self.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Calculate total available court-hours in the date range
            total_available_hours = 0
            total_used_hours = 0
            
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current_date <= end_date_obj:
                date_str = current_date.strftime('%Y-%m-%d')
                day_name = current_date.strftime('%A')
                
                if facility.is_available_on_date(date_str):
                    day_schedule = facility.schedule.get_day_schedule(day_name)
                    
                    for time_slot in day_schedule.start_times:
                        # Each time slot is typically 2 hours
                        hours_per_slot = 2.0
                        slot_available_hours = time_slot.available_courts * hours_per_slot
                        total_available_hours += slot_available_hours
                        
                        # Count used courts at this time slot
                        scheduled_lines = self.get_lines_by_time_slot(facility_id, date_str, time_slot.time)
                        used_courts = len(scheduled_lines)
                        slot_used_hours = used_courts * hours_per_slot
                        total_used_hours += slot_used_hours
                
                current_date += timedelta(days=1)
            
            # Calculate utilization metrics
            utilization_percentage = (total_used_hours / total_available_hours * 100) if total_available_hours > 0 else 0
            
            return {
                'total_available_hours': total_available_hours,
                'total_used_hours': total_used_hours,
                'utilization_percentage': round(utilization_percentage, 2),
                'start_date': start_date,
                'end_date': end_date,
                'days_analyzed': (end_date_obj - datetime.strptime(start_date, '%Y-%m-%d')).days + 1
            }
            
        except Exception as e:
            raise RuntimeError(f"Error calculating facility utilization: {e}")

    # ========== Bulk Operations ==========

    def bulk_create_matches_with_lines(self, league_id: int, teams: List[Team]) -> List[Match]:
        """Create all matches for a league with their required lines"""
        try:
            # Get league
            league = self.get_league(league_id)
            if not league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Generate matches using the league's method
            matches = league.generate_matches(teams)
            
            # Add each match to the database
            for match in matches:
                self.add_match(match)
                # Create lines for the match
                lines = self.create_lines_for_match(match.id, league)
                match.lines = lines
            
            return matches
            
        except Exception as e:
            raise RuntimeError(f"Error bulk creating matches: {e}")

    def create_lines_for_match(self, match_id: int, league: League) -> List[Line]:
        """Create the required number of unscheduled lines for a match based on league rules"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        # Verify match exists
        match = self.get_match(match_id)
        if not match:
            raise ValueError(f"Match with ID {match_id} does not exist")
        
        # Delete existing lines for this match
        self.cursor.execute("DELETE FROM lines WHERE match_id = ?", (match_id,))
        
        # Create new lines
        lines = []
        num_lines = league.get_total_courts_needed()
        
        for line_num in range(1, num_lines + 1):
            line_id = match_id * 100 + line_num  # Generate unique line ID
            line = Line(
                id=line_id,
                match_id=match_id,
                line_number=line_num,
                facility_id=None,
                date=None,
                time=None,
                court_number=None
            )
            self.add_line(line)
            lines.append(line)
        
        return lines

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
    config = {"db_path": "tennis_test.db"}
    db = SQLiteTennisDB(config)
    db.connect()
    print("✓ SQLite database connection successful")
    print(f"✓ Database ping: {db.ping()}")
    
    # Test basic functionality
    leagues = db.list_leagues()
    print(f"✓ Found {len(leagues)} leagues")
    
    db.disconnect()
    print("✓ Database disconnected successfully")