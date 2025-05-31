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


class SQLiteTennisDB(TennisDB):
    """SQLite implementation of the TennisDB abstract base class"""
    
    def _dictify(self, row) -> dict:
        """Convert sqlite Row object to dictionary"""
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

    def _initialize_schema(self):
        """Initialize database schema with tables and constraints"""
        try:
            self.conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=20.0,
                isolation_level=None
            )
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Enable foreign key constraints
            self.cursor.execute("PRAGMA foreign_keys = ON")
            self.cursor.execute("PRAGMA journal_mode = WAL")
            self.cursor.execute("PRAGMA synchronous = NORMAL")
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
                facility_id INTEGER,
                date TEXT,
                time TEXT,
                status TEXT NOT NULL DEFAULT 'unscheduled',
                FOREIGN KEY (league_id) REFERENCES leagues(id) ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (home_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (visitor_team_id) REFERENCES teams(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE RESTRICT ON UPDATE CASCADE
            );
            """)
            
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
                pass

    def __del__(self):
        """Ensure database connection is properly closed"""
        self.close()

    # =================================================================
    # TEAM METHODS - Required by TennisDB abstract base class
    # =================================================================
    
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

    # =================================================================
    # LEAGUE METHODS - Required by TennisDB abstract base class
    # =================================================================
    
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
    
    def list_leagues(self) -> List[League]:
        """List all leagues"""
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

    # =================================================================
    # MATCH METHODS - Required by TennisDB abstract base class
    # =================================================================
    
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
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding match: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding match: {e}")

    def get_match(self, match_id: int) -> Optional[Match]:
        """Get a match by ID - CRITICAL: This method must be implemented for abstract base class"""
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
            return Match(**match_data)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")

    def list_matches(self, league_id: Optional[int] = None, include_unscheduled: bool = False) -> List[Match]:
        """List all matches, optionally filtered by league and scheduling status"""
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
            
            self.cursor.execute(query, params)
            
            matches = []
            for row in self.cursor.fetchall():
                match_data = self._dictify(row)
                # Remove status field as it's not part of the Match dataclass
                match_data.pop('status', None)
                matches.append(Match(**match_data))
            
            return matches
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing matches: {e}")

    def unschedule_match(self, match_id: int) -> None:
        """Unschedule a match (remove date, time, facility) but keep the match record"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
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
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to unschedule match {match_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error unscheduling match {match_id}: {e}")

    def schedule_match(self, match_id: int, facility_id: int, date: str, time: str) -> None:
        """Schedule an unscheduled match by setting date, time, and facility"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            # Check if match exists
            existing_match = self.get_match(match_id)
            if not existing_match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Verify facility exists
            if not self.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Validate date and time formats (basic validation)
            if not date or not time:
                raise ValueError("Date and time are required")
            
            # Update the match to scheduled state
            self.cursor.execute("""
                UPDATE matches 
                SET facility_id = ?, date = ?, time = ?, status = 'scheduled'
                WHERE id = ?
            """, (facility_id, date, time, match_id))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to schedule match {match_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error scheduling match {match_id}: {e}")

    def delete_match(self, match_id: int) -> None:
        """Completely delete a match from the database"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            # Check if match exists
            existing_match = self.get_match(match_id)
            if not existing_match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Delete the match
            self.cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete match {match_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting match {match_id}: {e}")

    def update_match(self, match: Match) -> None:
        """Update an existing match in the database"""
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

    def get_unscheduled_matches(self, league_id: Optional[int] = None) -> List[Match]:
        """Get all unscheduled matches, optionally filtered by league"""
        return self.list_matches(league_id=league_id, include_unscheduled=True)

    # =================================================================
    # FACILITY METHODS - Required by TennisDB abstract base class
    # =================================================================
    
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
                location=facility_data['location']
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
                SET name = ?, location = ?
                WHERE id = ?
            """, (
                facility.name,
                facility.location,
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

    # =================================================================
    # HELPER METHODS FOR FACILITIES
    # =================================================================
    
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

    # =================================================================
    # UTILITY METHODS
    # =================================================================
    
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
                    obj = Match(**record)
                elif table == "facilities":
                    # For facilities, use the from_yaml_dict method to handle complex structure
                    obj = Facility.from_yaml_dict(record)
                
                insert_fn(obj)
                
            except Exception as e:
                raise ValueError(f"Failed to process record {i} in table '{table}': {e}")

    def calculate_pairings(self, league_id: int) -> List[tuple]:
        """Calculate pairings for teams in a league"""
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

    # Additional methods for listing USTA constants
    def list_sections(self) -> List[str]:
        return USTA_SECTIONS.copy()

    def list_regions(self) -> List[str]:
        return USTA_REGIONS.copy()

    def list_age_groups(self) -> List[str]:
        return USTA_AGE_GROUPS.copy()

    def list_divisions(self) -> List[str]:
        return USTA_DIVISIONS.copy()


# Command-line interface
def main():
    parser = argparse.ArgumentParser(description="Manage tennis scheduling database")
    parser.add_argument("--db", "--database", dest="db_path", required=True, help="Path to SQLite database file")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List entities from the database")
    list_parser.add_argument("table", choices=["teams", "leagues", "matches", "sections", "regions", "age-groups", "facilities", "divisions"], help="Type of entity to list")
    list_parser.add_argument("--league-id", type=int, help="Filter teams or matches by league ID")

    # Load command  
    load_parser = subparsers.add_parser("load", help="Load entities from YAML file")
    load_parser.add_argument("table", choices=["teams", "leagues", "matches", "facilities"], help="Type of entity to load")
    load_parser.add_argument("--file", "-f", dest="yaml_path", required=True, help="Path to the YAML file containing data")

    # Calculate pairings command
    pairings_parser = subparsers.add_parser("calculate-pairings", help="Calculate team pairings for a league")
    pairings_parser.add_argument("--league-id", type=int, required=True, help="League ID to calculate pairings for")

    # Unschedule match command
    unschedule_parser = subparsers.add_parser("unschedule-match", help="Unschedule a match (remove date/time/facility)")
    unschedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to unschedule")

    # Schedule match command
    schedule_parser = subparsers.add_parser("schedule-match", help="Schedule an unscheduled match")
    schedule_parser.add_argument("--match-id", type=int, required=True, help="Match ID to schedule")
    schedule_parser.add_argument("--facility-id", type=int, required=True, help="Facility ID for the match")
    schedule_parser.add_argument("--date", required=True, help="Match date (YYYY-MM-DD)")
    schedule_parser.add_argument("--time", required=True, help="Match time (HH:MM)")

    try:
        args = parser.parse_args()
        
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
                        results = db.list_teams(league_id=args.league_id)
                    elif args.table == "matches":
                        results = db.list_matches(league_id=args.league_id, include_unscheduled=args.include_unscheduled)
                    else:
                        method = getattr(db, f"list_{args.table}")
                        results = method()

                # Convert dataclass objects to dicts for JSON serialization
                if args.table in ["teams", "leagues", "matches", "facilities"]:
                    if args.table == "teams":
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
                    else:
                        results = [obj.__dict__ if hasattr(obj, '__dict__') else obj for obj in results]

                print(json.dumps(results, indent=2))
                    
            except Exception as e:
                print(f"Error: Failed to list {args.table}: {e}", file=sys.stderr)
                sys.exit(1)
                
        elif args.command == "load":
            if not args.yaml_path or not args.yaml_path.strip():
                print("Error: YAML path cannot be empty", file=sys.stderr)
                sys.exit(1)
            
            try:
                db.load_yaml(args.table, args.yaml_path)
                print(f"Successfully loaded {args.table} from {args.yaml_path}")
            except Exception as e:
                print(f"Error: Failed to load YAML - {e}", file=sys.stderr)
                sys.exit(1)
                
        elif args.command == "calculate-pairings":
            if args.league_id <= 0:
                print("Error: League ID must be a positive integer", file=sys.stderr)
                sys.exit(1)
            
            try:
                # Get league information first
                league = db.get_league(args.league_id)
                if not league:
                    print(f"Error: League with ID {args.league_id} not found", file=sys.stderr)
                    sys.exit(1)
                
                # Calculate pairings
                pairings = db.calculate_pairings(args.league_id)
                
                # Format and display results
                pairing_results = []
                for i, (home_team, away_team) in enumerate(pairings, 1):
                    pairing_dict = {
                        'match_number': i,
                        'home_team_id': home_team.id,
                        'home_team_name': home_team.name,
                        'visitor_team_id': away_team.id,
                        'visitor_team_name': away_team.name
                    }
                    pairing_results.append(pairing_dict)
                
                print(json.dumps(pairing_results, indent=2))
                
            except Exception as e:
                print(f"Error: Failed to calculate pairings - {e}", file=sys.stderr)
                sys.exit(1)
        
        elif args.command == "unschedule-match":
            if args.match_id <= 0:
                print("Error: Match ID must be a positive integer", file=sys.stderr)
                sys.exit(1)
            
            try:
                db.unschedule_match(args.match_id)
                print(f"Successfully unscheduled match {args.match_id}")
            except Exception as e:
                print(f"Error: Failed to unschedule match - {e}", file=sys.stderr)
                sys.exit(1)
        
        elif args.command == "schedule-match":
            if args.match_id <= 0:
                print("Error: Match ID must be a positive integer", file=sys.stderr)
                sys.exit(1)
            if args.facility_id <= 0:
                print("Error: Facility ID must be a positive integer", file=sys.stderr)
                sys.exit(1)
            
            try:
                db.schedule_match(args.match_id, args.facility_id, args.date, args.time)
                print(f"Successfully scheduled match {args.match_id} for {args.date} at {args.time}")
            except Exception as e:
                print(f"Error: Failed to schedule match - {e}", file=sys.stderr)
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