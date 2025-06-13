"""
Scheduling Management Helper for SQLite Tennis Database

Handles all scheduling-related operations including match scheduling,
team conflict checking, auto-scheduling, and scheduling analytics.

Updated to work without Line class - uses match scheduled_times instead.
"""

import sqlite3
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from usta import Match, League, Team
import utils


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


    def auto_schedule_match(self, match: Match, preferred_dates: List[str], 
                          prefer_home_facility: bool = True) -> bool:
        """
        Attempt to automatically schedule a single match
        
        Args:
            match: Match object to schedule
            preferred_dates: List of dates to try (in order of preference)
            prefer_home_facility: Whether to prefer the home team's facility
            
        Returns:
            True if match was successfully scheduled
        """
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            
            # Get facility IDs to try
            facility_ids = None
            if prefer_home_facility and match.home_team.home_facility:
                facility_ids = [match.home_team.home_facility.id]
            
            # Try each date in order
            for date in preferred_dates:
                # Check for team date conflicts first
                if (self.db.team_manager.check_team_date_conflict(match.home_team.id, date, exclude_match_id=match.id) or
                    self.db.team_manager.check_team_date_conflict(match.visitor_team.id, date, exclude_match_id=match.id)):
                    continue  # Skip this date and try the next one
                
                # Get facilities to try (prioritize home facility if specified)
                if facility_ids:
                    facilities_to_try = facility_ids
                else:
                    all_facilities = self.db.facility_manager.list_facilities()
                    facilities_to_try = [f.id for f in all_facilities]
                    # Still prioritize home team's facility if available
                    if match.home_team.home_facility:
                        home_facility_id = match.home_team.home_facility.id
                        if home_facility_id in facilities_to_try:
                            facilities_to_try.remove(home_facility_id)
                            facilities_to_try.insert(0, home_facility_id)
                
                # Try each facility for this date
                for facility_id in facilities_to_try:
                    facility = self.db.facility_manager.get_facility(facility_id)
                    if not facility:
                        continue
                    
                    # Check if facility is available on this date
                    if not facility.is_available_on_date(date):
                        continue
                    
                    # Get available times at this facility for this date
                    available_times = self.db.facility_manager.get_available_times_at_facility(
                        facility_id, date, match.get_expected_lines()
                    )
                    
                    # Try the first available time
                    for time in available_times:
                        # Attempt to schedule all lines at the same time
                        success = self.db.match_manager.schedule_match_all_lines_same_time(
                            match, facility, date, time
                        )
                        
                        if success:
                            return True
                        
                    # If same-time scheduling failed and league allows split lines, try sequential scheduling
                    if match.league.allow_split_lines and available_times:
                        try:
                            success = self.db.match_manager.schedule_match_sequential_times(
                                match, facility, date, available_times[0]
                            )
                            if success:
                                return True
                        except Exception:
                            continue  # Try next facility/date if sequential scheduling fails
            
            return False
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling match {match.id}: {e}")
    
    
    def auto_schedule_matches(self, matches: List[Match], dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule a list of matches
        
        Args:
            matches: List of Match objects to schedule
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        try:
            if not isinstance(matches, list):
                raise TypeError(f"Expected list of Match objects, got: {type(matches)}")
            
            for match in matches:
                if not isinstance(match, Match):
                    raise TypeError(f"All items in matches list must be Match objects, got: {type(match)}")
            
            results = {
                'total_matches': len(matches),
                'scheduled_successfully': 0,
                'failed_to_schedule': 0,
                'scheduling_details': [],
                'dry_run': dry_run,
                'matches_attempted': []
            }
            
            for match in matches:
                # Skip already scheduled matches
                if match.is_scheduled():
                    results['scheduling_details'].append({
                        'match_id': match.id,
                        'status': 'already_scheduled',
                        'home_team': match.home_team.name,
                        'visitor_team': match.visitor_team.name,
                        'facility': match.facility.name if match.facility else 'Unknown',
                        'date': match.date,
                        'times': match.scheduled_times
                    })
                    continue
                
                # Get optimal dates for this specific match (prioritizing team preferences)
                optimal_dates = utils.get_optimal_scheduling_dates(match)
                
                results['matches_attempted'].append({
                    'match_id': match.id,
                    'home_team': match.home_team.name,
                    'visitor_team': match.visitor_team.name,
                    'optimal_dates_tried': optimal_dates[:5]  # Show first 5 dates tried
                })

                print (f"\n\nTRYING TO SCHEDULE MATCH ON THESE DATES {optimal_dates}\n\n")
                
                
                success = self.auto_schedule_match(match, optimal_dates)
                
                if success:
                    results['scheduled_successfully'] += 1
                    # Reload match to get updated scheduling info (if not dry run)
                    if not dry_run:
                        updated_match = self.db.match_manager.get_match(match.id)
                        if updated_match:
                            results['scheduling_details'].append({
                                'match_id': match.id,
                                'status': 'scheduled',
                                'home_team': match.home_team.name,
                                'visitor_team': match.visitor_team.name,
                                'facility': updated_match.facility.name if updated_match.facility else 'Unknown',
                                'date': updated_match.date,
                                'times': updated_match.scheduled_times
                            })
                        else:
                            results['scheduling_details'].append({
                                'match_id': match.id,
                                'status': 'scheduled',
                                'home_team': match.home_team.name,
                                'visitor_team': match.visitor_team.name,
                                'note': 'Scheduled but unable to reload match details'
                            })
                    else:
                        results['scheduling_details'].append({
                            'match_id': match.id,
                            'status': 'would_schedule',
                            'home_team': match.home_team.name,
                            'visitor_team': match.visitor_team.name,
                            'note': 'Dry run - scheduling options available'
                        })
                else:
                    results['failed_to_schedule'] += 1
                    results['scheduling_details'].append({
                        'match_id': match.id,
                        'status': 'failed',
                        'home_team': match.home_team.name,
                        'visitor_team': match.visitor_team.name,
                        'reason': 'No available time slots found'
                    })
            
            # Calculate success rate
            attempted_matches = len([m for m in matches if not m.is_scheduled()])
            if attempted_matches > 0:
                success_rate = (results['scheduled_successfully'] / attempted_matches) * 100
                results['success_rate'] = round(success_rate, 2)
            else:
                results['success_rate'] = 100.0  # All matches were already scheduled
            
            results['already_scheduled'] = len(matches) - attempted_matches
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling matches: {e}")
    
    

    



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
                date_str = current.strftime('%Y-%m-%d')
                
                # Priority: 1 = preferred days, 2 = backup days, 3 = other allowed days
                priority = 3
                if day_name in league.preferred_days:
                    priority = 1
                elif day_name in league.backup_days:
                    priority = 2
                
                # Only include days that the league allows
                if priority <= 3:  # All allowed days
                    candidate_dates.append((date_str, priority))
                
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