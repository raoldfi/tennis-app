"""
Scheduling Management Helper for SQLite Tennis Database

Handles all scheduling-related operations including match scheduling,
team conflict checking, auto-scheduling, and scheduling analytics.

Updated to work without Line class - uses match scheduled_times instead.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from usta import Match, League, Team, Facility


class SQLSchedulingManager:
    """Helper class for managing scheduling operations in SQLite database"""
    
    def __init__(self, cursor: sqlite3.Cursor, db_instance):
        """
        Initialize SQLSchedulingManager
        
        Args:
            cursor: SQLite cursor for database operations
            db_instance: Reference to main database instance for accessing other managers
        """
        self.cursor = cursor
        self.db = db_instance
    
    def _dictify(self, row) -> dict:
        """Convert sqlite Row object to dictionary"""
        return dict(row) if row else {}

    def get_team_conflicts(self, team_id: int, date: str, time: str, duration_hours: int = 3) -> List[Dict]:
        """
        Check for scheduling conflicts for a team at a specific date/time
        
        Args:
            team_id: Team to check
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            duration_hours: Duration of the event in hours
            
        Returns:
            List of conflict descriptions
        """
        try:
            # Calculate end time
            start_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(hours=duration_hours)
            
            conflicts = []
            
            # Check for matches scheduled on the same date
            self.cursor.execute("""
                SELECT m.id, m.date, m.scheduled_times, m.facility_id,
                       ht.name as home_team_name, vt.name as visitor_team_name,
                       f.name as facility_name
                FROM matches m
                LEFT JOIN teams ht ON m.home_team_id = ht.id
                LEFT JOIN teams vt ON m.visitor_team_id = vt.id
                LEFT JOIN facilities f ON m.facility_id = f.id
                WHERE (m.home_team_id = ? OR m.visitor_team_id = ?)
                AND m.date = ?
                AND m.status = 'scheduled'
                AND m.scheduled_times IS NOT NULL
            """, (team_id, team_id, date))
            
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
                                        'type': 'team_time_conflict',
                                        'match_id': match_data['id'],
                                        'conflicting_time': scheduled_time,
                                        'home_team': match_data['home_team_name'],
                                        'visitor_team': match_data['visitor_team_name'],
                                        'facility': match_data['facility_name'],
                                        'reason': f"Team already has match at {scheduled_time}"
                                    })
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Error checking team conflicts: {e}")

    
    def get_facility_conflicts(self, facility_id: int, date: str, time: str, duration_hours: int = 3, 
                             exclude_match_id: Optional[int] = None) -> List[Dict]:
        """
        Check for scheduling conflicts at a facility
        
        Args:
            facility_id: Facility to check
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            duration_hours: Duration of the event in hours
            exclude_match_id: Match ID to exclude from conflict checking
            
        Returns:
            List of conflict descriptions
        """
        try:
            # Calculate end time
            start_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(hours=duration_hours)
            
            conflicts = []
            
            # Get facility information
            facility = self.db.facility_manager.get_facility(facility_id)
            if not facility:
                return [{'type': 'facility_not_found', 'reason': f"Facility {facility_id} not found"}]
            
            # Check if facility is available on this date
            if not facility.is_available_on_date(date):
                conflicts.append({
                    'type': 'facility_unavailable',
                    'reason': f"Facility {facility.name} is marked as unavailable on {date}"
                })
            
            # Check for other matches at this facility on this date
            query = """
                SELECT m.id, m.scheduled_times, 
                       ht.name as home_team_name, vt.name as visitor_team_name
                FROM matches m
                LEFT JOIN teams ht ON m.home_team_id = ht.id
                LEFT JOIN teams vt ON m.visitor_team_id = vt.id
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
                                        'reason': f"Facility already has match at {scheduled_time}"
                                    })
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Error checking facility conflicts: {e}")



    def is_schedulable(self, match: Match, date: str, 
                       facility: Optional['Facility'] = None,
                       allow_split_lines: Optional[bool]=False) -> bool:
        """
        Check if a match can be scheduled on a specific date
        
        This is a simple boolean function that uses the same logic as auto_schedule_match
        to determine if scheduling is possible.
        
        Args:
            match: Match object to check
            date: Date string in YYYY-MM-DD format
            facility: Optional facility to check. If None, uses home team's facility or tries all facilities
            
        Returns:
            True if the match can be scheduled on this date, False otherwise
            
        Examples:
            # Check if match can be scheduled at home facility
            can_schedule = db.scheduling_manager.is_schedulable(match, '2025-06-25')
            
            # Check if match can be scheduled at specific facility
            facility = db.get_facility(5)
            can_schedule = db.scheduling_manager.is_schedulable(match, '2025-06-25', facility)
        """
        try:
            print(f"\n\n IS_SCHEDULABLE: Checking {date}\n\n")
            
            if not isinstance(match, Match):
                return False
            
            if not date or not isinstance(date, str):
                return False
            
            # Validate date format
            try:
                from datetime import datetime
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError as ve:
                print(f"DATETIME ERROR {ve}")
                raise ve
                return False
            
            # STEP 1: Check team conflicts first (blocking check)
            # Use same logic as auto_schedule_match and filter_dates_by_availability

            try:
                # Check home team conflicts
                if self.db.check_team_date_conflict(team=match.home_team, 
                                                    date=date):
                    return False
                
                # Check visitor team conflicts  
                if self.db.check_team_date_conflict(team=match.visitor_team, 
                                                    date=date):
                    return False
            except Exception as date_error:
                print(f"\n\n ==== Team Conflict error: {date_error}\n\n")
                raise date_error
            
            # STEP 2: Check facility availability           
            if not facility:
                facility = match.home_team.home_facility
            
            
            # Check each facility until we find one that works
            lines_needed = match.get_expected_lines()

            try:
            
                # Check if facility is available on this date
                if facility.is_available_on_date(date):
                
                    # Check to see if this facilty can accommodate the number of lines
                    can_accommodate = self.db.facility_manager.can_accommodate_lines_on_date(facility=facility,
                                                                                 date=date,
                                                                                 num_lines=lines_needed,
                                                                                 allow_split_lines=allow_split_lines)
    
                    print(f"\n\n === {can_accommodate}: Checked to see if facility {facility.short_name} "
                          f"can accommodate {lines_needed}, allow_split_lines={allow_split_lines}")
    
                    if can_accommodate:
                        return True
                
                return False
                
            except Exception as accom_err:
                # Any unexpected error means we can't schedule
                print(f"\n\n ==== Error calling can_accommodate: {e}")
                raise e
                return False
            
            
        except Exception as e:
            # Any unexpected error means we can't schedule
            print(f"Error in is_schedulable: {e}")
            raise e
            return False
    
    

    def batch_is_schedulable(self, match: Match, date_list: List[str], 
                            facility: Optional['Facility'] = None) -> Dict[str, bool]:
        """
        Check schedulability for multiple dates at once
        
        Args:
            match: Match object to check
            date_list: List of date strings (YYYY-MM-DD)
            facility: Optional facility to check for all dates
            
        Returns:
            Dictionary mapping date strings to boolean schedulability:
            {
                '2025-06-25': True,
                '2025-06-26': False,
                '2025-06-27': True
            }
        """
        try:
            results = {}
            
            for current_date_str in date_list:
                try:
                    results[current_date_str] = self.is_schedulable(match=match, date=current_date_str, facility=facility)
                except Exception as e:
                    print(f"Error checking {current_date_str}: {e}")
                    results[current_date_str] = False
            
            return results
            
        except Exception as e:
            print(f"Error in batch_is_schedulable: {e}")
            return {date_str: False for date_str in date_list}
    
    
    def count_schedulable_dates(self, match: Match, start_date: str, end_date: str, 
                               facility: Optional['Facility'] = None) -> Dict[str, Any]:
        """
        Count how many dates in a range are schedulable for a match
        
        Args:
            match: Match object to check
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            facility: Optional facility to check
            
        Returns:
            Dictionary with count information:
            {
                'total_dates_checked': int,
                'schedulable_dates': int,
                'blocked_dates': int,
                'schedulability_percentage': float,
                'first_available_date': str or None,
                'sample_available_dates': List[str]
            }
        """
        try:
            from datetime import datetime, timedelta
            
            # Generate date range
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            dates_to_check = []
            current_dt = start_dt
            
            while current_dt <= end_dt:
                dates_to_check.append(current_dt.strftime('%Y-%m-%d'))
                current_dt += timedelta(days=1)
            
            # Check all dates
            schedulable_results = self.batch_is_schedulable(match, dates_to_check, facility)
            
            # Calculate statistics
            schedulable_dates = [date for date, is_schedulable in schedulable_results.items() if is_schedulable]
            blocked_dates = [date for date, is_schedulable in schedulable_results.items() if not is_schedulable]
            
            total_checked = len(dates_to_check)
            schedulable_count = len(schedulable_dates)
            blocked_count = len(blocked_dates)
            
            percentage = (schedulable_count / total_checked * 100) if total_checked > 0 else 0
            
            first_available = schedulable_dates[0] if schedulable_dates else None
            sample_dates = schedulable_dates[:10]  # First 10 available dates
            
            return {
                'total_dates_checked': total_checked,
                'schedulable_dates': schedulable_count,
                'blocked_dates': blocked_count,
                'schedulability_percentage': round(percentage, 1),
                'first_available_date': first_available,
                'sample_available_dates': sample_dates,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                }
            }
            
        except Exception as e:
            raise e

    
    
    
    def auto_schedule_match(self, match: Match, preferred_dates: List[str]) -> bool:
        """
        Attempt to automatically schedule a single match using the new consolidated scheduling methods
        
        Args:
            match: Match object to schedule
            preferred_dates: List of dates to try (in order of preference)
            
        Returns:
            True if match was successfully scheduled
        """
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            
            # Get all available facilities
            all_facilities = self.db.facility_manager.list_facilities()
            
            # Prioritize home team's facility if it exists
            facilities_to_check = []
            if match.home_team.home_facility:
                facilities_to_check.append(match.home_team.home_facility)
                # Add other facilities after home facility
                other_facilities = [f for f in all_facilities if f.id != match.home_team.home_facility.id]
                facilities_to_check.extend(other_facilities)
            else:
                facilities_to_check = all_facilities

            print(f"\n\n====== Trying to schedule match {match.id}, preferred_dates = {preferred_dates[:3]}...\n\n")

            # Strategy 1: Try to schedule all lines at the same time (preferred)
            for date in preferred_dates:
                # Check for team date conflicts first using existing method
                if (self.db.team_manager.check_team_date_conflict(match.home_team, date) or
                    self.db.team_manager.check_team_date_conflict(match.visitor_team, date)):
                    continue
                
                for facility in facilities_to_check:
                    # Check if facility is available on this date
                    if not facility.is_available_on_date(date):
                        continue
                    
                    # Get available times that can accommodate all lines
                    available_times = self.db.facility_manager.get_available_times_at_facility(
                        facility.id, date, match.league.num_lines_per_match
                    )
                    
                    if available_times:
                        # Try to schedule all lines at the same time
                        result = self.db.match_manager.schedule_match(
                            match, facility, date, [available_times[0]], 'same_time'
                        )
                        
                        if result['success']:
                            print(f"Successfully scheduled match {match.id} (same time) at {facility.name} on {date} at {available_times[0]}")
                            return True

            # Strategy 2: Try split scheduling if league allows it
            if match.league.allow_split_lines:
                for date in preferred_dates:
                    # Check for team date conflicts first
                    if (self.db.team_manager.check_team_date_conflict(match.home_team, date) or
                        self.db.team_manager.check_team_date_conflict(match.visitor_team)):
                        continue
                    
                    for facility in facilities_to_check:
                        # Check if facility is available on this date
                        if not facility.is_available_on_date(date):
                            continue
                        
                        # For split scheduling, we need times that can accommodate half the lines
                        import math
                        lines_per_slot = math.ceil(match.league.num_lines_per_match / 2)
                        
                        # Get available times that can accommodate split scheduling
                        available_times = self.db.facility_manager.get_available_times_at_facility(
                            facility.id, date, lines_per_slot
                        )
                        
                        if len(available_times) >= 2:
                            # Try split scheduling with first two available times
                            result = self.db.match_manager.schedule_match(
                                match, facility, date, available_times[:2], 'split_times'
                            )
                            
                            if result['success']:
                                print(f"Successfully scheduled match {match.id} (split) at {facility.name} on {date} at {available_times[:2]}")
                                return True


            print(f"Failed to schedule match {match.id} - no suitable slots found")
            return False
            
        except Exception as e:
            print(f"Error auto-scheduling match {match.id}: {e}")
            raise RuntimeError(f"Error auto-scheduling match {match.id}: {e}")


    def _get_facility_dates_to_check(self, matches: List['Match']) -> Dict['Facility', set]:
        """Get facility dates to check for all matches"""
        facility_dates = {}
        
        for match in matches:
            facility = match.get_facility()
            if not facility:
                continue

            # Add prioritized scheduling dates for this match based on team and league preferences
            prioritized_dates_with_priority = match.get_prioritized_scheduling_dates()
            prioritized_dates = [date for date, priority in prioritized_dates_with_priority]
            
            if not prioritized_dates:
                print(f"No prioritized dates for match {match.id}, skipping")
                continue

            for date in prioritized_dates:

                # Ensure date is a string in YYYY-MM-DD format or a datetime object
                if isinstance(date, str):
                    # Ensure date is in YYYY-MM-DD format
                    try:
                        datetime.strptime(date, '%Y-%m-%d')
                    except ValueError:
                        print(f"Invalid date format for {date}, skipping")
                        continue
                elif isinstance(date, datetime):
                    # Convert datetime to string in YYYY-MM-DD format
                    date = date.strftime('%Y-%m-%d')
                else:
                    print(f"Unsupported date type {type(date)} for match {match.id}, skipping")
                    continue
                
                # Initialize facility_dates if not already present
                if facility not in facility_dates:
                    facility_dates[facility] = set()

                # Add the date to the facility's set of dates
                if date not in facility_dates[facility]:
                    facility_dates[facility].add(date)
        
        # Convert sets to lists for consistent ordering
        for facility, dates in facility_dates.items():
            facility_dates[facility] = list(dates)
        
        
        # Return a dictionary mapping Facility to list of dates
        return facility_dates
    
        


    def get_scheduling_summary(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get scheduling summary statistics
        
        Args:
            league_id: Optional league to filter by
            
        Returns:
            Dictionary with scheduling statistics
        """
        try:
            if league_id:
                # League-specific summary
                league = self.db.league_manager.get_league(league_id)
                if not league:
                    raise ValueError(f"League with ID {league_id} does not exist")
                
                matches = self.db.match_manager.list_matches(league_id=league_id, include_unscheduled=True)
                
                summary = {
                    'league_id': league_id,
                    'league_name': league.name,
                    'total_matches': len(matches),
                    'scheduled_matches': len([m for m in matches if m.is_scheduled()]),
                    'unscheduled_matches': len([m for m in matches if m.is_unscheduled()]),
                    'partially_scheduled_matches': len([m for m in matches if m.is_partially_scheduled()]),
                    'fully_scheduled_matches': len([m for m in matches if m.is_fully_scheduled()])
                }
                
                # Calculate total scheduled times
                total_scheduled_times = sum(len(m.scheduled_times) for m in matches)
                expected_total_times = len(matches) * league.num_lines_per_match
                
                summary.update({
                    'total_scheduled_times': total_scheduled_times,
                    'expected_total_times': expected_total_times,
                    'scheduling_completion_percentage': round((total_scheduled_times / expected_total_times * 100) if expected_total_times > 0 else 0, 2)
                })
                
            else:
                # System-wide summary
                all_matches = self.db.match_manager.list_matches(include_unscheduled=True)
                
                summary = {
                    'system_wide': True,
                    'total_matches': len(all_matches),
                    'scheduled_matches': len([m for m in all_matches if m.is_scheduled()]),
                    'unscheduled_matches': len([m for m in all_matches if m.is_unscheduled()]),
                }
                
                # Get league breakdown
                leagues = self.db.league_manager.list_leagues()
                league_breakdown = []
                
                for league in leagues:
                    league_matches = [m for m in all_matches if m.league.id == league.id]
                    league_breakdown.append({
                        'league_id': league.id,
                        'league_name': league.name,
                        'total_matches': len(league_matches),
                        'scheduled_matches': len([m for m in league_matches if m.is_scheduled()]),
                        'unscheduled_matches': len([m for m in league_matches if m.is_unscheduled()])
                    })
                
                summary['league_breakdown'] = league_breakdown
            
            return summary
            
        except Exception as e:
            raise RuntimeError(f"Error getting scheduling summary: {e}")



    
    
    def _generate_league_candidate_dates(self, league: League, start_date: str, end_date: str) -> List[str]:
        """Generate candidate dates for scheduling based on league preferences"""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            candidate_dates = []
            current = start_dt
            
            # Priority levels for dates
            while current <= end_dt:
                day_name = current.strftime('%A')
                current_date_str = current.strftime('%Y-%m-%d')
                
                # Priority: 1 = preferred days, 2 = backup days, 3 = other allowed days
                priority = 3
                if day_name in league.preferred_days:
                    priority = 1
                elif day_name in league.backup_days:
                    priority = 2
                
                # Only include days that the league allows
                if priority <= 3:  # All allowed days
                    candidate_dates.append((current_date_str, priority))
                
                current += timedelta(days=1)
            
            # Sort by priority, then by date
            candidate_dates.sort(key=lambda x: (x[1], x[0]))
            
            # Return just the date strings
            return [date for date, _ in candidate_dates]
            
        except Exception as e:
            raise RuntimeError(f"Error generating candidate dates: {e}")

    def _has_team_date_conflict(self, match: Match, date: str) -> bool:
        """Check if either team has a conflict on the given date"""
        try:
            # Check home team
            home_conflicts = self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM matches 
                WHERE (home_team_id = ? OR visitor_team_id = ?)
                AND date = ?
                AND status = 'scheduled'
                AND id != ?
            """, (match.home_team.id, match.home_team.id, date, match.id)).fetchone()
            
            if home_conflicts['count'] > 0:
                return True
            
            # Check visitor team
            visitor_conflicts = self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM matches 
                WHERE (home_team_id = ? OR visitor_team_id = ?)
                AND date = ?
                AND status = 'scheduled'
                AND id != ?
            """, (match.visitor_team.id, match.visitor_team.id, date, match.id)).fetchone()
            
            return visitor_conflicts['count'] > 0
            
        except Exception as e:
            return True  # Assume conflict if error

    def _order_facilities_by_preference(self, match: Match, facility_ids: List[int]) -> List[int]:
        """Order facilities by preference (home team's facility first)"""
        try:
            # Get home team's facility ID
            home_facility_id = match.home_team.home_facility.id if match.home_team.home_facility else None
            
            ordered = []
            
            # Add home team's facility first if it's in the list
            if home_facility_id and home_facility_id in facility_ids:
                ordered.append(home_facility_id)
            
            # Add visitor team's facility second if different and in the list
            visitor_facility_id = match.visitor_team.home_facility.id if match.visitor_team.home_facility else None
            if visitor_facility_id and visitor_facility_id != home_facility_id and visitor_facility_id in facility_ids:
                ordered.append(visitor_facility_id)
            
            # Add remaining facilities
            for facility_id in facility_ids:
                if facility_id not in ordered:
                    ordered.append(facility_id)
            
            return ordered
            
        except Exception:
            return facility_ids  # Return original list if error