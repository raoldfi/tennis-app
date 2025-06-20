"""
League Management Helper for SQLite Tennis Database

Handles all league-related database operations including CRUD operations,
league configuration, and league validation.

Updated to work without Line class references.
"""

import sqlite3
from typing import List, Optional
from usta import League


class SQLLeagueManager:
    """Helper class for managing league operations in SQLite database"""
    
    def __init__(self, cursor: sqlite3.Cursor):
        """
        Initialize SQLLeagueManager
        
        Args:
            cursor: SQLite cursor for database operations
        """
        self.cursor = cursor
    
    def _dictify(self, row) -> dict:
        """Convert sqlite Row object to dictionary"""
        return dict(row) if row else {}
    
    def add_league(self, league: League) -> bool:
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
        return True
    
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

    def update_league(self, league: League) -> bool:
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
        return True

    def delete_league(self, league_id: int) -> bool:
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
        return True

    def get_leagues_by_year(self, year: int) -> List[League]:
        """Get all leagues for a specific year"""
        if not isinstance(year, int) or year < 1900 or year > 2100:
            raise ValueError(f"Year must be between 1900 and 2100, got: {year}")
        
        try:
            self.cursor.execute("SELECT * FROM leagues WHERE year = ? ORDER BY name", (year,))
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
            raise RuntimeError(f"Database error getting leagues by year: {e}")

    def get_leagues_by_section_region(self, section: str, region: str) -> List[League]:
        """Get all leagues for a specific section and region"""
        if not isinstance(section, str) or not section.strip():
            raise ValueError("Section must be a non-empty string")
        if not isinstance(region, str) or not region.strip():
            raise ValueError("Region must be a non-empty string")
        
        try:
            self.cursor.execute(
                "SELECT * FROM leagues WHERE section = ? AND region = ? ORDER BY year DESC, name",
                (section, region)
            )
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
            raise RuntimeError(f"Database error getting leagues by section/region: {e}")

    def get_active_leagues(self, current_date: str = None) -> List[League]:
        """
        Get all leagues that are currently active
        
        Args:
            current_date: Current date in YYYY-MM-DD format. If None, uses today.
            
        Returns:
            List of active leagues
        """
        if current_date is None:
            from datetime import date
            current_date = date.today().strftime('%Y-%m-%d')
        
        try:
            self.cursor.execute("""
                SELECT * FROM leagues 
                WHERE (start_date IS NULL OR start_date <= ?)
                AND (end_date IS NULL OR end_date >= ?)
                ORDER BY year DESC, name
            """, (current_date, current_date))
            
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
            raise RuntimeError(f"Database error getting active leagues: {e}")

    def get_league_scheduling_status(self, league_id: int) -> dict:
        """Get scheduling statistics for a league (updated for match-based scheduling)"""
        try:
            # Verify league exists
            league = self.get_league(league_id)
            if not league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Get match counts
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE league_id = ?", (league_id,))
            total_matches = self.cursor.fetchone()['count']
            
            self.cursor.execute("SELECT COUNT(*) as count FROM matches WHERE league_id = ? AND status = 'scheduled'", (league_id,))
            scheduled_matches = self.cursor.fetchone()['count']
            
            unscheduled_matches = total_matches - scheduled_matches
            
            # Get scheduled times statistics
            import json
            total_scheduled_times = 0
            partially_scheduled_matches = 0
            fully_scheduled_matches = 0
            
            self.cursor.execute("""
                SELECT scheduled_times 
                FROM matches 
                WHERE league_id = ? AND scheduled_times IS NOT NULL
            """, (league_id,))
            
            for row in self.cursor.fetchall():
                if row['scheduled_times']:
                    try:
                        times = json.loads(row['scheduled_times'])
                        if isinstance(times, list):
                            num_times = len(times)
                            total_scheduled_times += num_times
                            
                            # Check if match is fully or partially scheduled
                            expected_lines = league.num_lines_per_match
                            if num_times == expected_lines:
                                fully_scheduled_matches += 1
                            elif 0 < num_times < expected_lines:
                                partially_scheduled_matches += 1
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            expected_total_times = total_matches * league.num_lines_per_match
            
            return {
                'league_id': league_id,
                'league_name': league.name,
                'total_matches': total_matches,
                'scheduled_matches': scheduled_matches,
                'unscheduled_matches': unscheduled_matches,
                'fully_scheduled_matches': fully_scheduled_matches,
                'partially_scheduled_matches': partially_scheduled_matches,
                'total_scheduled_times': total_scheduled_times,
                'expected_total_times': expected_total_times,
                'scheduling_completion_percentage': round((total_scheduled_times / expected_total_times * 100) if expected_total_times > 0 else 0, 2)
            }
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting league scheduling status: {e}")