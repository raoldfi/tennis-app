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
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from tennis_db_interface import TennisDBInterface
from usta import Match, MatchType, Facility, League, Team
import math
from tennis_db_interface import TennisDBInterface



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
            league = self.db.league_manager.get_league(match_data['league_id'])
            home_team = self.db.team_manager.get_team(match_data['home_team_id'])
            visitor_team = self.db.team_manager.get_team(match_data['visitor_team_id'])
            match_facility = self.db.facility_manager.get_facility(match_data['facility_id']) if match_data['facility_id'] else None
            
            if not league or not home_team or not visitor_team:
                raise ValueError(f"Could not load related objects for match {match_id}")
            
            # Parse scheduled times from JSON
            scheduled_times = []
            if match_data.get('scheduled_times'):
                try:
                    parsed_times = json.loads(match_data['scheduled_times'])
                    if isinstance(parsed_times, list):
                        scheduled_times = parsed_times
                    else:
                        scheduled_times = [parsed_times] if parsed_times is not None else []
                except (json.JSONDecodeError, TypeError):
                    scheduled_times = []
            
            # Construct Match object
            return Match(
                id=match_data['id'],
                round=match_data['round'],
                num_rounds=match_data['num_rounds'],
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
            
            # Validate related entities exist
            if not self.db.league_manager.get_league(league_id):
                raise ValueError(f"League with ID {league_id} does not exist")
            if not self.db.team_manager.get_team(home_team_id):
                raise ValueError(f"Home team with ID {home_team_id} does not exist")
            if not self.db.team_manager.get_team(visitor_team_id):
                raise ValueError(f"Visitor team with ID {visitor_team_id} does not exist")
            if facility_id and not self.db.facility_manager.get_facility(facility_id):
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            # Serialize scheduled times to JSON
            scheduled_times_json = json.dumps(match.scheduled_times) if match.scheduled_times else None
            
            # Determine status
            status = 'scheduled' if match.is_scheduled() else 'unscheduled'
            
            # Insert match
            query = """
                INSERT INTO matches (id, league_id, home_team_id, visitor_team_id, 
                                   facility_id, date, scheduled_times, status, round, num_rounds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                match.id, league_id, home_team_id, visitor_team_id,
                facility_id, match.date, scheduled_times_json, status,
                match.round, match.num_rounds
            )
            
            # Execute with transaction awareness
            if hasattr(self.db, 'execute_operation'):
                self.db.execute_operation('add_match', query, params, f"Add match {match.id}: {match.home_team.name} vs {match.visitor_team.name}")
            else:
                self.cursor.execute(query, params)
            return True
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error adding match: {e}")

    def delete_match(self, match_id: int) -> bool:
        """Delete a match from the database"""
        try:
            # Execute with transaction awareness
            if hasattr(self.db, 'execute_operation'):
                self.db.execute_operation('delete_match', "DELETE FROM matches WHERE id = ?", (match_id,), f"Delete match {match_id}")
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
                match = self.get_match(row['id'])
                if match:
                    matches.append(match)
            
            return matches
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error getting matches on date: {e}")

    # ========== CONSOLIDATED SCHEDULING METHODS ==========
    

    # ========== SIMPLIFIED SCHEDULING - Use Match Methods ==========
    
    def schedule_match(self, match: Match, date: str, 
                      times: List[str], mode: str = 'auto') -> Dict[str, Any]:
        """
        Simplified scheduling that uses Match class methods directly
        """
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            
            # Check if match has a facility assigned
            if not match.facility:
                return {
                    'success': False,
                    'error': "No facility assigned to match",
                    'error_type': 'no_facility'
                }
            
            # Get detailed facility availability information
            facility_availability = self.db.facility_manager.get_facility_availability(
                facility=match.facility, dates=[date], max_days=1
            )
            
            if not facility_availability or not facility_availability[0].available:
                reason = facility_availability[0].reason if facility_availability else "Unknown reason"
                return {
                    'success': False,
                    'error': f"Facility {match.facility.name} not available on {date}: {reason}",
                    'error_type': 'facility_unavailable'
                }
            
            facility_info = facility_availability[0]
            
            # Check for team conflicts
            if self._has_team_date_conflicts(match, date):
                return {
                    'success': False,
                    'error': f"Team conflict detected on {date}",
                    'error_type': 'team_conflict'
                }
            
            # Auto-determine times if not provided. Since nothing was provided, 
            # we will try to get available times based on the mode, then select 
            # the appropriate times based on the mode.
            if not times:
                times = self._get_times_for_mode(match, facility_info, mode)
                if not times:
                    return {
                        'success': False,
                        'error': f"No available times for mode '{mode}'",
                        'error_type': 'no_available_times'
                    }
            
            # Validate scheduling request using FacilityAvailabilityInfo
            lines_needed = match.league.num_lines_per_match if match.league else 3
            is_valid, validation_error = facility_info.validate_scheduling_request(
                times=times, scheduling_mode=mode, lines_needed=lines_needed
            )
            

            if not is_valid:
                return {
                    'success': False,
                    'error': f"Scheduling validation failed: {validation_error}",
                    'error_type': 'validation_failed'
                }
            
            # Use Match class methods based on mode
            success = False
            
            if mode == 'same_time':
                if len(times) >= 1:
                    match.schedule_all_lines_same_time(match.facility, date, times[0])
                    success = True
                    
            elif mode == 'split_times':
                if len(times) >= 2:
                    # Generate split times using Match logic
                    lines_needed = match.get_expected_lines()
                    courts_per_slot = math.ceil(lines_needed / 2)
                    lines_in_second_slot = lines_needed - courts_per_slot
                    split_times = ([times[0]] * courts_per_slot + [times[1]] * lines_in_second_slot)
                    match.schedule_lines_split_times(match.facility, date, split_times)
                    success = True
                    
            elif mode == 'custom':
                success = match.schedule_lines_custom_times(match.facility, date, times)
            
            if success:
                # Update database
                self._update_match_in_db(match)
                
                # Update scheduling state for conflict detection in dry-run mode
                if hasattr(self.db, 'scheduling_state') and self.db.scheduling_state:
                    scheduled_times = match.get_scheduled_times()
                    for time in scheduled_times:
                        self.db.scheduling_state.book_time_slot(match.id, match.facility.id, date, time)
                    self.db.scheduling_state.book_team_date(match.id, match.home_team.id, date)
                    self.db.scheduling_state.book_team_date(match.id, match.visitor_team.id, date)
                
                return {
                    'success': True,
                    'scheduled_times': match.get_scheduled_times(),
                    'mode_used': mode
                }
            else:
                return {
                    'success': False,
                    'error': f"Could not schedule using mode '{mode}'",
                    'error_type': 'scheduling_failed'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'exception'
            }
    
    def auto_schedule_match(self, match: Match, preferred_dates: List[str]) -> bool:
        """
        Simplified auto-scheduling that tries different scheduling modes
        """
        try:
            # Skip already scheduled matches
            if match.is_scheduled():
                return True
                        
            # Try each date and facility combination
            for date in preferred_dates:
                    
                try:
                    # Strategy 1: Try same time scheduling
                    result = self.schedule_match(match, date, [], 'same_time')
                    if result['success']:
                        return True
                    
                    # Strategy 2: Try split scheduling if allowed
                    if match.league.allow_split_lines:
                        result = self.schedule_match(match, date, [], 'split_times')
                        if result['success']:
                            return True
                    
                        
                except Exception as e:
                    raise RuntimeError(f"{e}")
            
            return False
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling match {match.id}: {e}")
    
    def auto_schedule_matches(self, matches: List[Match], dry_run: bool = True) -> Dict[str, Any]:
        """
        Simplified batch auto-scheduling
        """
        try:
            results = {
                'total_matches': len(matches),
                'scheduled': 0,
                'failed': 0,
                'scheduling_details': [],
                'errors': [],
                'dry_run': dry_run
            }
            
            # Filter unscheduled matches
            unscheduled_matches = [m for m in matches if m.is_unscheduled()]
            
            if not unscheduled_matches:
                return results
            
            # Begin transaction
            self.db.begin_transaction(dry_run=dry_run)
            
            try:
                # Shuffle for fairness
                import random
                shuffled_matches = unscheduled_matches.copy()
                random.shuffle(shuffled_matches)
                
                for match in shuffled_matches:
                    # Use Match class method to get optimal dates with priorities
                    optimal_dates_with_priority = match.get_prioritized_scheduling_dates()
                    optimal_dates = [date for date, priority in optimal_dates_with_priority]
                    
                    success = self.auto_schedule_match(match, optimal_dates)
                    
                    if success:
                        results['scheduled'] += 1
                        results['scheduling_details'].append({
                            'match_id': match.id,
                            'status': 'would_be_scheduled' if dry_run else 'scheduled',
                            'home_team': match.home_team_name,
                            'visitor_team': match.visitor_team_name,
                            'facility': match.facility_name,
                            'date': match.date,
                            'times': match.get_scheduled_times()
                        })
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'match_id': match.id,
                            'status': 'scheduling_failed',
                            'home_team': match.home_team_name,
                            'visitor_team': match.visitor_team_name,
                            'reason': 'No available time slots found'
                        })
                
                # Commit transaction
                self.db.commit_transaction()
                return results
                
            except Exception as e:
                self.db.rollback_transaction()
                results['errors'].append({'type': 'transaction_error', 'message': str(e)})
                raise e
        
        except Exception as e:
            raise RuntimeError(f"Error in auto_schedule_matches: {e}")
    
    def unschedule_match(self, match: Match) -> bool:
        """Unschedule a match using Match class method"""
        try:
            match.unschedule()  # Use Match class method
            return self._update_match_in_db(match)
        except Exception as e:
            raise RuntimeError(f"Error unscheduling match: {e}")



    def _get_optimal_scheduling_dates(self, match: Match, days_ahead: int = 90) -> List[str]:
        """
        Get optimal scheduling dates for a match based on team and league preferences
        
        Args:
            match: Match object
            days_ahead: Number of days to look ahead (default 90)
            
        Returns:
            List of dates in order of preference
        """
        from datetime import datetime, timedelta
        
        try:
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=days_ahead)
            
            candidate_dates = []
            current = start_date
            
            while current <= end_date:
                day_name = current.strftime('%A')
                date_str = current.strftime('%Y-%m-%d')
                
                # Calculate priority based on league and team preferences
                priority = 10  # Default priority
                
                # League preferences
                if hasattr(match.league, 'preferred_days') and match.league.preferred_days:
                    if day_name in match.league.preferred_days:
                        priority = 1  # Highest priority
                    elif hasattr(match.league, 'backup_days') and day_name in match.league.backup_days:
                        priority = 3
                
                # Team preferences (home team gets priority)
                if hasattr(match.home_team, 'preferred_days') and match.home_team.preferred_days:
                    if day_name in match.home_team.preferred_days:
                        priority = min(priority, 2)  # High priority, but after league preferred
                
                # Weekend bonus for recreational leagues
                if day_name in ['Saturday', 'Sunday']:
                    priority = min(priority, 4)
                
                candidate_dates.append((date_str, priority))
                current += timedelta(days=1)
            
            # Sort by priority, then by date
            candidate_dates.sort(key=lambda x: (x[1], x[0]))
            
            # Return just the date strings
            return [date for date, _ in candidate_dates]
            
        except Exception as e:
            # Fallback to simple date range if preference calculation fails
            simple_dates = []
            current = start_date
            while current <= end_date:
                simple_dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            return simple_dates


    def _has_team_conflict_with_scheduling_state(self, match: Match, date: str) -> bool:
        """
        Check team conflicts considering both database and in-memory scheduling state
        
        Args:
            match: Match to check
            date: Date to check
            
        Returns:
            True if there's a conflict
        """
        # Check database conflicts first
        database_conflicts = (self.db.team_manager.check_team_date_conflict(match.home_team, date, exclude_match=match) or
                             self.db.team_manager.check_team_date_conflict(match.visitor_team, date, exclude_match=match))
        
        if database_conflicts:
            return True
        
        # Check scheduling state (for conflicts within current transaction/dry-run)
        if hasattr(self.db, 'scheduling_state') and self.db.scheduling_state:
            if (self.db.scheduling_state.has_team_conflict(match.home_team.id, date) or
                self.db.scheduling_state.has_team_conflict(match.visitor_team.id, date)):
                return True
        
        return False


    def get_auto_scheduling_summary(self, league: Optional[League] = None) -> Dict[str, Any]:
        """
        Get summary of auto-scheduling opportunities and constraints
        
        Args:
            league: Optional league to filter by
            
        Returns:
            Dictionary with scheduling analysis
        """
        try:
            # Get unscheduled matches
            if league:
                unscheduled_matches = self.list_matches(league=league, match_type=MatchType.UNSCHEDULED)
            else:
                unscheduled_matches = self.list_matches(match_type=MatchType.UNSCHEDULED)
            
            if not unscheduled_matches:
                return {
                    'total_unscheduled': 0,
                    'message': 'No unscheduled matches found'
                }
            
            # Analyze scheduling constraints
            facilities_available = len(self.db.facility_manager.list_facilities())
            
            # Count matches by league
            league_breakdown = {}
            for match in unscheduled_matches:
                league_name = match.league.name
                if league_name not in league_breakdown:
                    league_breakdown[league_name] = {
                        'count': 0,
                        'allow_split_lines': match.league.allow_split_lines,
                        'lines_per_match': match.league.num_lines_per_match
                    }
                league_breakdown[league_name]['count'] += 1
            
            return {
                'total_unscheduled': len(unscheduled_matches),
                'facilities_available': facilities_available,
                'league_breakdown': league_breakdown,
                'schedulable': facilities_available > 0,
                'recommendation': (
                    f"Ready to auto-schedule {len(unscheduled_matches)} matches across "
                    f"{len(league_breakdown)} league(s) using {facilities_available} facilities"
                    if facilities_available > 0 else
                    "Cannot auto-schedule: no facilities available"
                )
            }
            
        except Exception as e:
            return {
                'error': f"Error analyzing auto-scheduling opportunities: {e}",
                'total_unscheduled': 0
            }

    # ========== PRIVATE HELPER METHODS ==========

    from usta import FacilityAvailabilityInfo
    
    def _get_times_for_mode(self, match: Match, facility_info: 'FacilityAvailabilityInfo', mode: str) -> List[str]:
        """
        Try to get available times based on the mode, then select the appropriate times based on the mode.
        """
        lines_needed = match.league.num_lines_per_match if match.league else 3
        
        if mode == 'same_time':
            # Need exactly one time slot that can accommodate all lines
            available_times = facility_info.get_available_times_for_courts(lines_needed)
            return available_times[:1] if len(available_times) >= 1 else []

        elif mode == 'split_times':
            # Need exactly two time slots that can accommodate half the lines each
            courts_per_slot = math.ceil(lines_needed / 2)
            available_times = facility_info.get_available_times_for_courts(courts_per_slot)
            return available_times[:2] if len(available_times) >= 2 else []
        
        
        elif mode == 'custom':
            # For custom mode, return all available times
            return facility_info.get_available_times()
            
        return []
    
    def _validate_scheduling_times(self, times: List[str], mode: str, 
                                 lines_needed: int, facility_info) -> Optional[str]:
        """Validate scheduling times based on mode"""
        if mode == 'same_time':
            if len(times) != 1:
                return "Same time mode requires exactly one time slot"
            if not facility_info.check_time_availability(times[0], lines_needed):
                return f"Time {times[0]} cannot accommodate {lines_needed} courts"
                
        elif mode == 'split_times':
            if len(times) != 2:
                return "Split times mode requires exactly two time slots"
            courts_per_slot = math.ceil(lines_needed / 2)
            if not facility_info.check_time_availability(times[0], courts_per_slot):
                return f"Time {times[0]} cannot accommodate {courts_per_slot} courts"
            if not facility_info.check_time_availability(times[1], courts_per_slot):
                return f"Time {times[1]} cannot accommodate {courts_per_slot} courts"
            
            # Check time gap (at least 1 hour apart)
            try:
                dt1 = datetime.strptime(times[0], '%H:%M')
                dt2 = datetime.strptime(times[1], '%H:%M')
                if dt2 < dt1:
                    dt2 += timedelta(days=1)
                if dt2 - dt1 < timedelta(hours=1):
                    return "Split time slots must be at least 1 hour apart"
            except ValueError:
                return "Invalid time format"
                
        elif mode == 'custom':
            if len(times) != lines_needed:
                return f"Custom mode requires exactly {lines_needed} time slots"
            for i, time in enumerate(times):
                if not facility_info.check_time_availability(time, 1):
                    return f"Time {time} (line {i+1}) is not available"
            
            # Check for duplicate times that exceed capacity
            time_counts = Counter(times)
            for time, count in time_counts.items():
                if not facility_info.check_time_availability(time, count):
                    return f"Time {time} cannot accommodate {count} courts"
                    
        elif mode != 'auto':
            return f"Unknown scheduling mode: {mode}"
        
        return None  # No validation errors

    def _generate_scheduled_times(self, times: List[str], mode: str, lines_needed: int) -> List[str]:
        """Generate final scheduled times based on mode"""
        if mode == 'same_time':
            return [times[0]] * lines_needed
            
        elif mode == 'split_times':
            # Split lines between two time slots
            courts_per_slot = math.ceil(lines_needed / 2)
            lines_in_second_slot = lines_needed - courts_per_slot
            return ([times[0]] * courts_per_slot + [times[1]] * lines_in_second_slot)
            
        elif mode == 'custom':
            return times.copy()
            
        return []

    def _get_facilities_to_try(self, match: Match, facilities: Optional[List[Facility]], 
                             prefer_home_facility: bool) -> List[Facility]:
        """Get ordered list of facilities to try for scheduling"""
        if facilities:
            return facilities
        
        # Get all facilities
        all_facilities = self.db.facility_manager.list_facilities()
        
        if prefer_home_facility and match.home_team.home_facility:
            # Put home facility first
            home_facility = match.home_team.home_facility
            other_facilities = [f for f in all_facilities if f.id != home_facility.id]
            return [home_facility] + other_facilities
        
        return all_facilities

    def _has_team_date_conflicts(self, match: Match, date: str) -> bool:
        """Check if either team has a conflict on the given date, considering both database and scheduling state"""
        return self._has_team_conflict_with_scheduling_state(match, date)



    def _execute_scheduling(self, match: Match, facility: Facility, date: str, 
                          scheduled_times: List[str]) -> bool:
        """Execute the actual scheduling operation"""
        try:
            # Update match object
            match.facility = facility
            match.date = date
            match.scheduled_times = scheduled_times
            
            # Update scheduling state for conflict detection
            if hasattr(self.db, 'scheduling_state') and self.db.scheduling_state:
                for time in scheduled_times:
                    self.db.scheduling_state.book_time_slot(match.id, facility.id, date, time)
                self.db.scheduling_state.book_team_date(match.id, match.home_team.id, date)
                self.db.scheduling_state.book_team_date(match.id, match.visitor_team.id, date)
            
            # Update database
            return self._update_match_in_db(match)
            
        except Exception as e:
            print(f"Error executing scheduling: {e}")
            return False

    def _update_match_in_db(self, match: Match) -> bool:
        """Update match in database with transaction awareness"""
        try:
            # Verify related entities exist (skip in dry-run for performance)
            if not getattr(self.db, 'dry_run_active', False):
                if not self.db.league_manager.get_league(match.league.id):
                    raise ValueError(f"League with ID {match.league.id} does not exist")
                if not self.db.team_manager.get_team(match.home_team.id):
                    raise ValueError(f"Home team with ID {match.home_team.id} does not exist")
                if not self.db.team_manager.get_team(match.visitor_team.id):
                    raise ValueError(f"Visitor team with ID {match.visitor_team.id} does not exist")
                if match.facility and not self.db.facility_manager.get_facility(match.facility.id):
                    raise ValueError(f"Facility with ID {match.facility.id} does not exist")
            
            # Serialize scheduled times to JSON
            scheduled_times_json = json.dumps(match.scheduled_times) if match.scheduled_times else None
            
            # Determine status
            status = 'scheduled' if match.is_scheduled() else 'unscheduled'
            
            # Prepare operation description for transaction logging
            operation_desc = f"Update match {match.id}: {match.home_team.name} vs {match.visitor_team.name}"
            if match.facility:
                operation_desc += f" at {match.facility.name}"
            if match.date:
                operation_desc += f" on {match.date}"
            if match.scheduled_times:
                operation_desc += f" at {', '.join(match.scheduled_times)}"
            
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
                match.facility.id if match.facility else None,
                match.date,
                scheduled_times_json,
                status,
                match.round,
                match.num_rounds,
                match.id
            )
            
            # Execute with transaction awareness
            if hasattr(self.db, 'execute_operation'):
                self.db.execute_operation('update_match', query, params, operation_desc)
            else:
                self.cursor.execute(query, params)
            
            return True
            
        except Exception as e:
            raise RuntimeError(f"Error updating match in database: {e}")

    # ========== ADDITIONAL UTILITY METHODS ==========
    
    def preview_match_scheduling(self, 
                                 match: Match,
                                 date: str, 
                                 times: List[str], 
                                 scheduling_mode: str) -> Dict[str, Any]:
        """
        Preview what would happen if scheduling a match without actually doing it.

        Args:
            match: Match object to preview scheduling for
            date: Date to schedule the match
            times: List of proposed times for the match
            mode: Scheduling mode ('same_time', 'split_times', 'custom', etc.)
        
        Returns detailed information about conflicts, availability, and proposed schedule
        """
        try:
            lines_needed = match.league.num_lines_per_match if match.league else 3

            # Validate input parameters
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            if not isinstance(date, str):
                raise TypeError(f"Expected date as string, got: {type(date)}")
            if not isinstance(times, list):
                raise TypeError(f"Expected times as list, got: {type(times)}")
            if scheduling_mode not in ['same_time', 'split_times', 'custom', 'auto']:
                raise ValueError(f"Invalid scheduling mode: {scheduling_mode}")
            if not times:
                raise ValueError("Times list cannot be empty for scheduling preview")


            # Check to see if there are team conflicts for the match on the given date
            valid_dates = self.filter_match_conflicts(match, [date])
            if not valid_dates:
                return {
                    'schedulable': False,
                    'conflicts': [{'type': 'team_conflict', 'message': 'Team conflict detected on the given date'}],
                    'proposed_times': [],
                    'mode': scheduling_mode,
                    'lines_needed': lines_needed
                }
            date = valid_dates[0]  # Use the first valid date


            # Check if match has a facility assigned
            if not match.facility:
                return {
                    'schedulable': False,
                    'conflicts': [{'type': 'no_facility', 'message': 'No facility assigned to match'}],
                    'proposed_times': [],
                    'mode': scheduling_mode,
                    'lines_needed': lines_needed
                }
            

            # Initialize preview result
            preview_result = {
                'schedulable': False,
                'conflicts': [],
                'proposed_times': times,
                'mode': scheduling_mode,
                'lines_needed': lines_needed,
                'date': date,
                'facility_name': match.facility.name if match.facility else 'Unknown Facility',
                'scheduling_mode': scheduling_mode,
                'scheduling_details': f'Attempting to schedule {lines_needed} lines using {scheduling_mode} mode',
                'success': False,
                'warnings': [],
                'operations': []
            }

            # Get facility availability
            availability_list = self.db.facility_manager.get_facility_availability(
                facility=match.facility, dates=[date], max_days=1
            )
            # If no availability or facility is not available, return conflict
            if not availability_list or not availability_list[0].available:
                preview_result['conflicts'].append({
                    'type': 'facility_unavailable',
                    'message': f"Facility {match.facility.name} not available on {date}"
                })
                return preview_result
            
            facility_info = availability_list[0]

            # Validate scheduling times based on mode
            proposed_times = []
            
            # For 'same_time' mode, we need each time slot to accommodate all lines.
            if scheduling_mode == 'same_time':
                valid_times = facility_info.get_times_with_min_courts(lines_needed)
                if not valid_times:
                    preview_result['conflicts'].append({
                        'type': 'no_available_times',
                        'message': f"No available times for mode '{scheduling_mode}' with {lines_needed} lines"
                    })
                    return preview_result
                
                # any time is fine for same time mode
                proposed_times = valid_times 

            elif scheduling_mode == 'split_times':
                # For 'split_times', we need two time slots that can accommodate half the lines each
                courts_per_slot = math.ceil(lines_needed / 2)
                valid_times = facility_info.get_times_with_min_courts(courts_per_slot)
                if len(valid_times) < 2:
                    preview_result['conflicts'].append({
                        'type': 'no_available_times',
                        'message': f"Not enough available times for mode '{scheduling_mode}' with {lines_needed} lines"
                    })
                    return preview_result
                proposed_times = valid_times[:2]

            elif scheduling_mode == 'custom':
                # Raise an unimplemented error for custom mode
                raise NotImplementedError("Custom scheduling mode is not implemented")
            
            elif scheduling_mode == 'auto':
                # Raise and unimplemented error for auto mode
                raise NotImplementedError("Auto scheduling mode is not implemented")
            
            # if we reach here, we have valid proposed times
            preview_result['schedulable'] = True
            preview_result['proposed_times'] = proposed_times
            preview_result['success'] = True
            preview_result['scheduling_details'] = f'Successfully found {len(proposed_times)} available time slots for {lines_needed} lines using {scheduling_mode} mode'
            preview_result['operations'] = [
                {'type': 'update_match', 'description': f'Update match {match.id} with {scheduling_mode} scheduling'},
                {'type': 'set_facility', 'description': f'Set facility to {match.facility.name}'},
                {'type': 'set_date', 'description': f'Set date to {date}'},
                {'type': 'set_times', 'description': f'Set times to {", ".join(proposed_times)}'}
            ]

            return preview_result
            
        except Exception as e:
            return {
                'schedulable': False,
                'conflicts': [{'type': 'exception', 'message': str(e)}],
                'proposed_times': [],
                'mode': scheduling_mode
            }

    def _check_facility_time_conflicts(self, facility_id: int, date: str, 
                                     time: str, exclude_match_id: Optional[int] = None) -> List[Dict]:
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
                
                if match_data['scheduled_times']:
                    try:
                        scheduled_times = json.loads(match_data['scheduled_times'])
                        if isinstance(scheduled_times, list):
                            for scheduled_time in scheduled_times:
                                # Check if there's a time overlap
                                scheduled_start = datetime.strptime(f"{date} {scheduled_time}", "%Y-%m-%d %H:%M")
                                scheduled_end = scheduled_start + timedelta(hours=duration_hours)
                                
                                # Check for overlap
                                if (start_time < scheduled_end and end_time > scheduled_start):
                                    conflicts.append({
                                        'type': 'facility_time_conflict',
                                        'match_id': match_data['id'],
                                        'conflicting_time': scheduled_time,
                                        'home_team': match_data['home_team_name'],
                                        'visitor_team': match_data['visitor_team_name'],
                                        'message': f"Facility already has match at {scheduled_time}"
                                    })
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            return conflicts
            
        except Exception as e:
            return [{'type': 'error', 'message': f"Error checking conflicts: {e}"}]

    # ========== OTHER EXISTING METHODS (unchanged) ==========
    
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

    def filter_match_conflicts(self, match: Match, dates: List[str]) -> List[str]:
        """
        Filter out dates where either team is already scheduled
        
        Args:
            match: Match object to check conflicts for
            dates: List of candidate dates in YYYY-MM-DD format
            
        Returns:
            List of dates with no team conflicts (subset of input dates)
        """
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        if not isinstance(dates, list):
            raise TypeError(f"Expected list of dates, got: {type(dates)}")
        
        if not dates:
            return []
        
        try:
            # Query database for existing scheduled matches for both teams on these dates
            placeholders = ','.join(['?' for _ in dates])
            query = """
            SELECT DISTINCT date 
            FROM matches 
            WHERE status = 'scheduled' 
                AND date IN ({}) 
                AND (home_team_id = ? OR visitor_team_id = ? OR home_team_id = ? OR visitor_team_id = ?)
                AND id != ?
            """.format(placeholders)
            
            params = dates + [match.home_team.id, match.home_team.id, match.visitor_team.id, match.visitor_team.id, match.id]
            
            self.cursor.execute(query, params)
            conflicted_dates = {row['date'] for row in self.cursor.fetchall()}
            
            # Check scheduling state for conflicts within current transaction/dry-run
            if hasattr(self.db, 'scheduling_state') and self.db.scheduling_state:
                for date in dates:
                    if (self.db.scheduling_state.has_team_conflict(match.home_team.id, date) or
                        self.db.scheduling_state.has_team_conflict(match.visitor_team.id, date)):
                        conflicted_dates.add(date)
            
            # Return dates without conflicts
            return [date for date in dates if date not in conflicted_dates]
            
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error filtering match conflicts: {e}")
