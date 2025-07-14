"""
Team Management Helper for SQLite Tennis Database

Handles all team-related database operations including CRUD operations,
team preferences, and team validation.

Updated to work with the new match-based scheduling system.
"""

import sqlite3
from typing import List, Optional, TYPE_CHECKING
from usta import Team, League, Facility, Match
from scheduling_state import SchedulingState

if TYPE_CHECKING:
    from tennis_db_interface import TennisDBInterface


class SQLTeamManager:
    """Helper class for managing team operations in SQLite database"""
    
    def __init__(self, cursor: sqlite3.Cursor, db_instance: 'TennisDBInterface') -> None:
        """
        Initialize SQLTeamManager
        
        Args:
            cursor: SQLite cursor for database operations
            db_instance: Reference to main database instance for accessing other managers
        """
        self.cursor = cursor
        self.db = db_instance
    
    def _dictify(self, row: Optional[sqlite3.Row]) -> dict:
        """Convert sqlite Row object to dictionary"""
        return dict(row) if row else {}
    
    def add_team(self, team: Team) -> bool:
        """Add a new team to the database"""
        if not isinstance(team, Team):
            raise TypeError(f"Expected Team object, got: {type(team)}")
        
        try:
            # Check if team ID already exists
            existing = self.get_team(team.id)
            if existing:
                raise ValueError(f"Team with ID {team.id} already exists")
            
            # Verify league exists
            if not self.db.league_manager.get_league(team.league.id):
                raise ValueError(f"League with ID {team.league.id} does not exist")
            
            # Verify all preferred facilities exist
            for facility in team.preferred_facilities:
                if not self.db.facility_manager.get_facility(facility.id):
                    raise ValueError(f"Facility with ID {facility.id} does not exist")
            
            # Convert preferred_days list to comma-separated string for storage
            preferred_days_str = ','.join(team.preferred_days) if team.preferred_days else ''
            
            # Insert team record (without home_facility_id)
            query = """
                INSERT INTO teams (id, name, league_id, captain, preferred_days)
                VALUES (?, ?, ?, ?, ?)
            """
            params = (
                team.id,
                team.name,
                team.league.id,
                team.captain,
                preferred_days_str
            )
            
            description = f"Add team {team.id}: {team.name} (League: {team.league.name})"
            
            if hasattr(self.db, 'execute_operation'):
                self.db.execute_operation('add_team', query, params, description)
            else:
                self.cursor.execute(query, params)
            
            # Insert preferred facilities
            self._add_team_preferred_facilities(team.id, team.preferred_facilities)
            
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding team: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding team: {e}")
        return True
    
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
            league = self.db.league_manager.get_league(team_data['league_id'])
            if not league:
                raise RuntimeError(f"League {team_data['league_id']} not found for team {team_id}")
            
            # Get preferred facilities
            preferred_facilities = self._get_team_preferred_facilities(team_id)
            if not preferred_facilities:
                raise RuntimeError(f"No preferred facilities found for team {team_id}")
            
            # Convert preferred_days from string to list
            preferred_days = []
            if team_data.get('preferred_days'):
                preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
            
            return Team(
                id=team_data['id'],
                name=team_data['name'],
                league=league,
                preferred_facilities=preferred_facilities,
                captain=team_data.get('captain'),
                preferred_days=preferred_days
            )
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting team {team_id}: {e}")

    def list_teams(self, league: Optional['League'] = None) -> List[Team]:

        """List all teams, optionally filtered by league"""

        if league is not None and not hasattr(league, 'id'):
            raise TypeError(f"Expected League object, got: {type(league)}")
        
        league_id = league.id if league else None

        if league_id is not None and (not isinstance(league_id, int) or league_id <= 0):
            raise ValueError(f"League ID must be a positive integer, got: {league_id}")
        
        try:
            if league_id:
                # Verify league exists
                if not self.db.league_manager.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                self.cursor.execute("SELECT * FROM teams WHERE league_id = ? ORDER BY name", (league_id,))
            else:
                self.cursor.execute("SELECT * FROM teams ORDER BY name")
            
            teams = []
            for row in self.cursor.fetchall():
                team_data = self._dictify(row)
                
                # Get the league object
                league = self.db.league_manager.get_league(team_data['league_id'])
                if not league:
                    raise RuntimeError(f"Data integrity error: League with ID {team_data['league_id']} not found")
                
                # Get preferred facilities
                preferred_facilities = self._get_team_preferred_facilities(team_data['id'])
                if not preferred_facilities:
                    raise RuntimeError(f"Data integrity error: No preferred facilities found for team {team_data['id']}")
                
                # Convert comma-separated string back to list
                preferred_days = []
                if team_data.get('preferred_days'):
                    preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
                
                try:
                    # Create Team object with all required fields
                    new_team = Team(
                        id=team_data['id'],
                        name=team_data['name'],
                        league=league,
                        preferred_facilities=preferred_facilities,
                        captain=team_data.get('captain'),
                        preferred_days=preferred_days
                    )
                    teams.append(new_team)
                except Exception as team_error:
                    print(f"DEBUG: Error creating team: {team_error}")
                    print(f"DEBUG: team_data = {team_data}")
                    raise
            
            return teams
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing teams: {e}")

    def update_team(self, team: Team) -> bool:
        """Update an existing team in the database"""
        if not isinstance(team, Team):
            raise TypeError(f"Expected Team object, got: {type(team)}")
        
        try:
            # Check if team exists
            existing_team = self.get_team(team.id)
            if not existing_team:
                raise ValueError(f"Team with ID {team.id} does not exist")
            
            # Verify league exists
            if not self.db.league_manager.get_league(team.league.id):
                raise ValueError(f"League with ID {team.league.id} does not exist")
            
            # Verify all preferred facilities exist
            for facility in team.preferred_facilities:
                if not self.db.facility_manager.get_facility(facility.id):
                    raise ValueError(f"Facility with ID {facility.id} does not exist")
            
            # Convert preferred_days list to comma-separated string for storage
            preferred_days_str = ','.join(team.preferred_days) if team.preferred_days else ''
            
            # Update team record (without home_facility_id)
            query = """
                UPDATE teams 
                SET name = ?, league_id = ?, captain = ?, preferred_days = ?
                WHERE id = ?
            """
            params = (
                team.name,
                team.league.id,
                team.captain,
                preferred_days_str,
                team.id
            )
            
            description = f"Update team {team.id}: {team.name} (League: {team.league.name})"
            
            if hasattr(self.db, 'execute_operation'):
                self.db.execute_operation('update_team', query, params, description)
            else:
                self.cursor.execute(query, params)
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to update team {team.id}")
            
            # Update preferred facilities
            self._update_team_preferred_facilities(team.id, team.preferred_facilities)
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error updating team: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating team: {e}")
        return True

    def delete_team(self, team_id: int) -> bool:
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
            query = "DELETE FROM teams WHERE id = ?"
            params = (team_id,)
            description = f"Delete team {team_id}: {existing_team.name}"
            
            if hasattr(self.db, 'execute_operation'):
                self.db.execute_operation('delete_team', query, params, description)
            else:
                self.cursor.execute(query, params)
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete team {team_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting team {team_id}: {e}")
        return True

    def get_teams_by_facility(self, facility_id: int) -> List[Team]:
        """Get all teams that have a specific facility in their preferred facilities"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Query teams that have this facility in their preferred list
            query = """
                SELECT DISTINCT t.* FROM teams t
                JOIN team_preferred_facilities tpf ON t.id = tpf.team_id
                WHERE tpf.facility_id = ?
                ORDER BY t.name
            """
            self.cursor.execute(query, (facility_id,))
            
            teams = []
            for row in self.cursor.fetchall():
                team_data = self._dictify(row)
                league = self.db.league_manager.get_league(team_data['league_id'])
                preferred_facilities = self._get_team_preferred_facilities(team_data['id'])
                
                if league and preferred_facilities:
                    # Convert preferred_days
                    preferred_days = []
                    if team_data.get('preferred_days'):
                        preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
                    
                    teams.append(Team(
                        id=team_data['id'],
                        name=team_data['name'],
                        league=league,
                        preferred_facilities=preferred_facilities,
                        captain=team_data.get('captain'),
                        preferred_days=preferred_days
                    ))
            return teams
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting teams by facility: {e}")

    def get_teams_by_facility_name(self, facility_name: str, exact_match: bool = True) -> List[Team]:
        """Get all teams that use a specific facility name as their home"""
        if not isinstance(facility_name, str) or not facility_name.strip():
            raise ValueError("Facility name must be a non-empty string")
        
        try:
            # Get facilities that match the name
            facilities = self.db.facility_manager.get_facilities_by_name(facility_name, exact_match)
            
            if not facilities:
                return []
            
            # Get teams for all matching facilities
            all_teams = []
            for facility in facilities:
                teams = self.get_teams_by_facility(facility.id)
                all_teams.extend(teams)
            
            # Remove duplicates (in case a team somehow matches multiple facilities)
            seen_ids = set()
            unique_teams = []
            for team in all_teams:
                if team.id not in seen_ids:
                    unique_teams.append(team)
                    seen_ids.add(team.id)
            
            return sorted(unique_teams, key=lambda t: t.name)
            
        except Exception as e:
            raise RuntimeError(f"Database error getting teams by facility name: {e}")


    def check_team_date_conflict(self, team: Team, date: str) -> bool:
        """
        Check if a team already has a match scheduled on the given date.

        Args:
            team: Team to check
            date: Date to check (YYYY-MM-DD format)

        Returns:
            True if there's a conflict (team already scheduled on this date), False if no conflict
        """

        if not isinstance(team, Team):
            raise TypeError(f"Expected Team object, got: {type(team)}")
        if not isinstance(date, str) or not date.strip():
            raise ValueError("Date must be a non-empty string in YYYY-MM-DD format")
        
        try:
            # Check database first
            query = """
                SELECT COUNT(*) as count
                FROM matches 
                WHERE (home_team_id = ? OR visitor_team_id = ?)
                AND date = ?
                AND status = 'scheduled'
            """
            params = [team.id, team.id, date]
            
            self.cursor.execute(query, params)
            row = self.cursor.fetchone()
            database_conflict = row and row['count'] > 0

            if database_conflict:
                print(f"DEBUG-d: Team {team.id} has a database conflict on {date}")
            
            # Also check scheduling state if in dry run mode
            state_conflict = False
            if self.db.dry_run_active and self.db.scheduling_state:
                state_conflict = self.db.scheduling_state.has_team_conflict(team.id, date)
            if state_conflict:
                print(f"DEBUG-s: Team {team.id} has a state conflict on {date} in dry run mode")
                print(f"DEBUG: Team bookings: {[(k, v) for k, v in self.db.scheduling_state.team_bookings.items() if k[0] == team.id]}")
            
            # Return true if either has a conflict
            return database_conflict or state_conflict
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error checking team date conflict: {e}")
        


    # def check_team_date_conflict(self, team: Team, date: str) -> bool:
    #     """
    #     Check if a team already has a match scheduled on the given date.

    #     Args:
    #         team: Team to check
    #         date: Date to check (YYYY-MM-DD format)
    #         exclude_match: Optional match to exclude from the check

    #     Returns:
    #         True if there's a conflict (team already scheduled on this date), False if no conflict
    #     """

    #     try:
    #         # Check the scheduling state first
    #         if self.db.dry_run_active:
    #             state = self.db.scheduling_state
    #             if state.has_team_conflict(team.id, date):
    #                 return True

    #         # Query the database
    #         query = """
    #             SELECT COUNT(*) as count
    #             FROM matches 
    #             WHERE (home_team_id = ? OR visitor_team_id = ?)
    #             AND date = ?
    #             AND status = 'scheduled'
    #         """
    #         params = [team.id, team.id, date]
            
    #         # if exclude_match is not None:
    #         #     query += " AND id != ?"
    #         #     params.append(exclude_match.id)
                
    #         self.cursor.execute(query, params)
    #         row = self.cursor.fetchone()
    #         if row is None:
    #             return False
    #         count = row['count']
    #         return count > 0
            
    #     except sqlite3.Error as e:
    #         raise RuntimeError(f"Database error checking team date conflict: {e}")

    # def get_team_date_conflicts(self, team_id: int, date: str, exclude_match_id: Optional[int] = None) -> List[dict]:
    #     """
    #     Get detailed information about team date conflicts.
        
    #     Args:
    #         team_id: Team to check
    #         date: Date to check (YYYY-MM-DD format)
    #         exclude_match_id: Optional match ID to exclude from results
            
    #     Returns:
    #         List of conflicting match details
    #     """
    #     try:
    #         query = """
    #             SELECT m.id, m.scheduled_times, m.facility_id, f.name as facility_name,
    #                    ht.name as home_team_name, vt.name as visitor_team_name,
    #                    CASE WHEN m.home_team_id = ? THEN 'home' ELSE 'visitor' END as team_role
    #             FROM matches m
    #             LEFT JOIN facilities f ON m.facility_id = f.id
    #             JOIN teams ht ON m.home_team_id = ht.id  
    #             JOIN teams vt ON m.visitor_team_id = vt.id
    #             WHERE (m.home_team_id = ? OR m.visitor_team_id = ?)
    #             AND m.date = ?
    #             AND m.status = 'scheduled'
    #         """
    #         params = [team_id, team_id, team_id, date]
            
    #         if exclude_match_id is not None:
    #             query += " AND m.id != ?"
    #             params.append(exclude_match_id)
                
    #         self.cursor.execute(query, params)
            
    #         conflicts = []
    #         for row in self.cursor.fetchall():
    #             conflict_data = self._dictify(row)
                
    #             # Parse scheduled times
    #             scheduled_times = []
    #             if conflict_data.get('scheduled_times'):
    #                 try:
    #                     import json
    #                     times = json.loads(conflict_data['scheduled_times'])
    #                     if isinstance(times, list):
    #                         scheduled_times = times
    #                 except (json.JSONDecodeError, TypeError):
    #                     pass
                
    #             conflict_data['scheduled_times_list'] = scheduled_times
    #             conflicts.append(conflict_data)
            
    #         return conflicts
            
    #     except sqlite3.Error as e:
    #         raise RuntimeError(f"Database error getting team date conflicts: {e}")

    def check_team_facility_conflict(self, team_id: int, date: str, facility_name: str) -> bool:
        """
        Check if a team already has a match scheduled at a different facility on the given date.
        
        Args:
            team_id: Team to check
            date: Date to check (YYYY-MM-DD format)
            facility_name: Facility name being considered for scheduling
            
        Returns:
            True if there's a conflict (team already scheduled elsewhere), False if no conflict
        """
        try:
            # Get matches for this team on this date that are at facilities with different names
            query = """
                SELECT COUNT(*) as count
                FROM matches m
                LEFT JOIN facilities f ON m.facility_id = f.id
                WHERE (m.home_team_id = ? OR m.visitor_team_id = ?)
                AND m.date = ?
                AND m.status = 'scheduled'
                AND (f.name IS NOT NULL AND f.name != ? AND f.short_name != ?)
            """
            
            self.cursor.execute(query, (team_id, team_id, date, facility_name, facility_name))
            row = self.cursor.fetchone()
            if row is None:
                return False
            count = row['count']
            return count > 0
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error checking team facility conflict: {e}")

    def _get_team_preferred_facilities(self, team_id: int) -> List[Facility]:
        """Get ordered list of preferred facilities for a team"""
        try:
            query = """
                SELECT tpf.facility_id FROM team_preferred_facilities tpf
                WHERE tpf.team_id = ?
                ORDER BY tpf.priority_order
            """
            self.cursor.execute(query, (team_id,))
            
            facilities = []
            for row in self.cursor.fetchall():
                facility_id = row['facility_id']
                facility = self.db.facility_manager.get_facility(facility_id)
                if facility:
                    facilities.append(facility)
            return facilities
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting team preferred facilities: {e}")

    def _add_team_preferred_facilities(self, team_id: int, facilities: List[Facility]) -> None:
        """Add preferred facilities for a team"""
        try:
            for i, facility in enumerate(facilities):
                query = """
                    INSERT INTO team_preferred_facilities (team_id, facility_id, priority_order)
                    VALUES (?, ?, ?)
                """
                self.cursor.execute(query, (team_id, facility.id, i + 1))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding team preferred facilities: {e}")

    def _update_team_preferred_facilities(self, team_id: int, facilities: List[Facility]) -> None:
        """Update preferred facilities for a team"""
        try:
            # Delete existing preferences
            self.cursor.execute("DELETE FROM team_preferred_facilities WHERE team_id = ?", (team_id,))
            
            # Add new preferences
            self._add_team_preferred_facilities(team_id, facilities)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating team preferred facilities: {e}")