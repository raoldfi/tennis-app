"""
Combined Match and Line Management Helper for SQLite Tennis Database

Handles all match and line-related database operations including CRUD operations,
match validation, line scheduling, and conflict detection. Since lines are always
associated with matches, this combined approach provides better cohesion.
"""

import sqlite3
from typing import List, Optional, Dict, Any
from collections import defaultdict
from usta import Match, Line


class SQLMatchManager:
    """Helper class for managing match and line operations in SQLite database"""
    
    def __init__(self, cursor: sqlite3.Cursor, db_instance):
        """
        Initialize SQLMatchManager
        
        Args:
            cursor: SQLite cursor for database operations
            db_instance: Reference to main database instance for accessing other managers
        """
        self.cursor = cursor
        self.db = db_instance
    
    def _dictify(self, row) -> dict:
        """Convert sqlite Row object to dictionary"""
        return dict(row) if row else {}
    
    # ========== Match Management Methods ==========
    
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
            if not self.db.league_manager.get_league(match.league_id):
                raise ValueError(f"League with ID {match.league_id} does not exist")
            
            # Verify teams exist
            if not self.db.team_manager.get_team(match.home_team_id):
                raise ValueError(f"Home team with ID {match.home_team_id} does not exist")
            if not self.db.team_manager.get_team(match.visitor_team_id):
                raise ValueError(f"Visitor team with ID {match.visitor_team_id} does not exist")
            
            # Verify teams are in the same league
            home_team = self.db.team_manager.get_team(match.home_team_id)
            visitor_team = self.db.team_manager.get_team(match.visitor_team_id)
            if home_team.league.id != match.league_id:
                raise ValueError(f"Home team {match.home_team_id} is not in league {match.league_id}")
            if visitor_team.league.id != match.league_id:
                raise ValueError(f"Visitor team {match.visitor_team_id} is not in league {match.league_id}")
            
            # Determine if match is scheduled or unscheduled
            is_scheduled = all([match.facility_id, match.date, match.time])
            status = 'scheduled' if is_scheduled else 'unscheduled'
            
            # Verify facility exists if provided
            if match.facility_id and not self.db.facility_manager.get_facility(match.facility_id):
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
                if not self.db.league_manager.get_league(league_id):
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
            if not self.db.league_manager.get_league(match.league_id):
                raise ValueError(f"League with ID {match.league_id} does not exist")
            if not self.db.team_manager.get_team(match.home_team_id):
                raise ValueError(f"Home team with ID {match.home_team_id} does not exist")
            if not self.db.team_manager.get_team(match.visitor_team_id):
                raise ValueError(f"Visitor team with ID {match.visitor_team_id} does not exist")
            
            # Verify facility exists if provided
            if match.facility_id and not self.db.facility_manager.get_facility(match.facility_id):
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

    def get_unscheduled_matches(self, league_id: Optional[int] = None) -> List[Match]:
        """Get all unscheduled matches, optionally filtered by league"""
        return self.list_matches(league_id=league_id, include_unscheduled=True)

    def get_matches_by_team(self, team_id: int, include_unscheduled: bool = False) -> List[Match]:
        """Get all matches for a specific team (home or visitor)"""
        if not isinstance(team_id, int) or team_id <= 0:
            raise ValueError(f"Team ID must be a positive integer, got: {team_id}")
        
        try:
            # Verify team exists
            if not self.db.team_manager.get_team(team_id):
                raise ValueError(f"Team with ID {team_id} does not exist")
            
            where_conditions = ["(home_team_id = ? OR visitor_team_id = ?)"]
            params = [team_id, team_id]
            
            if not include_unscheduled:
                where_conditions.append("status = 'scheduled'")
            
            query = "SELECT * FROM matches WHERE " + " AND ".join(where_conditions)
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
            raise RuntimeError(f"Database error getting matches by team: {e}")

    def get_matches_by_facility(self, facility_id: int, start_date: Optional[str] = None, 
                               end_date: Optional[str] = None) -> List[Match]:
        """Get all matches scheduled at a specific facility within a date range"""
        if not isinstance(facility_id, int) or facility_id <= 0:
            raise ValueError(f"Facility ID must be a positive integer, got: {facility_id}")
        
        try:
            # Verify facility exists
            if not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            where_conditions = ["facility_id = ?", "status = 'scheduled'"]
            params = [facility_id]
            
            if start_date:
                where_conditions.append("date >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("date <= ?")
                params.append(end_date)
            
            query = "SELECT * FROM matches WHERE " + " AND ".join(where_conditions)
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
            raise RuntimeError(f"Database error getting matches by facility: {e}")

    def get_matches_by_date_range(self, start_date: str, end_date: str, 
                                 league_id: Optional[int] = None) -> List[Match]:
        """Get all matches within a specific date range"""
        try:
            where_conditions = ["date >= ?", "date <= ?", "status = 'scheduled'"]
            params = [start_date, end_date]
            
            if league_id:
                # Verify league exists
                if not self.db.league_manager.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                where_conditions.append("league_id = ?")
                params.append(league_id)
            
            query = "SELECT * FROM matches WHERE " + " AND ".join(where_conditions)
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
            raise RuntimeError(f"Database error getting matches by date range: {e}")

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

    def get_match_count_by_status(self, league_id: Optional[int] = None) -> dict:
        """Get count of matches by their scheduling status"""
        try:
            where_conditions = []
            params = []
            
            if league_id:
                # Verify league exists
                if not self.db.league_manager.get_league(league_id):
                    raise ValueError(f"League with ID {league_id} does not exist")
                where_conditions.append("league_id = ?")
                params.append(league_id)
            
            base_query = "SELECT COUNT(*) as count FROM matches"
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Get total count
            self.cursor.execute(base_query + where_clause, params)
            total_matches = self.cursor.fetchone()['count']
            
            # Get scheduled count
            scheduled_conditions = where_conditions + ["status = 'scheduled'"]
            scheduled_where = " WHERE " + " AND ".join(scheduled_conditions)
            scheduled_params = params + ['scheduled']
            self.cursor.execute(base_query + scheduled_where, scheduled_params)
            scheduled_matches = self.cursor.fetchone()['count']
            
            # Get unscheduled count
            unscheduled_conditions = where_conditions + ["status = 'unscheduled'"]
            unscheduled_where = " WHERE " + " AND ".join(unscheduled_conditions)
            unscheduled_params = params + ['unscheduled']
            self.cursor.execute(base_query + unscheduled_where, unscheduled_params)
            unscheduled_matches = self.cursor.fetchone()['count']
            
            return {
                'total_matches': total_matches,
                'scheduled_matches': scheduled_matches,
                'unscheduled_matches': unscheduled_matches
            }
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting match count by status: {e}")

    def get_matches_on_date(self, date: str, facility_id: Optional[int] = None) -> List[Match]:
        """Get all matches scheduled on a specific date"""
        try:
            where_conditions = ["date = ?", "status = 'scheduled'"]
            params = [date]
            
            if facility_id:
                # Verify facility exists
                if not self.db.facility_manager.get_facility(facility_id):
                    raise ValueError(f"Facility with ID {facility_id} does not exist")
                where_conditions.append("facility_id = ?")
                params.append(facility_id)
            
            query = "SELECT * FROM matches WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY time"
            
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
            raise RuntimeError(f"Database error getting matches on date: {e}")

    # ========== Line Management Methods ==========
    
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
            if line.facility_id and not self.db.facility_manager.get_facility(line.facility_id):
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
            
            if line.facility_id and not self.db.facility_manager.get_facility(line.facility_id):
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

    def get_scheduled_lines(self, facility_id: Optional[int] = None, 
                          date: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Line]:
        """Get all scheduled lines with optional filters"""
        try:
            where_conditions = ["facility_id IS NOT NULL", "date IS NOT NULL", "time IS NOT NULL"]
            params = []
            
            if facility_id is not None:
                where_conditions.append("facility_id = ?")
                params.append(facility_id)
            
            if date is not None:
                where_conditions.append("date = ?")
                params.append(date)
            elif start_date and end_date:
                where_conditions.append("date >= ? AND date <= ?")
                params.extend([start_date, end_date])
            
            query = "SELECT * FROM lines WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY date, time, facility_id, line_number"
            
            self.cursor.execute(query, params)
            
            lines = []
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                lines.append(Line(**line_data))
            
            return lines
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting scheduled lines: {e}")

    def get_unscheduled_lines(self, match_id: Optional[int] = None, 
                            league_id: Optional[int] = None) -> List[Line]:
        """Get all unscheduled lines with optional filters"""
        try:
            if league_id and match_id:
                raise ValueError("Cannot filter by both match_id and league_id")
            
            if league_id:
                # Get unscheduled lines for all matches in a league
                query = """
                    SELECT l.* FROM lines l
                    JOIN matches m ON l.match_id = m.id
                    WHERE m.league_id = ? 
                    AND (l.facility_id IS NULL OR l.date IS NULL OR l.time IS NULL)
                    ORDER BY l.match_id, l.line_number
                """
                params = [league_id]
            elif match_id:
                # Get unscheduled lines for a specific match
                query = """
                    SELECT * FROM lines 
                    WHERE match_id = ? 
                    AND (facility_id IS NULL OR date IS NULL OR time IS NULL)
                    ORDER BY line_number
                """
                params = [match_id]
            else:
                # Get all unscheduled lines
                query = """
                    SELECT * FROM lines 
                    WHERE facility_id IS NULL OR date IS NULL OR time IS NULL
                    ORDER BY match_id, line_number
                """
                params = []
            
            self.cursor.execute(query, params)
            
            lines = []
            for row in self.cursor.fetchall():
                line_data = self._dictify(row)
                lines.append(Line(**line_data))
            
            return lines
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting unscheduled lines: {e}")

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

    def get_lines_by_match(self, match_id: int) -> List[Line]:
        """Get all lines for a specific match"""
        return self.list_lines(match_id=match_id)

    def get_lines_count_by_status(self, match_id: Optional[int] = None, 
                                league_id: Optional[int] = None) -> Dict[str, int]:
        """Get count of lines by their scheduling status"""
        try:
            base_conditions = []
            base_params = []
            
            if match_id and league_id:
                raise ValueError("Cannot filter by both match_id and league_id")
            
            if match_id:
                base_conditions.append("match_id = ?")
                base_params.append(match_id)
            elif league_id:
                base_conditions.append("match_id IN (SELECT id FROM matches WHERE league_id = ?)")
                base_params.append(league_id)
            
            base_where = " WHERE " + " AND ".join(base_conditions) if base_conditions else ""
            
            # Get total count
            self.cursor.execute(f"SELECT COUNT(*) as count FROM lines{base_where}", base_params)
            total_lines = self.cursor.fetchone()['count']
            
            # Get scheduled count
            scheduled_conditions = base_conditions + [
                "facility_id IS NOT NULL", 
                "date IS NOT NULL", 
                "time IS NOT NULL"
            ]
            scheduled_where = " WHERE " + " AND ".join(scheduled_conditions)
            self.cursor.execute(f"SELECT COUNT(*) as count FROM lines{scheduled_where}", base_params)
            scheduled_lines = self.cursor.fetchone()['count']
            
            # Get unscheduled count
            unscheduled_conditions = base_conditions + [
                "(facility_id IS NULL OR date IS NULL OR time IS NULL)"
            ]
            unscheduled_where = " WHERE " + " AND ".join(unscheduled_conditions)
            self.cursor.execute(f"SELECT COUNT(*) as count FROM lines{unscheduled_where}", base_params)
            unscheduled_lines = self.cursor.fetchone()['count']
            
            return {
                'total_lines': total_lines,
                'scheduled_lines': scheduled_lines,
                'unscheduled_lines': unscheduled_lines
            }
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting line count by status: {e}")

    def schedule_line(self, line_id: int, facility_id: int, date: str, time: str, 
                     court_number: Optional[int] = None) -> None:
        """Schedule a specific line"""
        try:
            # Get the line to verify it exists
            line = self.get_line(line_id)
            if not line:
                raise ValueError(f"Line with ID {line_id} does not exist")
            
            # Verify facility exists
            if not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Update the line
            self.cursor.execute("""
                UPDATE lines 
                SET facility_id = ?, date = ?, time = ?, court_number = ?
                WHERE id = ?
            """, (facility_id, date, time, court_number, line_id))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to schedule line {line_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error scheduling line: {e}")

    def unschedule_line(self, line_id: int) -> None:
        """Unschedule a specific line"""
        try:
            # Get the line to verify it exists
            line = self.get_line(line_id)
            if not line:
                raise ValueError(f"Line with ID {line_id} does not exist")
            
            # Update the line
            self.cursor.execute("""
                UPDATE lines 
                SET facility_id = NULL, date = NULL, time = NULL, court_number = NULL
                WHERE id = ?
            """, (line_id,))
            
            # Check if the update was successful
            if self.cursor.rowcount == 0:
                raise RuntimeError(f"Failed to unschedule line {line_id}")
                
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error unscheduling line: {e}")

    def schedule_lines_for_match(self, match_id: int, facility_id: int, 
                               date: str, time: str) -> None:
        """Schedule all lines for a match at the same facility, date, and time"""
        try:
            # Verify match exists
            if not self.get_match(match_id):
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Verify facility exists
            if not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Update all lines for this match
            self.cursor.execute("""
                UPDATE lines 
                SET facility_id = ?, date = ?, time = ?
                WHERE match_id = ?
            """, (facility_id, date, time, match_id))
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error scheduling lines for match: {e}")

    def unschedule_lines_for_match(self, match_id: int) -> None:
        """Unschedule all lines for a match"""
        try:
            # Verify match exists
            if not self.get_match(match_id):
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Update all lines for this match
            self.cursor.execute("""
                UPDATE lines 
                SET facility_id = NULL, date = NULL, time = NULL, court_number = NULL
                WHERE match_id = ?
            """, (match_id,))
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error unscheduling lines for match: {e}")

    # ========== Combined Match and Line Operations ==========

    def create_lines_for_match(self, match_id: int, league) -> List[Line]:
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

    def bulk_create_matches_with_lines(self, league_id: int, teams) -> List[Match]:
        """Create all matches for a league with their required lines"""
        try:
            # Get league
            league = self.db.league_manager.get_league(league_id)
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

    def get_lines_summary_by_facility(self, facility_id: int, 
                                    start_date: Optional[str] = None,
                                    end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of lines scheduled at a facility over a date range"""
        try:
            # Verify facility exists
            if not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            where_conditions = ["facility_id = ?"]
            params = [facility_id]
            
            if start_date:
                where_conditions.append("date >= ?")
                params.append(start_date)
            
            if end_date:
                where_conditions.append("date <= ?")
                params.append(end_date)
            
            # Get total lines count
            query = f"SELECT COUNT(*) as count FROM lines WHERE {' AND '.join(where_conditions)}"
            self.cursor.execute(query, params)
            total_lines = self.cursor.fetchone()['count']
            
            # Get lines by date
            query = f"""
                SELECT date, COUNT(*) as lines_count
                FROM lines 
                WHERE {' AND '.join(where_conditions)}
                GROUP BY date
                ORDER BY date
            """
            self.cursor.execute(query, params)
            lines_by_date = {}
            for row in self.cursor.fetchall():
                lines_by_date[row['date']] = row['lines_count']
            
            # Get lines by time
            query = f"""
                SELECT time, COUNT(*) as lines_count
                FROM lines 
                WHERE {' AND '.join(where_conditions)}
                GROUP BY time
                ORDER BY time
            """
            self.cursor.execute(query, params)
            lines_by_time = {}
            for row in self.cursor.fetchall():
                lines_by_time[row['time']] = row['lines_count']
            
            return {
                'facility_id': facility_id,
                'total_lines': total_lines,
                'lines_by_date': lines_by_date,
                'lines_by_time': lines_by_time,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting lines summary: {e}")

    def get_court_usage_statistics(self, facility_id: int, date: str) -> Dict[str, Any]:
        """Get detailed court usage statistics for a facility on a specific date"""
        try:
            # Verify facility exists
            facility = self.db.facility_manager.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Get all lines for this facility/date
            lines = self.list_lines(facility_id=facility_id, date=date)
            
            # Group lines by time
            lines_by_time = {}
            for line in lines:
                if line.time not in lines_by_time:
                    lines_by_time[line.time] = []
                lines_by_time[line.time].append(line)
            
            # Get facility's schedule for this day
            from datetime import datetime
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            usage_stats = {
                'facility_id': facility_id,
                'facility_name': facility.name,
                'date': date,
                'day_of_week': day_name,
                'time_slots': {},
                'total_available_court_hours': 0,
                'total_used_court_hours': 0,
                'overall_utilization_percentage': 0
            }
            
            total_available = 0
            total_used = 0
            
            for time_slot in day_schedule.start_times:
                time = time_slot.time
                available_courts = time_slot.available_courts
                used_courts = len(lines_by_time.get(time, []))
                
                # Assuming each time slot is 2 hours (standard match length)
                hours_per_slot = 2.0
                available_hours = available_courts * hours_per_slot
                used_hours = used_courts * hours_per_slot
                
                total_available += available_hours
                total_used += used_hours
                
                usage_stats['time_slots'][time] = {
                    'available_courts': available_courts,
                    'used_courts': used_courts,
                    'remaining_courts': available_courts - used_courts,
                    'available_court_hours': available_hours,
                    'used_court_hours': used_hours,
                    'utilization_percentage': (used_courts / available_courts * 100) if available_courts > 0 else 0,
                    'scheduled_lines': [{'line_id': line.id, 'match_id': line.match_id} for line in lines_by_time.get(time, [])]
                }
            
            usage_stats['total_available_court_hours'] = total_available
            usage_stats['total_used_court_hours'] = total_used
            usage_stats['overall_utilization_percentage'] = (total_used / total_available * 100) if total_available > 0 else 0
            
            return usage_stats
            
        except Exception as e:
            raise RuntimeError(f"Error getting court usage statistics: {e}")

    def bulk_schedule_lines(self, line_schedules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk schedule multiple lines
        
        Args:
            line_schedules: List of dicts with keys: line_id, facility_id, date, time, court_number (optional)
            
        Returns:
            Dictionary with scheduling results
        """
        try:
            results = {
                'total_lines': len(line_schedules),
                'scheduled_successfully': 0,
                'failed_schedules': [],
                'errors': []
            }
            
            for schedule in line_schedules:
                try:
                    line_id = schedule['line_id']
                    facility_id = schedule['facility_id']
                    date = schedule['date']
                    time = schedule['time']
                    court_number = schedule.get('court_number')
                    
                    self.schedule_line(line_id, facility_id, date, time, court_number)
                    results['scheduled_successfully'] += 1
                    
                except Exception as e:
                    results['failed_schedules'].append(schedule)
                    results['errors'].append(str(e))
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Error in bulk scheduling lines: {e}")

    def get_match_and_line_statistics(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive statistics for both matches and lines"""
        try:
            stats = {}
            
            # Get match statistics
            match_stats = self.get_match_count_by_status(league_id)
            stats.update(match_stats)
            
            # Get line statistics
            line_stats = self.get_lines_count_by_status(league_id=league_id)
            stats.update(line_stats)
            
            # Calculate additional metrics
            if stats['total_matches'] > 0:
                stats['lines_per_match_avg'] = stats['total_lines'] / stats['total_matches']
                stats['scheduled_match_percentage'] = (stats['scheduled_matches'] / stats['total_matches']) * 100
            else:
                stats['lines_per_match_avg'] = 0
                stats['scheduled_match_percentage'] = 0
            
            if stats['total_lines'] > 0:
                stats['scheduled_line_percentage'] = (stats['scheduled_lines'] / stats['total_lines']) * 100
            else:
                stats['scheduled_line_percentage'] = 0
            
            return stats
            
        except Exception as e:
            raise RuntimeError(f"Error getting match and line statistics: {e}")

    def get_line_history(self, line_id: int) -> Dict[str, Any]:
        """Get scheduling history for a line (current implementation returns current state)"""
        try:
            line = self.get_line(line_id)
            if not line:
                raise ValueError(f"Line with ID {line_id} does not exist")
            
            # In a more advanced implementation, this could track scheduling changes over time
            # For now, return current scheduling state
            return {
                'line_id': line_id,
                'current_state': {
                    'match_id': line.match_id,
                    'line_number': line.line_number,
                    'facility_id': line.facility_id,
                    'date': line.date,
                    'time': line.time,
                    'court_number': line.court_number,
                    'is_scheduled': line.is_scheduled()
                },
                'history': []  # Could be implemented with an audit table
            }
            
        except Exception as e:
            raise RuntimeError(f"Error getting line history: {e}")

    def find_available_courts(self, facility_id: int, date: str, time: str, 
                            courts_needed: int = 1) -> bool:
        """Check if the required number of courts are available at a facility/date/time"""
        try:
            # Use the facility manager's method to check availability
            return self.db.facility_manager.check_court_availability(
                facility_id, date, time, courts_needed
            )
        except Exception as e:
            raise RuntimeError(f"Error checking court availability: {e}")
