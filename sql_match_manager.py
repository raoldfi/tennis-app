"""
Updated SQLite Match Manager - Using Modular Managers

Handles match-related database operations without using a separate Line class.
Instead, scheduled times are stored as a JSON array in the matches table.

Updated to use SQLLeagueManager, SQLTeamManager, and SQLFacilityManager
for all related entity operations instead of direct database access.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from collections import defaultdict
from usta import Match, MatchType, Facility
import math


class SQLMatchManager:
    """Match manager that stores scheduled times as JSON array in matches table"""
    
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
    
    def get_match(self, match_id: int) -> Optional[Match]:
        """Get a match with all related objects populated using modular managers"""
        query = """
        SELECT 
            m.id, m.league_id, m.home_team_id, m.visitor_team_id, 
            m.facility_id, m.date, m.scheduled_times
        FROM matches m
        WHERE m.id = ?
        """
        
        try:
            result = self.cursor.execute(query, (match_id,)).fetchone()
            if not result:
                return None
            
            match_data = self._dictify(result)
            
            # Use managers to get related objects
            league = self.db.league_manager.get_league(match_data['league_id'])
            if not league:
                raise RuntimeError(f"League {match_data['league_id']} not found for match {match_id}")
            
            home_team = self.db.team_manager.get_team(match_data['home_team_id'])
            if not home_team:
                raise RuntimeError(f"Home team {match_data['home_team_id']} not found for match {match_id}")
            
            visitor_team = self.db.team_manager.get_team(match_data['visitor_team_id'])
            if not visitor_team:
                raise RuntimeError(f"Visitor team {match_data['visitor_team_id']} not found for match {match_id}")
            
            # Get match facility if assigned
            match_facility = None
            if match_data['facility_id']:
                match_facility = self.db.facility_manager.get_facility(match_data['facility_id'])
                if not match_facility:
                    raise RuntimeError(f"Facility {match_data['facility_id']} not found for match {match_id}")
            
            # Parse scheduled times from JSON
            scheduled_times = []
            if match_data['scheduled_times']:
                try:
                    scheduled_times = json.loads(match_data['scheduled_times'])
                    if not isinstance(scheduled_times, list):
                        scheduled_times = []
                except (json.JSONDecodeError, TypeError):
                    scheduled_times = []
            
            # Construct Match object
            return Match(
                id=match_data['id'],
                league=league,
                home_team=home_team,
                visitor_team=visitor_team,
                facility=match_facility,
                date=match_data['date'],
                scheduled_times=scheduled_times
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
            facility_id = match.facility.id if match.facility else None
            
            # Validate that teams belong to the league using team manager
            home_team = self.db.team_manager.get_team(home_team_id)
            visitor_team = self.db.team_manager.get_team(visitor_team_id)
            
            if not home_team or home_team.league.id != league_id:
                raise ValueError("Home team must belong to the match league")
            if not visitor_team or visitor_team.league.id != league_id:
                raise ValueError("Visitor team must belong to the match league")
            
            # Verify related entities exist using managers
            if not self.db.league_manager.get_league(league_id):
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Verify facility exists if provided
            if facility_id and not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Serialize scheduled times to JSON
            scheduled_times_json = json.dumps(match.scheduled_times) if match.scheduled_times else None
            
            # Determine status
            status = 'scheduled' if match.is_scheduled() else 'unscheduled'
            
            # Insert match
            self.cursor.execute("""
                INSERT INTO matches (id, league_id, home_team_id, visitor_team_id, 
                                   facility_id, date, scheduled_times, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (match.id, league_id, home_team_id, visitor_team_id, 
                  facility_id, match.date, scheduled_times_json, status))
                
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Database integrity error adding match: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding match: {e}")
        return True

    def get_match_simple(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Get a match as a simple dictionary (for performance)"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            self.cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            
            match_data = self._dictify(row)
            
            # Parse scheduled times from JSON
            if match_data.get('scheduled_times'):
                try:
                    parsed_times = json.loads(match_data['scheduled_times'])
                    # Ensure it's always a list
                    if isinstance(parsed_times, list):
                        match_data['scheduled_times'] = parsed_times
                    else:
                        # Convert single value to list
                        match_data['scheduled_times'] = [parsed_times] if parsed_times is not None else []
                except (json.JSONDecodeError, TypeError):
                    match_data['scheduled_times'] = []
            else:
                match_data['scheduled_times'] = []
            
            return match_data
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")




    
    def list_matches(self, 
                     facility: Optional['Facility'] = None,
                     league: Optional['League'] = None,
                     team: Optional['Team'] = None,
                    match_type: Optional['MatchType'] = MatchType.ALL) -> List[Match]:
        """List matches with optional filtering by league, match type, facility, and team
        
        Args:
            league: Optional League object to filter by
            match_type: Optional type of matches to return (MatchType enum, defaults to MatchType.ALL)
            facility: Optional Facility object to filter by (matches at this facility)
            team: Optional Team object to filter by (matches involving this team)
        
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
        if not isinstance(match_type, MatchType):
            raise TypeError(f"match_type must be a MatchType enum, got: {type(match_type)}")
        
        if facility is not None and not hasattr(facility, 'id'):
            raise TypeError(f"facility must be a Facility object with an id attribute, got: {type(facility)}")
        
        if team is not None and not hasattr(team, 'id'):
            raise TypeError(f"team must be a Team object with an id attribute, got: {type(team)}")
        
        print(f"Trying to get Matches for League = {league}, match_type={match_type}, facility={facility}, team={team}")
        
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
            
            print(f"Query: {query}")
            print(f"Params: {params}")
            
            self.cursor.execute(query, params)
            
            matches = []
            for row in self.cursor.fetchall():
                match = self.get_match(row['id'])
                if match:
                    matches.append(match)
            
            print(f"Found {len(matches)} matches")
            return matches
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing matches: {e}")



    def update_match(self, match: Match) -> bool:
        """Update match metadata and scheduled times."""
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        try:
            # Check if match exists
            existing_data = self.get_match_simple(match.id)
            if not existing_data:
                raise ValueError(f"Match with ID {match.id} does not exist")
            
            # Extract IDs from objects for database storage
            league_id = match.league.id
            home_team_id = match.home_team.id
            visitor_team_id = match.visitor_team.id
            facility_id = match.facility.id if match.facility else None
            
            # Verify related entities exist using managers
            if not self.db.league_manager.get_league(league_id):
                raise ValueError(f"League with ID {league_id} does not exist")
            if not self.db.team_manager.get_team(home_team_id):
                raise ValueError(f"Home team with ID {home_team_id} does not exist")
            if not self.db.team_manager.get_team(visitor_team_id):
                raise ValueError(f"Visitor team with ID {visitor_team_id} does not exist")
            
            # Verify facility exists if provided
            if facility_id and not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Serialize scheduled times to JSON
            scheduled_times_json = json.dumps(match.scheduled_times) if match.scheduled_times else None
            
            # Determine status
            status = 'scheduled' if match.is_scheduled() else 'unscheduled'
            
            # Update the match
            self.cursor.execute("""
                UPDATE matches 
                SET league_id = ?, home_team_id = ?, visitor_team_id = ?, 
                    facility_id = ?, date = ?, scheduled_times = ?, status = ?
                WHERE id = ?
            """, (league_id, home_team_id, visitor_team_id, 
                  facility_id, match.date, scheduled_times_json, status, match.id))
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error updating match: {e}")
        return True

    def delete_match(self, match_id: int) -> bool:
        """Delete a match"""
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(f"Match ID must be a positive integer, got: {match_id}")
        
        try:
            # Check if match exists
            existing_data = self.get_match_simple(match_id)
            if not existing_data:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Delete the match
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
                match = self.get_match(row['id'])
                if match:
                    matches.append(match)
            
            return matches
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting matches on date: {e}")

    # ========== Schedule Match Operations ==========
    
    def schedule_match_all_lines_same_time(self, match: 'Match', 
                                           facility: 'Facility', 
                                           date: str, 
                                           time: Optional[str] = None) -> bool:
        
        """Schedule all lines of a match at the same facility, date, and time"""
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            
            # Verify facility exists using facility manager
            if not self.db.facility_manager.get_facility(facility.id):
                raise ValueError(f"Facility with ID {facility.id} does not exist")

            num_lines = match.league.num_lines_per_match
            
            # If time is not provided, find first available
            if not time:
            
                available_times = self.get_available_times_at_facility(facility=facility, 
                                                                   date=date,
                                                                   courts_needed=num_lines)
                # Take the first available time slot
                if available_times:
                    time = available_times[0]
                else:
                    return False
            
            else:
                # Need to make sure time provided as input is available
                if not self.check_time_availability(facility=facility, 
                                                        date=date, 
                                                        time=time, 
                                                        courts_needed=num_lines):
                    return False

            # At this point, time should be defined and available
            match.schedule_all_lines_same_time(facility=facility, date=date, time=time)
            
            # Update in database
            self.update_match(match)
            return True
            
        except Exception as e:
            # If there's any error, return False (could be due to conflicts, etc.)
            return False


    
    def schedule_match_split_times(self, match: Match, facility: Facility, date: str, 
                                  timeslots: Optional[List[str]]=None) -> bool:
        
        """Schedule lines in split times mode"""
        print(f"\n\n\n ====== A: schedule_match_split_times to timeslots = {timeslots}\n\n\n")

        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            
            # Verify facility exists using facility manager
            if not self.db.facility_manager.get_facility(facility.id):
                raise ValueError(f"Facility with ID {facility.id} does not exist")

            available_times = None
            
            # should we try to schedule half and half? 
            total_lines = match.league.num_lines_per_match

            # if timeslots were not provided, find consecutive slots for a split match
            if not timeslots:

                print(f"\n\n\n ====== A: SCHEDULE_MATCH_SPLIT_TIMES: available_times = {available_times}\n\n\n")


                # Calculate how many lines go in each slot
                lines_slot1 = math.ceil(total_lines / 2)  # First slot gets extra line if odd
                lines_slot2 = total_lines - lines_slot1   # Remaining lines
                
                # Find available times that can accommodate the larger requirement
                max_lines_needed = max(lines_slot1, lines_slot2)
                available_times = self.get_available_times_at_facility(
                    facility=facility, 
                    date=date,
                    courts_needed=max_lines_needed
                )
                
                if not available_times or len(available_times) < 2:
                    raise ValueError(f"Not enough available timeslots for split scheduling. Need 2, found {len(available_times) if available_times else 0}")
                    return False


                # Create timeslots list: first half of lines at time 1, rest at time 2
                timeslots = []
                for i in range(total_lines):
                    if i < lines_slot1:
                        timeslots.append(available_times[0])
                    else:
                        timeslots.append(available_times[1])

            
            # Validate timeslots list
            if len(timeslots) != total_lines:
                raise ValueError(f"Timeslots list length ({len(timeslots)}) must equal total lines ({total_lines})")
            
            print(f"Scheduling match with timeslots: {timeslots}")

            # Check availability for each unique timeslot
            from collections import Counter
            timeslot_counts = Counter(timeslots)
            
            for timeslot, count in timeslot_counts.items():
                if not self.check_time_availability(facility, date, timeslot, count):
                    print(f"Timeslot {timeslot} cannot accommodate {count} courts")
                    return False

            # If we got here, all timeslots are available. Go ahead and schedule
            if not match.schedule_lines_split_times(facility, date, timeslots):
                raise Exception(f"match.schedule_line_split_times returned an error")
                return False
            
            # Update in database
            return self.update_match(match)

            
        except Exception as e:
            print(f"\n\n CAUGHT EXCEPTION {e}\n\n")
            return False

        
    def unschedule_match(self, match: Match) -> bool:
        """Unschedule a match (remove facility, date, and all times)"""
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        match.unschedule()
        return self.update_match(match)


    
    def get_scheduled_times_at_facility(self, facility: Facility, date: str) -> List[str]:
        """Get all scheduled times at a facility on a specific date using facility manager for validation"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        # Verify facility exists using facility manager
        if not self.db.facility_manager.get_facility(facility.id):
            raise ValueError(f"Facility with ID {facility.id} does not exist")
        
        try:
            self.cursor.execute("""
                SELECT scheduled_times 
                FROM matches 
                WHERE facility_id = ? AND date = ? AND status = 'scheduled' AND scheduled_times IS NOT NULL
            """, (facility.id, date))
            
            all_times = []
            for row in self.cursor.fetchall():
                if row['scheduled_times']:
                    try:
                        times = json.loads(row['scheduled_times'])
                        if isinstance(times, list):
                            all_times.extend(times)
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            return sorted(list(set(all_times)))  # Remove duplicates and sort
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting scheduled times: {e}")
    
    def check_time_availability(self, facility: Facility, date: str, time: str, courts_needed: int = 1) -> bool:
        """Check if a specific time slot is available at a facility using facility manager"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        # Use facility manager to check availability
        return self.db.facility_manager.check_time_availability(facility.id, date, time, courts_needed)
    
    def get_available_times_at_facility(self, facility: Facility, date: str, courts_needed: int = 1) -> List[str]:
        """Get all available times at a facility for the specified number of courts using facility manager"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        # Use facility manager to get available times
        return self.db.facility_manager.get_available_times_at_facility(facility.id, date, courts_needed)

    # ========== Statistics and Reporting ==========
    
    def get_match_statistics(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get statistics about matches"""
        try:
            where_clause = "WHERE league_id = ?" if league_id else ""
            params = [league_id] if league_id else []
            
            # Get basic counts
            self.cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled_matches,
                    SUM(CASE WHEN status = 'unscheduled' THEN 1 ELSE 0 END) as unscheduled_matches
                FROM matches {where_clause}
            """, params)
            
            row = self.cursor.fetchone()
            stats = self._dictify(row)
            
            # Calculate scheduled lines
            self.cursor.execute(f"""
                SELECT scheduled_times 
                FROM matches 
                {where_clause} AND scheduled_times IS NOT NULL
            """, params)
            
            total_scheduled_lines = 0
            partially_scheduled_matches = 0
            fully_scheduled_matches = 0
            
            # Get league info for expected lines per match
            expected_lines = 3  # Default
            if league_id:
                league = self.db.league_manager.get_league(league_id)
                if league:
                    expected_lines = league.num_lines_per_match
            
            for row in self.cursor.fetchall():
                if row['scheduled_times']:
                    try:
                        times = json.loads(row['scheduled_times'])
                        if isinstance(times, list):
                            num_lines = len(times)
                            total_scheduled_lines += num_lines
                            
                            # Determine if match is fully or partially scheduled
                            if num_lines == expected_lines:
                                fully_scheduled_matches += 1
                            elif 0 < num_lines < expected_lines:
                                partially_scheduled_matches += 1
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            stats.update({
                'total_scheduled_lines': total_scheduled_lines,
                'partially_scheduled_matches': partially_scheduled_matches,
                'fully_scheduled_matches': fully_scheduled_matches,
                'scheduling_percentage': round((stats['scheduled_matches'] / stats['total_matches'] * 100) if stats['total_matches'] > 0 else 0, 2)
            })
            
            return stats
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting match statistics: {e}")
    
    def get_facility_usage_report(self, facility: Facility, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get facility usage report for a date range using facility manager for validation"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        # Verify facility exists using facility manager
        if not self.db.facility_manager.get_facility(facility.id):
            raise ValueError(f"Facility with ID {facility.id} does not exist")
        
        try:
            self.cursor.execute("""
                SELECT date, scheduled_times 
                FROM matches 
                WHERE facility_id = ? AND date BETWEEN ? AND ? AND status = 'scheduled'
                ORDER BY date
            """, (facility.id, start_date, end_date))
            
            usage_by_date = defaultdict(list)
            total_lines_scheduled = 0
            
            for row in self.cursor.fetchall():
                date = row['date']
                if row['scheduled_times']:
                    try:
                        times = json.loads(row['scheduled_times'])
                        if isinstance(times, list):
                            usage_by_date[date].extend(times)
                            total_lines_scheduled += len(times)
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            # Calculate peak usage times
            all_times = []
            for times_list in usage_by_date.values():
                all_times.extend(times_list)
            
            time_counts = defaultdict(int)
            for time in all_times:
                time_counts[time] += 1
            
            peak_times = sorted(time_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                'facility_id': facility.id,
                'facility_name': facility.name,
                'start_date': start_date,
                'end_date': end_date,
                'total_days_used': len(usage_by_date),
                'total_lines_scheduled': total_lines_scheduled,
                'usage_by_date': dict(usage_by_date),
                'peak_times': peak_times,
                'average_lines_per_day': round(total_lines_scheduled / len(usage_by_date) if usage_by_date else 0, 2)
            }
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting facility usage report: {e}")
    
    def get_scheduling_conflicts(self, facility: Facility, date: str) -> List[Dict[str, Any]]:
        """Find potential scheduling conflicts at a facility on a specific date using facility manager"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        # Verify facility exists using facility manager
        if not self.db.facility_manager.get_facility(facility.id):
            raise ValueError(f"Facility with ID {facility.id} does not exist")
        
        try:
            matches = self.get_matches_on_date(date)
            # Filter matches for this facility
            facility_matches = [m for m in matches if m.facility and m.facility.id == facility.id]
            
            conflicts = []
            time_usage = defaultdict(list)
            
            # Group matches by time
            for match in facility_matches:
                for time in match.scheduled_times:
                    time_usage[time].append({
                        'match_id': match.id,
                        'home_team': match.home_team.name,
                        'visitor_team': match.visitor_team.name,
                        'league': match.league.name
                    })
            
            # Use facility manager to get facility capacity information
            facility_obj = self.db.facility_manager.get_facility(facility.id)
            max_courts = facility_obj.total_courts if facility_obj else 0
            
            # Find times with multiple matches exceeding court capacity
            for time, matches_at_time in time_usage.items():
                if len(matches_at_time) > max_courts:
                    conflicts.append({
                        'time': time,
                        'courts_needed': len(matches_at_time),
                        'courts_available': max_courts,
                        'excess_demand': len(matches_at_time) - max_courts,
                        'matches': matches_at_time
                    })
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Error finding scheduling conflicts: {e}")