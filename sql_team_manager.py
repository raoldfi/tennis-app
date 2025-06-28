"""
Team Management Helper for SQLite Tennis Database

Handles all team-related database operations including CRUD operations,
team preferences, and team validation.

Updated to work with the new match-based scheduling system.
"""

import sqlite3
from typing import List, Optional
from usta import Team, League, Facility, Match


class SQLTeamManager:
    """Helper class for managing team operations in SQLite database"""
    
    def __init__(self, cursor: sqlite3.Cursor, db_instance):
        """
        Initialize SQLTeamManager
        
        Args:
            cursor: SQLite cursor for database operations
            db_instance: Reference to main database instance for accessing other managers
        """
        self.cursor = cursor
        self.db = db_instance
    
    def _dictify(self, row) -> dict:
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
            
            # Verify facility exists
            if not self.db.facility_manager.get_facility(team.home_facility.id):
                raise ValueError(f"Facility with ID {team.home_facility.id} does not exist")
            
            # Convert preferred_days list to comma-separated string for storage
            preferred_days_str = ','.join(team.preferred_days) if team.preferred_days else ''
            
            self.cursor.execute("""
                INSERT INTO teams (id, name, league_id, home_facility_id, captain, preferred_days)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                team.id,
                team.name,
                team.league.id,
                team.home_facility.id,
                team.captain,
                preferred_days_str
            ))
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
            
            # Get the facility object
            facility = self.db.facility_manager.get_facility(team_data['home_facility_id'])
            if not facility:
                raise RuntimeError(f"Facility {team_data['home_facility_id']} not found for team {team_id}")
            
            # Convert preferred_days from string to list
            preferred_days = []
            if team_data.get('preferred_days'):
                preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
            
            return Team(
                id=team_data['id'],
                name=team_data['name'],
                league=league,
                home_facility=facility,
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
                
                # Get the facility object using home_facility_id
                facility = self.db.facility_manager.get_facility(team_data['home_facility_id'])
                if not facility:
                    raise RuntimeError(f"Data integrity error: Facility with ID {team_data['home_facility_id']} not found")
                
                # Convert comma-separated string back to list
                preferred_days = []
                if team_data.get('preferred_days'):
                    preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
                
                # DEBUG: Print team data before creating Team object
                print(f"DEBUG: Creating team from data: {team_data}")
                print(f"DEBUG: team_data['id'] = {team_data.get('id', 'MISSING')} (type: {type(team_data.get('id', 'MISSING'))})")
                print(f"DEBUG: league = {league} (ID: {getattr(league, 'id', 'MISSING')})")
                print(f"DEBUG: facility = {facility} (ID: {getattr(facility, 'id', 'MISSING')})")

                try:
                    # Create Team object with all required fields
                    new_team = Team(
                        id=team_data['id'],
                        name=team_data['name'],
                        league=league,
                        home_facility=facility,
                        captain=team_data.get('captain'),
                        preferred_days=preferred_days
                    )
                    teams.append(new_team)
                    print(f"DEBUG: Successfully created team {new_team.name} with ID {new_team.id}")
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
            
            # Verify facility exists
            if not self.db.facility_manager.get_facility(team.home_facility.id):
                raise ValueError(f"Facility with ID {team.home_facility.id} does not exist")
            
            # Convert preferred_days list to comma-separated string for storage
            preferred_days_str = ','.join(team.preferred_days) if team.preferred_days else ''
            
            self.cursor.execute("""
                UPDATE teams 
                SET name = ?, league_id = ?, home_facility_id = ?, captain = ?, preferred_days = ?
                WHERE id = ?
            """, (
                team.name,
                team.league.id,
                team.home_facility.id,
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
            self.cursor.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            
            # Check if the deletion was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to delete team {team_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting team {team_id}: {e}")
        return True

    def get_teams_by_facility(self, facility_id: int) -> List[Team]:
        """Get all teams that use a specific facility as their home"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            self.cursor.execute("SELECT * FROM teams WHERE home_facility_id = ? ORDER BY name", (facility_id,))
            
            teams = []
            for row in self.cursor.fetchall():
                team_data = self._dictify(row)
                league = self.db.league_manager.get_league(team_data['league_id'])
                facility = self.db.facility_manager.get_facility(team_data['home_facility_id'])
                
                if league and facility:
                    # Convert preferred_days
                    preferred_days = []
                    if team_data.get('preferred_days'):
                        preferred_days = [day.strip() for day in team_data['preferred_days'].split(',') if day.strip()]
                    
                    teams.append(Team(
                        id=team_data['id'],
                        name=team_data['name'],
                        league=league,
                        home_facility=facility,
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

    def check_team_date_conflict(self, team: Team, date: str, exclude_match: Optional['Match'] = None) -> bool:
        """
        Check if a team already has a match scheduled on the given date.
        
        Args:
            team_id: Team to check
            date: Date to check (YYYY-MM-DD format)
            exclude_match_id: Optional match ID to exclude from the check (useful when rescheduling)
            
        Returns:
            True if there's a conflict (team already scheduled on this date), False if no conflict
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM matches 
                WHERE (home_team_id = ? OR visitor_team_id = ?)
                AND date = ?
                AND status = 'scheduled'
            """
            params = [team.id, team.id, date]
            
            if exclude_match is not None:
                query += " AND id != ?"
                params.append(exclude_match.id)
                
            self.cursor.execute(query, params)
            count = self.cursor.fetchone()['count']
            return count > 0
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error checking team date conflict: {e}")

    def get_team_date_conflicts(self, team_id: int, date: str, exclude_match_id: Optional[int] = None) -> List[dict]:
        """
        Get detailed information about team date conflicts.
        
        Args:
            team_id: Team to check
            date: Date to check (YYYY-MM-DD format)
            exclude_match_id: Optional match ID to exclude from results
            
        Returns:
            List of conflicting match details
        """
        try:
            query = """
                SELECT m.id, m.scheduled_times, m.facility_id, f.name as facility_name,
                       ht.name as home_team_name, vt.name as visitor_team_name,
                       CASE WHEN m.home_team_id = ? THEN 'home' ELSE 'visitor' END as team_role
                FROM matches m
                LEFT JOIN facilities f ON m.facility_id = f.id
                JOIN teams ht ON m.home_team_id = ht.id  
                JOIN teams vt ON m.visitor_team_id = vt.id
                WHERE (m.home_team_id = ? OR m.visitor_team_id = ?)
                AND m.date = ?
                AND m.status = 'scheduled'
            """
            params = [team_id, team_id, team_id, date]
            
            if exclude_match_id is not None:
                query += " AND m.id != ?"
                params.append(exclude_match_id)
                
            self.cursor.execute(query, params)
            
            conflicts = []
            for row in self.cursor.fetchall():
                conflict_data = self._dictify(row)
                
                # Parse scheduled times
                scheduled_times = []
                if conflict_data.get('scheduled_times'):
                    try:
                        import json
                        times = json.loads(conflict_data['scheduled_times'])
                        if isinstance(times, list):
                            scheduled_times = times
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                conflict_data['scheduled_times_list'] = scheduled_times
                conflicts.append(conflict_data)
            
            return conflicts
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting team date conflicts: {e}")

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
            count = self.cursor.fetchone()['count']
            return count > 0
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error checking team facility conflict: {e}")