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
from usta_match import MatchScheduling
from scheduling_options import SchedulingOptions
import math


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


    def get_scheduling_options(self, match: Match,
                                    max_dates: int = 365,
                                    ignore_conflicts: bool = False, 
                                    ignore_league_preferences: bool = False,
                                    ignore_team_preferences: bool = False) -> 'SchedulingOptions':
        """
        Get comprehensive scheduling options for a match using the new SchedulingOptions class.
        This method retrieves viable scheduling dates based on team and league preferences,
        facility availability, and team conflicts.

        Args:
            match: Match object
            max_dates: Maximum number of dates to consider
            ignore_conflicts: If True, ignore team date conflicts
            ignore_league_preferences: If True, ignore league preferred days
            ignore_team_preferences: If True, ignore team preferred days

        Returns:
            SchedulingOptions: A comprehensive scheduling options object with enhanced functionality.
        """

        try:
            if ignore_league_preferences or ignore_team_preferences:
                # Filtering league and team preferences are not implemented yet, raise NotImplementedError
                raise NotImplementedError("Filtering league and team preferences is not implemented")

            # Get preferred scheduling options (dates, facility, priority) based on team and league preferences
            prioritized_match_scheduling = match.get_prioritized_scheduling_options()
            if not prioritized_match_scheduling:
                # Return empty SchedulingOptions if no dates found
                return SchedulingOptions(match=match)

            # Extract dates from the MatchScheduling objects
            dates = [option.date for option in prioritized_match_scheduling]
            
            # Get the facility (prefer match facility, fall back to home team facility)
            facility = match.get_facility()
            if not facility and match.home_team:
                facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None
            
            if not facility:
                raise ValueError("No facility available for match")

            # Get detailed facility availability information
            facility_availability_list = self.db.facility_manager.get_facility_availability(
                facility=facility, 
                dates=dates, 
                max_days=max_dates
            )

            # Filter out unavailable dates and dates with conflicts
            filtered_availability = []
            for facility_info in facility_availability_list:
                if not facility_info.available:
                    continue
                
                # Check if facility can accommodate the match
                can_accommodate, reason = facility_info.can_accommodate_match(match)
                if not can_accommodate:
                    continue
                    
                # Check for team conflicts if not ignoring them
                if not ignore_conflicts:
                    if (self.db.check_team_date_conflict(match.home_team, facility_info.date) or 
                        self.db.check_team_date_conflict(match.visitor_team, facility_info.date)):
                        continue
                
                filtered_availability.append(facility_info)

            # Create and return SchedulingOptions using the factory method
            scheduling_options = SchedulingOptions.from_facility_availability_list(
                match=match,
                facility_availability_list=filtered_availability,
                facility=facility
            )

            return scheduling_options

        except Exception as e:
            raise RuntimeError(f"Error getting scheduling options: {e}")
        

    def _filter_team_conflicts(self, match: Match, scheduling_options: List[MatchScheduling]) -> List[MatchScheduling]:
        """
        Filter out dates that have team conflicts.
        """
        filtered_options = []
        for option in scheduling_options:
            if not self.db.team_manager.check_team_date_conflict(match.home_team, option.date) and \
               not self.db.team_manager.check_team_date_conflict(match.visitor_team, option.date):
                filtered_options.append(option)
        return filtered_options

    def _filter_facility_availability(self, match: Match, scheduling_options: List[MatchScheduling]) -> List[MatchScheduling]:
        """
        Filter out options that do not have facility availability.
        """

        try: 
            # Check if options list is empty
            if not scheduling_options:
                return []
            
            # Get the dates from the scheduling options
            dates = [option.date for option in scheduling_options]

            # Get our facilities from the home team
            facilities = [match.home_team.get_primary_facility()] if match.home_team.preferred_facilities else []

            filtered_options = []

            for facility in facilities:

                # get facility availability for the range of dates -- it will filter out dates that are not available
                facility_availability = self.db.facility_manager.get_facility_availability(
                    facility=facility, dates=dates, max_days=len(dates)
                )
                # If no availability info, skip this facility
                # This means the facility is not available for any of the dates
                if not facility_availability:
                    continue


                for availability_info in facility_availability:

                    # Check if the facility can accommodate the match on this date
                    success, desc = availability_info.can_accommodate_match(match)

                    if success:
                        # get the option that matches this date and facility
                        option = next((opt for opt in scheduling_options if opt.date == availability_info.date and opt.facility.id == facility.id), None)

                        # If we found an option that matches this date and facility
                        # and it can accommodate the match, add it to the filtered list
                        # This will be a MatchScheduling object
                        # with the date, facility, and scheduled_times set to empty
                        # since we are just filtering availability here
                        # If it can, add the option to the filtered list
                        if option:
                            filtered_options.append(option)
                    else:
                        # Log the reason for filtering out this date
                        print(f"Filtering out date {availability_info.date} for match {match.id}: {desc}")

            # Return the filtered options
            return filtered_options
        
        except Exception as e:
            raise RuntimeError(f"Error filtering facility availability: {e}")
    


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
                facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None
            
            
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
    
    

    def schedule_match(
        self, match: Match, date: str, times: List[str], mode: str = "auto"
    ) -> Dict[str, Any]:
        """
        Simplified scheduling that uses Match class methods directly
        """
        try:
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")

            # Check if match has a facility assigned
            if not match.facility:
                return {
                    "success": False,
                    "error": "No facility assigned to match",
                    "error_type": "no_facility",
                }

            # Get detailed facility availability information
            facility_availability = self.db.facility_manager.get_facility_availability(
                facility=match.facility, dates=[date], max_days=1
            )

            if not facility_availability or not facility_availability[0].available:
                reason = (
                    facility_availability[0].reason
                    if facility_availability
                    else "Unknown reason"
                )
                return {
                    "success": False,
                    "error": f"Facility {match.facility.name} not available on {date}: {reason}",
                    "error_type": "facility_unavailable",
                }

            facility_info = facility_availability[0]

            # Check for team conflicts
            if self.db.team_manager.check_team_date_conflict(
                match.home_team, date
            ) or self.db.team_manager.check_team_date_conflict(
                match.visitor_team, date
            ):
                return {
                    "success": False,
                    "error": f"Team conflict detected on {date}",
                    "error_type": "team_conflict",
                }

            # Auto-determine times if not provided. Since nothing was provided,
            # we will try to get available times based on the mode, then select
            # the appropriate times based on the mode.
            if not times:
                times = self._get_times_for_mode(match, facility_info, mode)
                if not times:
                    return {
                        "success": False,
                        "error": f"No available times for mode '{mode}'",
                        "error_type": "no_available_times",
                    }

            # Validate scheduling request using FacilityAvailabilityInfo
            lines_needed = match.league.num_lines_per_match if match.league else 3
            is_valid, validation_error = facility_info.validate_scheduling_request(
                times=times, scheduling_mode=mode, lines_needed=lines_needed
            )

            if not is_valid:
                return {
                    "success": False,
                    "error": f"Scheduling validation failed: {validation_error}",
                    "error_type": "validation_failed",
                }

            # Use Match class methods based on mode
            success = False

            if mode == "same_time":
                if len(times) >= 1:
                    success = match.schedule_all_lines_same_time(match.facility, date, times[0])

            elif mode == "split_times":
                if len(times) >= 2:
                    # Generate split times using Match logic
                    lines_needed = match.get_expected_lines()
                    courts_per_slot = math.ceil(lines_needed / 2)
                    lines_in_second_slot = lines_needed - courts_per_slot
                    split_times = [times[0]] * courts_per_slot + [
                        times[1]
                    ] * lines_in_second_slot
                    success = match.schedule_lines_split_times(match.facility, date, split_times)

            elif mode == "custom":
                success = match.schedule_lines_custom_times(match.facility, date, times)

            if success:
                # Update database
                self._update_match_in_db(match)

                # Update scheduling state for conflict detection in dry-run mode
                if hasattr(self.db, "scheduling_state") and self.db.scheduling_state:
                    scheduled_times = match.get_scheduled_times()
                    for time in scheduled_times:
                        self.db.scheduling_state.book_time_slot(
                            match.id, match.facility.id, date, time
                        )
                    self.db.scheduling_state.book_team_date(
                        match.id, match.home_team.id, date
                    )
                    self.db.scheduling_state.book_team_date(
                        match.id, match.visitor_team.id, date
                    )

                # Check to make sure facility availability 
                facility_availability = self.db.facility_manager.get_facility_availability(
                    facility=match.facility, dates=[date], max_days=1
                )

                facility_info_after = facility_availability[0] if facility_availability else None
                initial_slots = facility_info.available_court_slots if facility_info else None
                after_slots = facility_info_after.available_court_slots if facility_info_after else None
                expected_slots = initial_slots - match.get_num_scheduled_lines()
                
                if after_slots is not None and after_slots != expected_slots:
                    print(f"---WARNING---: Facility {match.facility.id} has {after_slots} courts available after scheduling, "
                          f"but {expected_slots} were expected after scheduling match {match.id}.")
                    raise ValueError(
                        f"Facility {match.facility.id} has {after_slots} courts available after scheduling, "
                        f"but {expected_slots} were expected after scheduling match {match.id}."
                    )
                

                return {
                    "success": True,
                    "scheduled_times": match.get_scheduled_times(),
                    "mode_used": mode,
                }
            else:
                return {
                    "success": False,
                    "error": f"Could not schedule using mode '{mode}'",
                    "error_type": "scheduling_failed",
                }

        except Exception as e:
            print(f"Error scheduling match {match.id}: {e}")
            return {"success": False, 
                    "error": str(e), 
                    "error_type": "exception"}

    def auto_schedule_match(self, match: Match, preferred_dates: List[str]) -> bool:
        """
        Simplified auto-scheduling that tries different scheduling modes
        """
        try:
            # Skip already scheduled matches
            if match.is_scheduled():
                return True

            # Try each date scheduling all lines at the same time
            for date in preferred_dates:
                result = self.schedule_match(match, date, [], "same_time")

                # if result['success'] set to result['mode_used'] else set to result['error']
                detail = result['mode_used'] if result['success'] else result['error']
                #print(f"SCHED, {match.id}, {match.home_team.id}, {match.visitor_team.id}, {date}, {result['success']}, {detail}")

                if result["success"]:
                    return True


            # Now try each date with split times
            if match.league.allow_split_lines:
                for date in preferred_dates:
                    result = self.schedule_match(match, date, [], "split_times")

                    # if result['success'] set to result['mode_used'] else set to result['error']
                    detail = result['mode_used'] if result['success'] else result['error']
                    #print(f"SCHED, {match.id}, {match.home_team.id}, {match.visitor_team.id}, {date}, {result['success']}, {detail}")

                    if result["success"]:
                        return True

            # If we got here, no scheduling was successful
            return False

        except Exception as e:
            raise RuntimeError(f"Error auto-scheduling match {match.id}: {e}")


    def auto_schedule_matches(
        self, matches: List[Match], dry_run: bool = True, seed: int = None
    ) -> Dict[str, Any]:
        """
        Auto-schedule multiple matches using Match class methods
        Args:
            matches: List of Match objects to schedule
            dry_run: If True, only simulate scheduling without committing changes
            seed: Optional random seed for reproducibility
        Returns:
            A dictionary with scheduling results
        """
        try:
            results = {
                "total_matches": len(matches),
                "scheduled": 0,
                "failed": 0,
                "scheduling_details": [],
                "errors": [],
                "dry_run": dry_run,
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

                if seed is not None:
                    random.seed(seed)

                # Shuffle matches to avoid bias in scheduling order
                shuffled_matches = unscheduled_matches.copy()
                random.shuffle(shuffled_matches)

                for match in shuffled_matches:
                    # Use Match class method to get optimal dates with priorities
                    prioritized_dates = match.get_prioritized_scheduling_dates()

                    # Extract just the dates from the prioritized list
                    optimal_dates = [date for date, priority in prioritized_dates]

                    # 
                    success = self.auto_schedule_match(match, optimal_dates)

                    if success:
                        results["scheduled"] += 1
                        # Calculate quality score for scheduled match
                        quality_score = match.get_quality_score()
                        results["scheduling_details"].append(
                            {
                                "match_id": match.id,
                                "status": (
                                    "would_be_scheduled" if dry_run else "scheduled"
                                ),
                                "home_team": match.home_team_name,
                                "visitor_team": match.visitor_team_name,
                                "facility": match.facility_name,
                                "date": match.date,
                                "times": match.get_scheduled_times(),
                                "quality_score": quality_score,
                            }
                        )
                    else:
                        results["failed"] += 1
                        results["errors"].append(
                            {
                                "match_id": match.id,
                                "status": "scheduling_failed",
                                "home_team": match.home_team_name,
                                "visitor_team": match.visitor_team_name,
                                "reason": "No available time slots found",
                            }
                        )

                # Commit transaction
                self.db.commit_transaction()
                return results

            except Exception as e:
                self.db.rollback_transaction()
                results["errors"].append(
                    {"type": "transaction_error", "message": str(e)}
                )
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



    
    




    


    