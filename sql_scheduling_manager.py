"""
Scheduling Management Helper for SQLite Tennis Database

Handles all scheduling-related operations including match scheduling,
team conflict checking, auto-scheduling, and scheduling analytics.
"""

import sqlite3
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from usta import Match, League, Team


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
    
    def schedule_match_all_lines_same_time(
        self,
        match_id: int,
        facility_id: int,
        date: str,
        time: str
    ) -> bool:
        """
        Schedule all lines of a match at the same facility, date, and time.
        Returns True if successful, False if there is not enough capacity or conflicts exist.
        """
        try:
            # 1) Verify that the match exists (and load its lines)
            match = self.db.match_line_manager.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")

            # 2) Verify that the facility exists
            facility = self.db.facility_manager.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")

            # 3) Ensure lines exist for this match
            if not match.lines:
                league = self.db.league_manager.get_league(match.league_id)
                self.db.match_line_manager.create_lines_for_match(match_id, league)
                match = self.db.match_line_manager.get_match_with_lines(match_id)  # Reload with lines
            
            courts_needed = len(match.lines)

            # 4) Check for team date conflicts FIRST (before checking court availability)
            # Check if home team already has a match on this date
            home_date_conflict = self.db.team_manager.check_team_date_conflict(
                match.home_team_id, date, exclude_match_id=match_id
            )
            if home_date_conflict:
                return False
            
            # Check if visitor team already has a match on this date
            visitor_date_conflict = self.db.team_manager.check_team_date_conflict(
                match.visitor_team_id, date, exclude_match_id=match_id
            )
            if visitor_date_conflict:
                return False

            # 5) Check if the facility is open on that date & time, and has enough available courts
            availability_check = self.db.facility_manager.check_court_availability(
                facility_id, date, time, courts_needed
            )
            if not availability_check:
                return False

            # 6) Check for team facility conflicts (teams can't be at multiple facilities same day)
            home_facility_conflict = self.db.team_manager.check_team_facility_conflict(
                match.home_team_id, date, facility_id
            )
            if home_facility_conflict:
                return False
            
            visitor_facility_conflict = self.db.team_manager.check_team_facility_conflict(
                match.visitor_team_id, date, facility_id
            )
            if visitor_facility_conflict:
                return False

            # 7) All checks passed - update the match and lines
            self.cursor.execute("""
                UPDATE matches
                   SET facility_id = ?,
                       date        = ?,
                       time        = ?,
                       status      = 'scheduled'
                 WHERE id = ?
            """, (facility_id, date, time, match_id))

            # 8) Update all lines
            for line in match.lines:
                self.cursor.execute("""
                    UPDATE lines
                       SET facility_id = ?,
                           date        = ?,
                           time        = ?
                     WHERE id = ?
                """, (facility_id, date, time, line.id))

            return True

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error scheduling match {match_id}: {e}")
        except Exception as e:
            raise

    def schedule_match_split_lines(
        self,
        match_id: int,
        date: str,
        scheduling_plan: List[Tuple[str, int, int]]
    ) -> bool:
        """
        Schedule the lines of a single match across multiple (time, facility, num_lines) slots.

        Args:
            match_id: Match to schedule
            date: Date to schedule on
            scheduling_plan: List of (time_str, facility_id, num_lines_at_time) tuples

        Returns:
            True if all lines can be scheduled exactly as requested; returns False if
            any individual timeslot does not have enough courts.
        """
        try:
            # Verify that the match exists (and load its lines)
            match = self.db.match_line_manager.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")

            # Verify that the parent league allows split‐line scheduling
            league = self.db.league_manager.get_league(match.league_id)
            if not league.allow_split_lines:
                raise ValueError(f"League {league.name} does not allow split‐line scheduling")

            # Ensure the plan covers exactly as many lines as the match has
            total_planned_lines = sum(num_lines for _, _, num_lines in scheduling_plan)
            if total_planned_lines != len(match.lines):
                raise ValueError(
                    f"Scheduling plan covers {total_planned_lines} lines, "
                    f"but match {match_id} has {len(match.lines)} lines"
                )

            # Check if this match is already scheduled
            for line in match.lines:
                if line.date is not None or line.facility_id is not None:
                    raise RuntimeError(f"Match {match_id} is already scheduled. Unschedule it first.")

            # Check for team date conflicts FIRST
            home_date_conflict = self.db.team_manager.check_team_date_conflict(
                match.home_team_id, date, exclude_match_id=match_id
            )
            if home_date_conflict:
                raise ValueError(f"Home team {match.home_team_id} already has a match scheduled on {date}")
            
            visitor_date_conflict = self.db.team_manager.check_team_date_conflict(
                match.visitor_team_id, date, exclude_match_id=match_id
            )
            if visitor_date_conflict:
                raise ValueError(f"Visitor team {match.visitor_team_id} already has a match scheduled on {date}")

            # Check for team facility conflicts across all facilities in the plan
            facilities_in_plan = set(facility_id for _, facility_id, _ in scheduling_plan)
            
            for facility_id in facilities_in_plan:
                home_conflict = self.db.team_manager.check_team_facility_conflict(
                    match.home_team_id, date, facility_id
                )
                if home_conflict:
                    raise ValueError(
                        f"Home team {match.home_team_id} already scheduled at different facility on {date}"
                    )
                
                visitor_conflict = self.db.team_manager.check_team_facility_conflict(
                    match.visitor_team_id, date, facility_id
                )
                if visitor_conflict:
                    raise ValueError(
                        f"Visitor team {match.visitor_team_id} already scheduled at different facility on {date}"
                    )

            # Verify all timeslots have enough capacity before making any changes
            for (slot_time, slot_facility_id, num_lines_at_time) in scheduling_plan:
                if not self.db.facility_manager.check_court_availability(
                    slot_facility_id, date, slot_time, num_lines_at_time
                ):
                    return False

            # All checks passed, now schedule the lines
            line_index = 0
            primary_facility = None
            primary_time = None

            for (slot_time, slot_facility_id, num_lines_at_time) in scheduling_plan:
                # On the very first timeslot, remember it as the "primary"
                if primary_facility is None:
                    primary_facility = slot_facility_id
                    primary_time = slot_time

                # Schedule each line for this time slot
                for _ in range(num_lines_at_time):
                    if line_index >= len(match.lines):
                        break
                    this_line = match.lines[line_index]
                    self.cursor.execute("""
                        UPDATE lines
                           SET facility_id = ?,
                               date        = ?,
                               time        = ?
                         WHERE id = ?
                    """, (slot_facility_id, date, slot_time, this_line.id))
                    line_index += 1

            # Update the match row to reflect the "primary" slot
            self.cursor.execute("""
                UPDATE matches
                   SET facility_id = ?,
                       date        = ?,
                       time        = ?,
                       status      = 'scheduled'
                 WHERE id = ?
            """, (primary_facility, date, primary_time, match_id))

            return True

        except sqlite3.Error as e:
            raise RuntimeError(f"Database error scheduling split lines for match {match_id}: {e}")
        except Exception:
            raise

    def unschedule_match(self, match_id: int) -> None:
        """Unschedule a match and all its lines"""
        try:
            # Check if match exists
            existing_match = self.db.match_line_manager.get_match(match_id)
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

    def find_scheduling_options_for_match(self, match_id: int, preferred_dates: List[str], 
                                        facility_ids: Optional[List[int]] = None) -> Dict[str, List[Dict]]:
        """
        Find all possible scheduling options for a match
        
        Args:
            match_id: Match to schedule
            preferred_dates: List of preferred dates to check
            facility_ids: Optional list of facility IDs to check (if None, checks all)
            
        Returns:
            Dictionary mapping dates to scheduling options
        """
        try:
            # Get the match and verify it exists
            match = self.db.match_line_manager.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Get the league
            league = self.db.league_manager.get_league(match.league_id)
            if not league:
                raise ValueError(f"League with ID {match.league_id} does not exist")
            
            # Get facility list
            if facility_ids is None:
                all_facilities = self.db.facility_manager.list_facilities()
                facility_ids = [f.id for f in all_facilities]
            
            options = {}
            
            for date in preferred_dates:
                # Skip dates where either team already has a match
                if (self.db.team_manager.check_team_date_conflict(match.home_team_id, date, exclude_match_id=match_id) or
                    self.db.team_manager.check_team_date_conflict(match.visitor_team_id, date, exclude_match_id=match_id)):
                    continue
                
                date_options = []
                
                for facility_id in facility_ids:
                    facility = self.db.facility_manager.get_facility(facility_id)
                    if not facility:
                        continue
                    
                    # Get scheduling options for this facility/date
                    facility_options = facility.get_scheduling_options_for_match(league, date)
                    
                    if facility_options:
                        # Check if we have enough courts
                        day_name = list(facility_options.keys())[0]
                        available_times = facility_options[day_name]
                        
                        valid_times = []
                        for time in available_times:
                            if self.db.facility_manager.check_court_availability(
                                facility_id, date, time, league.get_total_courts_needed()
                            ):
                                valid_times.append(time)
                        
                        if valid_times:
                            date_options.append({
                                'facility_id': facility_id,
                                'facility_name': facility.name,
                                'day': day_name,
                                'times': valid_times,
                                'type': 'same_time'
                            })
                        
                        # Also check split line options if allowed
                        if league.allow_split_lines:
                            split_options = facility.find_scheduling_slots_for_split_lines(
                                day_name, league.get_total_courts_needed()
                            )
                            if split_options:
                                # Validate each split option against actual availability
                                valid_split_options = []
                                for option in split_options:
                                    is_valid = True
                                    for time_str, courts_needed in option:
                                        if not self.db.facility_manager.check_court_availability(
                                            facility_id, date, time_str, courts_needed
                                        ):
                                            is_valid = False
                                            break
                                    if is_valid:
                                        valid_split_options.append(option)
                                
                                if valid_split_options:
                                    date_options.append({
                                        'facility_id': facility_id,
                                        'facility_name': facility.name,
                                        'day': day_name,
                                        'split_options': valid_split_options,
                                        'type': 'split_lines'
                                    })
                
                if date_options:
                    options[date] = date_options
            
            return options
            
        except Exception as e:
            raise RuntimeError(f"Error finding scheduling options for match {match_id}: {e}")

    def auto_schedule_match(self, match_id: int, preferred_dates: List[str], 
                          prefer_home_facility: bool = True) -> bool:
        """
        Attempt to automatically schedule a single match
        
        Args:
            match_id: Match to schedule
            preferred_dates: List of dates to try (in order of preference)
            prefer_home_facility: Whether to prefer the home team's facility
            
        Returns:
            True if match was successfully scheduled
        """
        try:
            # Get the match and ensure it has lines
            match = self.db.match_line_manager.get_match_with_lines(match_id)
            if not match:
                raise ValueError(f"Match with ID {match_id} does not exist")
            
            # Ensure lines exist
            if not match.lines:
                league = self.db.league_manager.get_league(match.league_id)
                self.db.match_line_manager.create_lines_for_match(match_id, league)
                match = self.db.match_line_manager.get_match_with_lines(match_id)  # Reload with lines
            
            # Get home team's facility if preferring home facility
            facility_ids = None
            if prefer_home_facility:
                home_team = self.db.team_manager.get_team(match.home_team_id)
                if home_team:
                    facility_ids = [home_team.home_facility_id]
            
            # Try each date in order
            for date in preferred_dates:
                # Skip dates where either team already has a match
                if (self.db.team_manager.check_team_date_conflict(match.home_team_id, date, exclude_match_id=match_id) or
                    self.db.team_manager.check_team_date_conflict(match.visitor_team_id, date, exclude_match_id=match_id)):
                    continue  # Skip this date and try the next one
                
                # Find scheduling options for this date
                options_by_date = self.find_scheduling_options_for_match(match_id, [date], facility_ids)
                
                if date in options_by_date:
                    # Try the first available option
                    for option in options_by_date[date]:
                        try:
                            if option['type'] == 'same_time' and option['times']:
                                # Schedule all lines at the same time
                                time = option['times'][0]  # Use first available time
                                success = self.schedule_match_all_lines_same_time(
                                    match_id, option['facility_id'], date, time
                                )
                                if success:
                                    return True
                            
                            elif option['type'] == 'split_lines' and option['split_options']:
                                # Schedule lines across different times
                                split_option = option['split_options'][0]  # Use first split option
                                # Convert to the format expected by the database method
                                plan_tuples = [
                                    (time, option['facility_id'], courts) 
                                    for time, courts in split_option
                                ]
                                success = self.schedule_match_split_lines(match_id, date, plan_tuples)
                                if success:
                                    return True
                        except Exception:
                            # If this specific option fails, try the next one
                            continue
            
            return False
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling match {match_id}: {e}")

    def auto_schedule_matches(self, matches: List[Match], dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule a list of matches
        
        Args:
            matches: List of matches to schedule
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        try:
            results = {
                'total_matches': len(matches),
                'scheduled_successfully': 0,
                'failed_to_schedule': 0,
                'scheduling_details': [],
                'dry_run': dry_run
            }
            
            for match in matches:
                # Get optimal dates for this specific match (prioritizing team preferences)
                optimal_dates = self.get_optimal_scheduling_dates(match)
                
                if not dry_run:
                    success = self.auto_schedule_match(match.id, optimal_dates[:10])  # Try first 10 dates
                else:
                    # For dry run, just check if options exist
                    options = self.find_scheduling_options_for_match(match.id, optimal_dates[:5])
                    success = len(options) > 0
                
                if success:
                    results['scheduled_successfully'] += 1
                    results['scheduling_details'].append({
                        'match_id': match.id,
                        'status': 'scheduled',
                        'home_team_id': match.home_team_id,
                        'visitor_team_id': match.visitor_team_id
                    })
                else:
                    results['failed_to_schedule'] += 1
                    results['scheduling_details'].append({
                        'match_id': match.id,
                        'status': 'failed',
                        'home_team_id': match.home_team_id,
                        'visitor_team_id': match.visitor_team_id,
                        'reason': 'No available time slots found'
                    })
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling matches: {e}")

    def auto_schedule_league_matches(self, league_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Attempt to automatically schedule all unscheduled matches in a league
        
        Args:
            league_id: League to schedule matches for
            dry_run: If True, don't actually schedule, just report what would happen
            
        Returns:
            Dictionary with scheduling results and statistics
        """
        try:
            # Get the league
            league = self.db.league_manager.get_league(league_id)
            if not league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Get unscheduled matches
            all_matches = self.db.match_line_manager.list_matches_with_lines(league_id=league_id, include_unscheduled=True)
            unscheduled_matches = [m for m in all_matches if m.is_unscheduled()]
            
            # Use the auto_schedule_matches function
            results = self.auto_schedule_matches(unscheduled_matches, dry_run=dry_run)
            
            # Add league-specific information to results
            results['league_id'] = league_id
            results['total_unscheduled'] = results['total_matches']  # Backward compatibility
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling league matches: {e}")

    def get_optimal_scheduling_dates(self, match: Match, 
                                   start_date: Optional[str] = None,
                                   end_date: Optional[str] = None,
                                   num_dates: int = 20) -> List[str]:
        """
        Find optimal dates for scheduling a specific match, prioritizing team preferences
        
        Args:
            match: Match to find dates for
            start_date: Start date for search (defaults to league start_date)
            end_date: End date for search (defaults to league end_date)  
            num_dates: Number of dates to return
            
        Returns:
            List of date strings in YYYY-MM-DD format, ordered by preference
            (team preferred days first, then league preferred days, then backup days)
        """
        try:
            # Get the league
            league = self.db.league_manager.get_league(match.league_id)
            if not league:
                raise ValueError(f"League with ID {match.league_id} does not exist")
            
            # Get teams to understand their preferences
            home_team = self.db.team_manager.get_team(match.home_team_id)
            visitor_team = self.db.team_manager.get_team(match.visitor_team_id)
            
            if not home_team or not visitor_team:
                raise ValueError(f"Teams not found for match {match.id}")
            
            # Use league dates or reasonable defaults
            search_start = start_date or league.start_date or datetime.now().strftime('%Y-%m-%d')
            search_end = end_date or league.end_date
            
            if not search_end:
                # Default to 16 weeks from start
                start_dt = datetime.strptime(search_start, '%Y-%m-%d')
                end_dt = start_dt + timedelta(weeks=16)
                search_end = end_dt.strftime('%Y-%m-%d')
            
            # Generate candidate dates with priority system
            start_dt = datetime.strptime(search_start, '%Y-%m-%d')
            end_dt = datetime.strptime(search_end, '%Y-%m-%d')
            
            candidate_dates = []
            current = start_dt
            
            # Create combined team preferred days (intersection is highest priority)
            home_preferred = set(home_team.preferred_days)
            visitor_preferred = set(visitor_team.preferred_days)
            
            # Priority levels:
            # 1 = Both teams prefer this day
            # 2 = One team prefers this day
            # 3 = League prefers this day (but no team preference)
            # 4 = League backup day (but no team preference)
            # 5 = Day is allowed but not preferred by anyone
            
            while current <= end_dt:
                day_name = current.strftime('%A')
                date_str = current.strftime('%Y-%m-%d')
                
                # Skip days that the league doesn't allow
                if not league.can_schedule_on_day(day_name):
                    current += timedelta(days=1)
                    continue
                
                # Determine priority based on team and league preferences
                priority = 5  # Default: allowed but not preferred
                
                if day_name in home_preferred and day_name in visitor_preferred:
                    priority = 1  # Both teams prefer this day
                elif day_name in home_preferred or day_name in visitor_preferred:
                    priority = 2  # One team prefers this day
                elif day_name in league.preferred_days:
                    priority = 3  # League prefers this day
                elif day_name in league.backup_days:
                    priority = 4  # League backup day
                
                candidate_dates.append((date_str, priority))
                current += timedelta(days=1)
            
            # Sort by priority (lower number = higher priority)
            # For same priority, maintain chronological order
            candidate_dates.sort(key=lambda x: (x[1], x[0]))
            
            # Return the requested number of dates
            return [date for date, _ in candidate_dates[:num_dates]]
            
        except Exception as e:
            raise RuntimeError(f"Error getting optimal scheduling dates for match {match.id}: {e}")

    def validate_league_scheduling_feasibility(self, league_id: int) -> Dict[str, Any]:
        """
        Analyze whether it's feasible to schedule all matches in a league
        
        Args:
            league_id: League to analyze
            
        Returns:
            Dictionary with feasibility analysis
        """
        try:
            # Get the league
            league = self.db.league_manager.get_league(league_id)
            if not league:
                raise ValueError(f"League with ID {league_id} does not exist")
            
            # Get facilities and teams
            facilities = self.db.facility_manager.list_facilities()
            teams = self.db.team_manager.list_teams(league_id=league_id)
            
            # Calculate total court-hours needed
            total_matches = len(teams) * league.num_matches // 2  # Each match involves 2 teams
            total_court_hours = total_matches * league.num_lines_per_match * (league.get_match_duration_estimate() / 60)
            
            # Calculate available court-hours at facilities
            available_court_hours = 0
            facility_analysis = []
            
            for facility in facilities:
                facility_hours = self._calculate_facility_weekly_hours(facility, league)
                weeks_available = league.get_season_duration_weeks() or 16  # Default to 16 weeks
                facility_total_hours = facility_hours * weeks_available
                available_court_hours += facility_total_hours
                
                facility_analysis.append({
                    'facility_id': facility.id,
                    'facility_name': facility.name,
                    'weekly_court_hours': facility_hours,
                    'total_season_hours': facility_total_hours
                })
            
            utilization_percentage = (total_court_hours / available_court_hours * 100) if available_court_hours > 0 else float('inf')
            
            return {
                'feasible': utilization_percentage < 80,  # Consider feasible if under 80% utilization
                'total_court_hours_needed': round(total_court_hours, 1),
                'total_court_hours_available': round(available_court_hours, 1),
                'utilization_percentage': round(utilization_percentage, 1),
                'total_matches': total_matches,
                'courts_per_match': league.num_lines_per_match,
                'facility_breakdown': facility_analysis,
                'recommendations': self._get_feasibility_recommendations(utilization_percentage, league)
            }
            
        except Exception as e:
            raise RuntimeError(f"Error validating league scheduling feasibility: {e}")

    def _calculate_facility_weekly_hours(self, facility, league) -> float:
        """Calculate total court-hours available per week at a facility for a specific league"""
        total_hours = 0
        
        for day_name, day_schedule in facility.schedule.get_all_days().items():
            # Only count days that work for this league
            if not league.can_schedule_on_day(day_name):
                continue
            
            for time_slot in day_schedule.start_times:
                # Each time slot contributes: courts * hours_per_slot
                # Assuming each time slot represents a 2-hour block
                hours_per_slot = 2.0
                total_hours += time_slot.available_courts * hours_per_slot
        
        return total_hours

    def _get_feasibility_recommendations(self, utilization_percentage: float, league) -> List[str]:
        """Get recommendations based on utilization analysis"""
        recommendations = []
        
        if utilization_percentage > 100:
            recommendations.append("CRITICAL: Not enough court availability. Consider reducing matches or adding facilities.")
        elif utilization_percentage > 80:
            recommendations.append("WARNING: High utilization. Scheduling may be difficult.")
            recommendations.append("Consider allowing split-line scheduling if not already enabled.")
        elif utilization_percentage > 60:
            recommendations.append("Moderate utilization. Should be schedulable with some flexibility.")
        else:
            recommendations.append("Good availability. Scheduling should be straightforward.")
        
        if not league.allow_split_lines and utilization_percentage > 50:
            recommendations.append("Consider enabling split-line scheduling for more flexibility.")
        
        if len(league.preferred_days) < 2:
            recommendations.append("Consider adding more preferred scheduling days for flexibility.")
        
        return recommendations

    def get_scheduling_conflicts_summary(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get a summary of all scheduling conflicts in the system"""
        try:
            conflicts = {
                'team_date_conflicts': [],
                'facility_overbookings': [],
                'total_conflicts': 0
            }
            
            # Get all scheduled matches
            matches = self.db.match_line_manager.list_matches(league_id=league_id, include_unscheduled=False)
            
            # Check for team date conflicts
            date_team_matches = {}
            for match in matches:
                if match.date:
                    key = f"{match.date}_{match.home_team_id}"
                    if key not in date_team_matches:
                        date_team_matches[key] = []
                    date_team_matches[key].append(match)
                    
                    key = f"{match.date}_{match.visitor_team_id}"
                    if key not in date_team_matches:
                        date_team_matches[key] = []
                    date_team_matches[key].append(match)
            
            for key, match_list in date_team_matches.items():
                if len(match_list) > 1:
                    date, team_id = key.split('_')
                    conflicts['team_date_conflicts'].append({
                        'date': date,
                        'team_id': int(team_id),
                        'conflicting_matches': [m.id for m in match_list]
                    })
            
            # Check for facility overbookings
            facility_bookings = {}
            for match in matches:
                if match.facility_id and match.date and match.time:
                    key = f"{match.facility_id}_{match.date}_{match.time}"
                    if key not in facility_bookings:
                        facility_bookings[key] = []
                    facility_bookings[key].append(match)
            
            for key, match_list in facility_bookings.items():
                facility_id, date, time = key.split('_')
                facility_id = int(facility_id)
                
                # Count total lines needed
                total_lines_needed = 0
                for match in match_list:
                    match_with_lines = self.db.match_line_manager.get_match_with_lines(match.id)
                    total_lines_needed += len(match_with_lines.lines)
                
                # Check available courts
                available_courts = self.db.facility_manager.get_available_courts_count(
                    facility_id, date, time
                )
                
                if total_lines_needed > available_courts:
                    conflicts['facility_overbookings'].append({
                        'facility_id': facility_id,
                        'date': date,
                        'time': time,
                        'courts_needed': total_lines_needed,
                        'courts_available': available_courts,
                        'conflicting_matches': [m.id for m in match_list]
                    })
            
            conflicts['total_conflicts'] = len(conflicts['team_date_conflicts']) + len(conflicts['facility_overbookings'])
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Error getting scheduling conflicts summary: {e}")

    def get_scheduling_statistics(self, league_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive scheduling statistics"""
        try:
            stats = {}
            
            # Get basic match statistics
            if league_id:
                stats.update(self.db.league_manager.get_league_scheduling_status(league_id))
            else:
                # Get system-wide statistics
                match_stats = self.db.match_line_manager.get_match_count_by_status()
                line_stats = self.db.match_line_manager.get_lines_count_by_status()
                stats.update(match_stats)
                stats.update(line_stats)
            
            # Get facility utilization
            facilities = self.db.facility_manager.list_facilities()
            facility_utilization = []
            
            for facility in facilities:
                # Calculate utilization for the next 30 days
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                
                utilization = self.db.facility_manager.get_facility_utilization(
                    facility.id, start_date, end_date
                )
                facility_utilization.append({
                    'facility_id': facility.id,
                    'facility_name': facility.name,
                    **utilization
                })
            
            stats['facility_utilization'] = facility_utilization
            
            # Get conflicts summary
            stats['conflicts'] = self.get_scheduling_conflicts_summary(league_id)
            
            return stats
            
        except Exception as e:
            raise RuntimeError(f"Error getting scheduling statistics: {e}")

    def reschedule_match(self, match_id: int, new_facility_id: int, 
                        new_date: str, new_time: str) -> bool:
        """
        Reschedule an existing match to a new facility, date, and time
        
        Args:
            match_id: Match to reschedule
            new_facility_id: New facility ID
            new_date: New date in YYYY-MM-DD format
            new_time: New time in HH:MM format
            
        Returns:
            True if successfully rescheduled, False otherwise
        """
        try:
            # First unschedule the match
            self.unschedule_match(match_id)
            
            # Then schedule it at the new time/place
            return self.schedule_match_all_lines_same_time(
                match_id, new_facility_id, new_date, new_time
            )
            
        except Exception as e:
            raise RuntimeError(f"Error rescheduling match {match_id}: {e}")

    def find_next_available_slot(self, facility_id: int, preferred_date: str, 
                                courts_needed: int = 1, 
                                search_days_ahead: int = 30) -> Optional[Dict[str, str]]:
        """
        Find the next available time slot at a facility
        
        Args:
            facility_id: Facility to search
            preferred_date: Starting date for search
            courts_needed: Number of courts needed
            search_days_ahead: How many days ahead to search
            
        Returns:
            Dict with 'date' and 'time' if found, None otherwise
        """
        try:
            facility = self.db.facility_manager.get_facility(facility_id)
            if not facility:
                raise ValueError(f"Facility with ID {facility_id} does not exist")
            
            start_date = datetime.strptime(preferred_date, '%Y-%m-%d')
            
            for days_offset in range(search_days_ahead):
                check_date = start_date + timedelta(days=days_offset)
                date_str = check_date.strftime('%Y-%m-%d')
                day_name = check_date.strftime('%A')
                
                if not facility.is_available_on_date(date_str):
                    continue
                
                day_schedule = facility.schedule.get_day_schedule(day_name)
                
                for time_slot in day_schedule.start_times:
                    if self.db.facility_manager.check_court_availability(
                        facility_id, date_str, time_slot.time, courts_needed
                    ):
                        return {
                            'date': date_str,
                            'time': time_slot.time
                        }
            
            return None
            
        except Exception as e:
            raise RuntimeError(f"Error finding next available slot: {e}")
