"""
Refactored SQLite Match Manager - Consolidated Scheduling Functions

This refactored version eliminates redundant scheduling functions and consolidates
similar functionality into unified, flexible methods.

Key improvements:
1. Single auto_schedule_match method instead of multiple versions
2. Unified schedule_match method that handles all scheduling modes
3. Consolidated validation logic
4. Simplified scheduling execution
5. Removed duplicate helper functions
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from tennis_db_interface import TennisDBInterface
from usta import Match, MatchType, Facility, League, Team
import math
from usta_match import MatchScheduling


class SQLMatchManager:
    """Match manager with consolidated scheduling functions"""

    def __init__(self, cursor: sqlite3.Cursor, db_instance: TennisDBInterface):
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

    # ========== Core Match Operations (unchanged) ==========

    def get_match(self, match_id: int) -> Optional[Match]:
        """Get a match with all related objects populated using modular managers"""
        query = """
        SELECT 
            m.id, m.league_id, m.home_team_id, m.visitor_team_id, 
            m.facility_id, m.date, m.scheduled_times, m.round, m.num_rounds
        FROM matches m
        WHERE m.id = ?
        """

        try:
            self.cursor.execute(query, (match_id,))
            row = self.cursor.fetchone()
            if not row:
                return None

            match_data = self._dictify(row)

            # Get related objects using modular managers
            league = self.db.league_manager.get_league(match_data["league_id"])
            home_team = self.db.team_manager.get_team(match_data["home_team_id"])
            visitor_team = self.db.team_manager.get_team(match_data["visitor_team_id"])
            match_facility = (
                self.db.facility_manager.get_facility(match_data["facility_id"])
                if match_data["facility_id"]
                else None
            )

            if not league or not home_team or not visitor_team:
                raise ValueError(f"Could not load related objects for match {match_id}")

            # Parse scheduled times from JSON
            scheduled_times = []
            if match_data.get("scheduled_times"):
                try:
                    parsed_times = json.loads(match_data["scheduled_times"])
                    if isinstance(parsed_times, list):
                        scheduled_times = parsed_times
                    else:
                        scheduled_times = (
                            [parsed_times] if parsed_times is not None else []
                        )
                except (json.JSONDecodeError, TypeError):
                    scheduled_times = []

            # Create MatchScheduling object if match is scheduled
            scheduling = None
            if match_facility and match_data.get("date") and scheduled_times:
                scheduling = MatchScheduling(
                    facility=match_facility,
                    date=match_data["date"],
                    scheduled_times=scheduled_times
                )

            # Construct Match object
            return Match(
                id=match_data["id"],
                round=match_data["round"],
                num_rounds=match_data["num_rounds"],
                league=league,
                home_team=home_team,
                visitor_team=visitor_team,
                scheduling=scheduling
            )
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")

    def add_match(self, match: Match) -> bool:
        """Add a new match to the database"""
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")

        try:
            # Check if match ID already exists
            existing = self.get_match(match.id)
            if existing:
                raise ValueError(f"Match with ID {match.id} already exists")

            # Extract IDs from objects for database storage
            league_id = match.league.id
            home_team_id = match.home_team.id
            visitor_team_id = match.visitor_team.id
            facility_id = match.scheduling.facility.id if match.scheduling else None

            # Validate related entities exist
            if not self.db.league_manager.get_league(league_id):
                raise ValueError(f"League with ID {league_id} does not exist")
            if not self.db.team_manager.get_team(home_team_id):
                raise ValueError(f"Home team with ID {home_team_id} does not exist")
            if not self.db.team_manager.get_team(visitor_team_id):
                raise ValueError(
                    f"Visitor team with ID {visitor_team_id} does not exist"
                )
            if facility_id and not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")

            # Serialize scheduled times to JSON
            scheduled_times_json = (
                json.dumps(match.scheduling.scheduled_times) if match.scheduling and match.scheduling.scheduled_times else None
            )

            # Determine status
            status = "scheduled" if match.is_scheduled() else "unscheduled"

            # Insert match
            query = """
                INSERT INTO matches (id, league_id, home_team_id, visitor_team_id, 
                                   facility_id, date, scheduled_times, status, round, num_rounds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                match.id,
                league_id,
                home_team_id,
                visitor_team_id,
                facility_id,
                match.scheduling.date if match.scheduling else None,
                scheduled_times_json,
                status,
                match.round,
                match.num_rounds,
            )

            # Execute with transaction awareness
            if hasattr(self.db, "execute_operation"):
                self.db.execute_operation(
                    "add_match",
                    query,
                    params,
                    f"Add match {match.id}: {match.home_team.name} vs {match.visitor_team.name}",
                )
            else:
                self.cursor.execute(query, params)
            return True

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding match: {e}")

    def delete_match(self, match_id: int) -> bool:
        """Delete a match from the database"""
        try:
            # Execute with transaction awareness
            if hasattr(self.db, "execute_operation"):
                self.db.execute_operation(
                    "delete_match",
                    "DELETE FROM matches WHERE id = ?",
                    (match_id,),
                    f"Delete match {match_id}",
                )
            else:
                self.cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error deleting match: {e}")
        return True

    def get_matches_on_date(self, date: str) -> List[Match]:
        """Get all scheduled matches on a specific date"""
        try:
            where_conditions = ["date = ?", "status = 'scheduled'"]
            params = [date]

            query = "SELECT id FROM matches WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY id"

            self.cursor.execute(query, params)

            matches = []
            for row in self.cursor.fetchall():
                match = self.get_match(row["id"])
                if match:
                    matches.append(match)

            return matches
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting matches on date: {e}")




    def update_match(self, match: Match) -> bool:
        """Update match in database with transaction awareness
        
        If the match is unscheduled, removes scheduling information from the database.
        If the match is scheduled, updates the database with the information in match.scheduling.
        
        Args:
            match: Match object to update in database
            
        Returns:
            bool: True if update successful
            
        Raises:
            ValueError: If required entities don't exist
            RuntimeError: If database error occurs
        """
        try:
            # Verify related entities exist (skip in dry-run for performance)
            if not getattr(self.db, "dry_run_active", False):
                if not self.db.league_manager.get_league(match.league.id):
                    raise ValueError(f"League with ID {match.league.id} does not exist")
                if not self.db.team_manager.get_team(match.home_team.id):
                    raise ValueError(
                        f"Home team with ID {match.home_team.id} does not exist"
                    )
                if not self.db.team_manager.get_team(match.visitor_team.id):
                    raise ValueError(
                        f"Visitor team with ID {match.visitor_team.id} does not exist"
                    )
                if match.scheduling and match.scheduling.facility and not self.db.facility_manager.get_facility(
                    match.scheduling.facility.id
                ):
                    raise ValueError(
                        f"Facility with ID {match.scheduling.facility.id} does not exist"
                    )

            # Handle scheduling information based on match state
            if match.is_scheduled():
                # Match is scheduled - update with scheduling information
                scheduled_times_json = json.dumps(match.scheduling.scheduled_times) if match.scheduling.scheduled_times else None
                facility_id = match.scheduling.facility.id if match.scheduling.facility else None
                date = match.scheduling.date if match.scheduling else None
                status = "scheduled"
                
                # Update scheduling state for conflict detection when scheduling
                if hasattr(self.db, "scheduling_state") and self.db.scheduling_state:
                    # Atomically update bookings to avoid race conditions
                    if match.scheduling and match.scheduling.scheduled_times:
                        self.db.scheduling_state.update_match_bookings(
                            match.id, facility_id, date, 
                            match.scheduling.scheduled_times,
                            match.home_team.id, match.visitor_team.id
                        )
                    else:
                        # Clear bookings if match has no scheduling
                        self.db.scheduling_state.clear_match_bookings(match.id)
            else:
                # Match is unscheduled - remove scheduling information
                scheduled_times_json = None
                facility_id = None
                date = None
                status = "unscheduled"
                
                # Clear scheduling state if it exists
                if hasattr(self.db, "scheduling_state") and self.db.scheduling_state:
                    self.db.scheduling_state.clear_match_bookings(match.id)

            # Prepare operation description for transaction logging
            operation_desc = f"Update match {match.id}: {match.home_team.name} vs {match.visitor_team.name}"
            if status == "scheduled":
                if facility_id:
                    facility = self.db.facility_manager.get_facility(facility_id)
                    if facility:
                        operation_desc += f" at {facility.name}"
                if date:
                    operation_desc += f" on {date}"
                if scheduled_times_json:
                    times = json.loads(scheduled_times_json)
                    operation_desc += f" at {', '.join(times)}"
            else:
                operation_desc += " (unscheduled)"

            # Update the match using transaction-aware execution
            query = """
                UPDATE matches 
                SET league_id = ?, home_team_id = ?, visitor_team_id = ?, 
                    facility_id = ?, date = ?, scheduled_times = ?, status = ?, 
                    round = ?, num_rounds = ?
                WHERE id = ?
            """

            params = (
                match.league.id,
                match.home_team.id,
                match.visitor_team.id,
                facility_id,
                date,
                scheduled_times_json,
                status,
                match.round,
                match.num_rounds,
                match.id,
            )

            # Execute with transaction awareness
            if hasattr(self.db, "execute_operation"):
                self.db.execute_operation("update_match", query, params, operation_desc)
            else:
                self.cursor.execute(query, params)

            return True

        except Exception as e:
            raise RuntimeError(f"Error updating match in database: {e}")

    # ========== ADDITIONAL UTILITY METHODS ==========


    def _check_facility_time_conflicts(
        self,
        facility_id: int,
        date: str,
        time: str,
        exclude_match_id: Optional[int] = None,
    ) -> List[Dict]:
        """Check for conflicts at a specific facility, date, and time"""
        try:
            conflicts = []
            duration_hours = 3  # Standard match duration

            # Parse the proposed time
            start_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(hours=duration_hours)

            # Query for overlapping matches
            query = """
            SELECT m.id, m.scheduled_times, 
                   ht.name as home_team_name, vt.name as visitor_team_name
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.id
            JOIN teams vt ON m.visitor_team_id = vt.id
            WHERE m.facility_id = ? 
                AND m.date = ?
                AND m.status = 'scheduled'
                AND m.scheduled_times IS NOT NULL
            """
            params = [facility_id, date]

            if exclude_match_id:
                query += " AND m.id != ?"
                params.append(exclude_match_id)

            self.cursor.execute(query, params)

            for row in self.cursor.fetchall():
                match_data = self._dictify(row)

                if match_data["scheduled_times"]:
                    try:
                        scheduled_times = json.loads(match_data["scheduled_times"])
                        if isinstance(scheduled_times, list):
                            for scheduled_time in scheduled_times:
                                # Check if there's a time overlap
                                scheduled_start = datetime.strptime(
                                    f"{date} {scheduled_time}", "%Y-%m-%d %H:%M"
                                )
                                scheduled_end = scheduled_start + timedelta(
                                    hours=duration_hours
                                )

                                # Check for overlap
                                if (
                                    start_time < scheduled_end
                                    and end_time > scheduled_start
                                ):
                                    conflicts.append(
                                        {
                                            "type": "facility_time_conflict",
                                            "match_id": match_data["id"],
                                            "conflicting_time": scheduled_time,
                                            "home_team": match_data["home_team_name"],
                                            "visitor_team": match_data[
                                                "visitor_team_name"
                                            ],
                                            "message": f"Facility already has match at {scheduled_time}",
                                        }
                                    )
                    except (json.JSONDecodeError, TypeError):
                        continue

            return conflicts

        except Exception as e:
            return [{"type": "error", "message": f"Error checking conflicts: {e}"}]

    # ========== OTHER EXISTING METHODS (unchanged) ==========

    def list_matches(
        self,
        facility: Optional["Facility"] = None,
        league: Optional["League"] = None,
        team: Optional["Team"] = None,
        date_str: Optional[str] = None,
        match_type: Optional["MatchType"] = MatchType.ALL,
    ) -> List[Match]:
        """List matches with optional filtering by league, match type, facility, and team

        Args:
            league: Optional League object to filter by
            match_type: Optional type of matches to return (MatchType enum, defaults to MatchType.ALL)
            facility: Optional Facility object to filter by (matches at this facility)
            team: Optional Team object to filter by (matches involving this team)
            date_str: Optional date string to filter matches by (YYYY-MM-DD format)
            match_type: MatchType enum to filter matches by status (scheduled, unscheduled, or all)

        Returns:
            List of Match objects matching the criteria

        Raises:
            TypeError: If match_type is not a MatchType enum, or if facility/team are wrong types
            RuntimeError: If database error occurs

        Examples:
            # Get all matches
            matches = manager.list_matches()

            # Get only scheduled matches
            matches = manager.list_matches(match_type=MatchType.SCHEDULED)

            # Get unscheduled matches in a specific league
            matches = manager.list_matches(my_league, MatchType.UNSCHEDULED)

            # Get matches at a specific facility
            matches = manager.list_matches(facility=my_facility)

            # Get matches involving a specific team
            matches = manager.list_matches(team=my_team)

            # Get scheduled matches for a team at a facility
            matches = manager.list_matches(match_type=MatchType.SCHEDULED, facility=my_facility, team=my_team)
        """

        # Validate parameters
        if league is not None and not hasattr(league, "id"):
            raise TypeError(
                f"league must be a League object with an id attribute, got: {type(league)}"
            )
        if match_type is None:
            match_type = MatchType.ALL
        elif isinstance(match_type, str):
            # Convert string to MatchType enum if possible
            try:
                match_type = MatchType[match_type.upper()]
            except KeyError:
                raise ValueError(f"Invalid match_type string: {match_type}")
        elif isinstance(match_type, int):
            # Convert integer to MatchType enum if possible
            try:
                match_type = MatchType(match_type)
            except ValueError:
                raise ValueError(f"Invalid match_type integer: {match_type}")
        elif not isinstance(match_type, MatchType):
            # Raise error if not a valid MatchType enum
            raise TypeError(
                f"match_type must be a MatchType enum, got: {type(match_type)}"
            )
        if date_str is not None and not isinstance(date_str, str):
            raise TypeError(f"date_str must be a string, got: {type(date_str)}")

        if facility is not None and not hasattr(facility, "id"):
            raise TypeError(
                f"facility must be a Facility object with an id attribute, got: {type(facility)}"
            )

        if team is not None and not hasattr(team, "id"):
            raise TypeError(
                f"team must be a Team object with an id attribute, got: {type(team)}"
            )

        # print(
        #     f"Trying to get Matches for League = {league}, match_type={match_type}, facility={facility}, team={team}"
        # )

        try:
            # Build query based on filters
            where_conditions = []
            params = []

            if league:
                where_conditions.append("league_id = ?")
                params.append(league.id)

            # Add facility filter
            if facility:
                where_conditions.append("facility_id = ?")
                params.append(facility.id)

            # Add team filter (matches where team is either home or visitor)
            if team:
                where_conditions.append("(home_team_id = ? OR visitor_team_id = ?)")
                params.append(team.id)
                params.append(team.id)

            # Add date filter
            if date_str:
                where_conditions.append("date = ?")
                params.append(date_str)


            # Add match type filter
            if match_type == MatchType.SCHEDULED:
                where_conditions.append("status = 'scheduled'")
            elif match_type == MatchType.UNSCHEDULED:
                where_conditions.append("status = 'unscheduled'")
            # For MatchType.ALL, no additional filter needed

            # Build the query
            query = "SELECT id FROM matches"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY id"

            # print(f"Query: {query}")
            # print(f"Params: {params}")

            self.cursor.execute(query, params)

            matches = []
            for row in self.cursor.fetchall():
                match = self.get_match(row["id"])
                if match:
                    matches.append(match)

            # print(f"Found {len(matches)} matches")
            return matches

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing matches: {e}")

    
    
    
