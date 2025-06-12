"""
Updated SQLite Match Manager - No Line Class

Handles match-related database operations without using a separate Line class.
Instead, scheduled times are stored as a JSON array in the matches table.

Updated to work with the new object-based interface.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from collections import defaultdict
from usta import Match, Facility




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
        """Get a match with all related objects populated"""
        query = """
        SELECT 
            m.id, m.league_id, m.home_team_id, m.visitor_team_id, 
            m.facility_id, m.date, m.scheduled_times,
            -- League fields
            l.name as league_name, l.year, l.section, l.region, 
            l.age_group, l.division, l.num_lines_per_match, l.num_matches,
            -- Home team fields  
            ht.name as home_team_name, ht.captain as home_team_captain,
            -- Visitor team fields
            vt.name as visitor_team_name, vt.captain as visitor_team_captain,
            -- Home team facility fields
            htf.id as home_facility_id, htf.name as home_facility_name, 
            htf.short_name as home_facility_short_name, htf.location as home_facility_location,
            -- Visitor team facility fields  
            vtf.id as visitor_facility_id, vtf.name as visitor_facility_name,
            vtf.short_name as visitor_facility_short_name, vtf.location as visitor_facility_location,
            -- Match facility fields
            f.name as facility_name, f.short_name as facility_short_name, 
            f.location as facility_location, f.total_courts
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.id
        LEFT JOIN teams ht ON m.home_team_id = ht.id  
        LEFT JOIN teams vt ON m.visitor_team_id = vt.id
        LEFT JOIN facilities htf ON ht.home_facility_id = htf.id
        LEFT JOIN facilities vtf ON vt.home_facility_id = vtf.id
        LEFT JOIN facilities f ON m.facility_id = f.id
        WHERE m.id = ?
        """
        
        try:
            result = self.cursor.execute(query, (match_id,)).fetchone()
            if not result:
                return None
                
            # Construct League object
            from usta import League
            league = League(
                id=result['league_id'],
                name=result['league_name'],
                year=result['year'],
                section=result['section'],
                region=result['region'],
                age_group=result['age_group'],
                division=result['division'],
                num_lines_per_match=result['num_lines_per_match'],
                num_matches=result['num_matches']
            )
            
            # Construct home team facility
            from usta import Facility
            home_facility = Facility(
                id=result['home_facility_id'],
                name=result['home_facility_name'],
                short_name=result['home_facility_short_name'],
                location=result['home_facility_location']
            ) if result['home_facility_id'] else None
            
            # Construct visitor team facility  
            visitor_facility = Facility(
                id=result['visitor_facility_id'],
                name=result['visitor_facility_name'],
                short_name=result['visitor_facility_short_name'],
                location=result['visitor_facility_location']
            ) if result['visitor_facility_id'] else None
            
            # Construct Team objects
            from usta import Team
            home_team = Team(
                id=result['home_team_id'],
                name=result['home_team_name'],
                league=league,
                home_facility=home_facility,
                captain=result['home_team_captain']
            )
            
            visitor_team = Team(
                id=result['visitor_team_id'], 
                name=result['visitor_team_name'],
                league=league,
                home_facility=visitor_facility,
                captain=result['visitor_team_captain']
            )
            
            # Construct match facility
            match_facility = Facility(
                id=result['facility_id'],
                name=result['facility_name'],
                short_name=result['facility_short_name'],
                location=result['facility_location'],
                total_courts=result['total_courts']
            ) if result['facility_id'] else None
            
            # Parse scheduled times from JSON
            scheduled_times = []
            if result['scheduled_times']:
                try:
                    scheduled_times = json.loads(result['scheduled_times'])
                    if not isinstance(scheduled_times, list):
                        scheduled_times = []
                except (json.JSONDecodeError, TypeError):
                    scheduled_times = []
            
            # Construct Match object
            return Match(
                id=result['id'],
                league=league,
                home_team=home_team,
                visitor_team=visitor_team,
                facility=match_facility,
                date=result['date'],
                scheduled_times=scheduled_times
            )
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")

    def add_match(self, match: Match) -> None:
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
            
            # Validate that teams belong to the league
            if match.home_team.league.id != league_id:
                raise ValueError("Home team must belong to the match league")
            if match.visitor_team.league.id != league_id:
                raise ValueError("Visitor team must belong to the match league")
            
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
                    match_data['scheduled_times'] = json.loads(match_data['scheduled_times'])
                except (json.JSONDecodeError, TypeError):
                    match_data['scheduled_times'] = []
            else:
                match_data['scheduled_times'] = []
            
            return match_data
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving match {match_id}: {e}")

    def list_matches(self, league: Optional['League'] = None, include_unscheduled: bool = True) -> List[Match]:
        """List matches with optional filtering"""

        print(f"Trying to get Matches for League = {league}, include_unscheduled={include_unscheduled}")
        
        try:
            # Build query based on filters
            where_conditions = []
            params = []
            
            if league:
                where_conditions.append("league_id = ?")
                params.append(league.id)
            
            if not include_unscheduled:
                where_conditions.append("status = 'scheduled'")
            
            query = "SELECT id FROM matches"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY date, id"
            
            self.cursor.execute(query, params)
            
            matches = []
            for row in self.cursor.fetchall():
                match = self.get_match(row['id'])
                if match:
                    matches.append(match)

            #print(f"Executed query {query}")
            #print(f"matches returned = {matches}")
            
            return matches
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error listing matches: {e}")

    def update_match(self, match: Match) -> None:
        """Update match metadata and scheduled times"""
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
            
            # Verify related entities exist
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

    def delete_match(self, match_id: int) -> None:
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
    
    def schedule_match_all_lines_same_time(self, match: Match, facility: Facility, date: str, time: str) -> bool:
        """Schedule all lines of a match at the same facility, date, and time"""
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            
            # Schedule all lines at the same time
            match.schedule_all_lines_same_time(facility, date, time)
            
            # Update in database
            self.update_match(match)
            return True
            
        except Exception as e:
            # If there's any error, return False (could be due to conflicts, etc.)
            return False
    
    def schedule_match_sequential_times(self, match: Match, facility: Facility, date: str, start_time: str, interval_minutes: int = 180) -> bool:
        """Schedule lines sequentially with specified interval"""
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            if not isinstance(facility, Facility):
                raise TypeError(f"Expected Facility object, got: {type(facility)}")
            
            # Schedule lines sequentially
            match.schedule_lines_sequential(facility, date, start_time, interval_minutes)
            
            # Update in database
            self.update_match(match)
            return True
            
        except Exception as e:
            return False
    
    def unschedule_match(self, match: Match) -> None:
        """Unschedule a match (remove facility, date, and all times)"""
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        match.unschedule()
        self.update_match(match)
    
    def get_scheduled_times_at_facility(self, facility: Facility, date: str) -> List[str]:
        """Get all scheduled times at a facility on a specific date"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
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
        """Check if a specific time slot is available at a facility"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            # Get all scheduled times at this facility/date
            scheduled_times = self.get_scheduled_times_at_facility(facility, date)
            
            # Count how many times this specific time is already used
            times_used = scheduled_times.count(time)
            
            # Get day of week and check if time slot exists
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return False
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            # Find the time slot
            time_slot = None
            for slot in day_schedule.start_times:
                if slot.time == time:
                    time_slot = slot
                    break
            
            if not time_slot:
                return False  # Time slot not available at this facility
            
            # Check if there are enough courts available
            available_courts = time_slot.available_courts - times_used
            return available_courts >= courts_needed
            
        except Exception as e:
            return False
    
    def get_available_times_at_facility(self, facility: Facility, date: str, courts_needed: int = 1) -> List[str]:
        """Get all available times at a facility for the specified number of courts"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            # Check if facility is available on this date
            if not facility.is_available_on_date(date):
                return []
            
            # Get day of week
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')
            except ValueError:
                return []
            
            day_schedule = facility.schedule.get_day_schedule(day_name)
            
            available_times = []
            for time_slot in day_schedule.start_times:
                if self.check_time_availability(facility, date, time_slot.time, courts_needed):
                    available_times.append(time_slot.time)
            
            return available_times
            
        except Exception as e:
            return []

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
            
            for row in self.cursor.fetchall():
                if row['scheduled_times']:
                    try:
                        times = json.loads(row['scheduled_times'])
                        if isinstance(times, list):
                            num_lines = len(times)
                            total_scheduled_lines += num_lines
                            
                            # Determine if match is fully or partially scheduled
                            # This would require knowing expected lines per match
                            # For now, assume 3 lines per match
                            expected_lines = 3
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
        """Get facility usage report for a date range"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
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
        """Find potential scheduling conflicts at a facility on a specific date"""
        if not isinstance(facility, Facility):
            raise TypeError(f"Expected Facility object, got: {type(facility)}")
        
        try:
            matches = self.get_matches_on_date(date, facility)
            
            conflicts = []
            time_usage = defaultdict(list)
            
            # Group matches by time
            for match in matches:
                for time in match.scheduled_times:
                    time_usage[time].append({
                        'match_id': match.id,
                        'home_team': match.home_team.name,
                        'visitor_team': match.visitor_team.name,
                        'league': match.league.name
                    })
            
            # Find times with multiple matches exceeding court capacity
            max_courts = facility.total_courts
            
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

