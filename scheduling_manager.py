"""
Scheduling Management for Tennis Database

Handles all scheduling-related operations including match scheduling,
team conflict checking, auto-scheduling, and scheduling analytics.

This is a generic implementation that uses TennisDBInterface for database access,
making it backend-agnostic and easily testable.
"""

from typing import List, Optional, Dict, Any
from datetime import date

from usta import Match, League, Facility
from usta_match import MatchScheduling
from scheduling_options import SchedulingOptions, DateOption, FacilityOption, TimeSlotInfo
from tennis_db_interface import TennisDBInterface


class SchedulingManager:
    """Generic scheduling manager that uses TennisDBInterface for database operations"""
    
    def __init__(self, db: TennisDBInterface):
        """
        Initialize SchedulingManager
        
        Args:
            db: TennisDBInterface implementation for database operations
        """
        self.db = db

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
            if not dates:
                raise ValueError("No valid dates found for match scheduling")

            # Filter out dates where either team has conflicts
            if not ignore_conflicts:
                dates = self.filter_team_conflicts(match, dates)
                if not dates:
                    # If no valid dates after filtering, return empty SchedulingOptions
                    return SchedulingOptions(match=match)

            # extract the facilities from the match scheduling options
            facilities = [option.facility for option in prioritized_match_scheduling if option.facility]

            # get facilities availability for the range of dates
            if not facilities:
                raise ValueError("No facilities available for match scheduling")

            # Get availability information for each facility
            # This will return a dictionary of facility ID to availability info
            filter_availability_info = {}
            for facility in facilities:
                availability = self.db.get_facility_availability(
                    facility=facility,
                    dates=dates
                )
                filter_availability_info[facility.id] = availability

            filtered_availability = []

            for option in prioritized_match_scheduling:
                # get the list for this facility
                facility_availability_list = filter_availability_info.get(option.facility.id, [])

                # get the facility_info for this date
                facility_info = next((info for info in facility_availability_list if info.date == option.date), None)

                if not facility_info:
                    # If no availability info for this date, skip this option
                    continue

                can_accommodate, _ = facility_info.can_accommodate_match(match) 
                if not can_accommodate:
                    continue  # Skip this facility if it can't accommodate the match

                # If it can accommodate, add the option to the filtered list
                option.scheduled_times = facility_info.get_available_times(match.league.num_lines_per_match)
                filtered_availability.append(option)

            # Create and return SchedulingOptions by building DateOptions from the filtered availability
            scheduling_options = SchedulingOptions(match=match)
            
            # Group filtered options by date to create DateOption objects
            from collections import defaultdict
            date_groups = defaultdict(list)
            
            for option in filtered_availability:
                date_groups[option.date].append(option)
            
            # Create DateOption objects for each date with multiple facilities
            for date_obj, options_for_date in date_groups.items():
                day_of_week = date_obj.strftime("%A")
                
                # Create FacilityOption objects for each facility on this date
                facility_options = []
                for option in options_for_date:
                    # Get facility availability info for quality scoring and time slots
                    facility_availability_list = filter_availability_info.get(option.facility.id, [])
                    facility_info = next((info for info in facility_availability_list if info.date == option.date), None)
                    
                    if facility_info:
                        # Convert time slots
                        time_slots = []
                        for slot in facility_info.time_slots:
                            time_slot = TimeSlotInfo(
                                time=slot.time,
                                total_courts=slot.total_courts,
                                available_courts=slot.available_courts,
                                used_courts=slot.used_courts
                            )
                            time_slots.append(time_slot)
                        
                        # Calculate quality score for this facility on this date
                        quality_score, conflicts = match.calculate_quality_score(option.date) if match else (0, [])
                        
                        facility_option = FacilityOption(
                            facility_id=option.facility.id,
                            facility_name=option.facility.name,
                            time_slots=time_slots,
                            quality_score=quality_score,
                            conflicts=conflicts if isinstance(conflicts, list) else [],
                            facility=option.facility
                        )
                        facility_options.append(facility_option)
                
                # Create DateOption with all facility options for this date
                if facility_options:
                    date_option = DateOption(
                        date=date_obj,
                        day_of_week=day_of_week,
                        facility_options=facility_options
                    )
                    scheduling_options.add_date_option(date_option)
            
            return scheduling_options

        except Exception as e:
            raise RuntimeError(f"Error getting scheduling options: {e}")
        

    def filter_team_conflicts(self, match: Match, dates: List[date]) -> List[date]:
        """
        Filter out dates where either team is already scheduled
        
        Args:
            match: Match object to check conflicts for
            dates: List of candidate date objects
            
        Returns:
            List of date objects with no team conflicts (subset of input dates)
        """
        if not isinstance(match, Match):
            raise TypeError(f"Expected Match object, got: {type(match)}")
        
        if not isinstance(dates, list):
            raise TypeError(f"Expected list of dates, got: {type(dates)}")
        
        if not dates:
            return []
        
        filtered_dates = []
        for date_obj in dates:
            # Check for team conflicts on this date
            home_conflict = self.db.check_team_date_conflict(match.home_team, date_obj)
            visitor_conflict = self.db.check_team_date_conflict(match.visitor_team, date_obj)
            
            # If no conflicts, add to filtered list
            if not home_conflict and not visitor_conflict:
                filtered_dates.append(date_obj)
                
        return filtered_dates

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
                facility_availability = self.db.get_facility_availability(
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

    def is_schedulable(self, match: Match, date_obj: date, 
                       facility: Optional['Facility'] = None,
                       allow_split_lines: Optional[bool]=False) -> bool:
        """
        Check if a match can be scheduled on a specific date
        
        This is a simple boolean function that uses the same logic as auto_schedule_match
        to determine if scheduling is possible.
        
        Args:
            match: Match object to check
            date_obj: Date object to check
            facility: Optional facility to check. If None, uses home team's facility or tries all facilities
            allow_split_lines: Whether to allow split line scheduling
            
        Returns:
            True if the match can be scheduled on this date, False otherwise
            
        Examples:
            # Check if match can be scheduled at home facility
            from datetime import date
            can_schedule = scheduling_manager.is_schedulable(match, date(2025, 6, 25))
            
            # Check if match can be scheduled at specific facility
            facility = db.get_facility(5)
            can_schedule = scheduling_manager.is_schedulable(match, date(2025, 6, 25), facility)
        """
        try:
            print(f"\n\n IS_SCHEDULABLE: Checking {date_obj}\n\n")
            
            if not isinstance(match, Match):
                return False
            
            if not isinstance(date_obj, date):
                raise TypeError(f"Expected date object, got: {type(date_obj)}")
            
            # STEP 1: Check team conflicts first (blocking check)
            # Use same logic as auto_schedule_match and filter_dates_by_availability

            try:
                # Check home team conflicts
                if self.db.check_team_date_conflict(team=match.home_team, 
                                                    date_obj=date_obj):
                    return False
                
                # Check visitor team conflicts  
                if self.db.check_team_date_conflict(team=match.visitor_team, 
                                                    date_obj=date_obj):
                    return False
            except Exception as date_error:
                print(f"\n\n ==== Team Conflict error: {date_error}\n\n")
                raise date_error
            
            # STEP 2: Check facility availability           
            if not facility:
                facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None
            
            
            # Check each facility until we find one that works

            try:
            
                # Check if facility is available on this date
                if facility.is_available_on_date(date_obj):
                
                    # Check to see if this facility can accommodate the number of lines
                    # Use the database interface to check availability
                    facility_availability = self.db.get_facility_availability(
                        facility=facility, dates=[date_obj], max_days=1
                    )
                    
                    if facility_availability and facility_availability[0].available:
                        can_accommodate, _ = facility_availability[0].can_accommodate_match(match)
                        
                        print(f"\n\n === {can_accommodate}: Checked to see if facility {facility.short_name} "
                              f"can accommodate match {match.id}, allow_split_lines={allow_split_lines}")
        
                        if can_accommodate:
                            return True
                
                return False
                
            except Exception as accom_err:
                # Any unexpected error means we can't schedule
                print(f"\n\n ==== Error calling can_accommodate: {accom_err}")
                raise accom_err
            
            
        except Exception as e:
            # Any unexpected error means we can't schedule
            print(f"Error in is_schedulable: {e}")
            raise e

    def schedule_match(self, match: Match) -> bool:
        """
        Schedule a match using the database interface
        """
        try:
            # make sure the match is ready to be scheduled
            if not match.is_scheduled():
                raise ValueError("Match is not ready to be scheduled. Check match details and scheduling options.")
            
            # Update the match scheduling in the database
            print(f"Scheduling match {match.id} for teams {match.home_team_name} vs {match.visitor_team_name} "
                  f"on {match.date} at {match.facility_name} with times {match.get_scheduled_times()}")
            
            return self.db.update_match(match)

        except Exception as e:
            raise RuntimeError(f"Error scheduling match {match.id}: {e}")


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

            # Begin transaction if database supports it
            if hasattr(self.db, 'begin_transaction'):
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

                    # Get scheduling options for the match.  
                    scheduling_options = self.get_scheduling_options(
                        match,
                        ignore_conflicts=False,  # Do not ignore conflicts for auto-scheduling
                        ignore_league_preferences=False,
                        ignore_team_preferences=False,
                    )

                    # For the auto-scheduling, we use the highest first option which should
                    # be the most preferred date based on team and league preferences
                    if not scheduling_options.date_options:
                        results["failed"] += 1
                        results["errors"].append(
                            {
                                "match_id": match.id,
                                "status": "no_scheduling_options",
                                "home_team": match.home_team_name,
                                "visitor_team": match.visitor_team_name,
                                "reason": "No scheduling options available",
                            }
                        )
                        continue

                    # The scheduling options should already be sorted by priority
                    # and we can use the first option as the preferred date
                    match_scheduling = scheduling_options.get_best_match_scheduling("same_time")

                    if not match_scheduling and match.league.allow_split_lines:
                        match_scheduling = scheduling_options.get_best_match_scheduling("split_times")

                    if not match_scheduling:
                        results["failed"] += 1
                        results["errors"].append(
                            {
                                "match_id": match.id,
                                "status": "no_available_scheduling",
                                "home_team": match.home_team_name,
                                "visitor_team": match.visitor_team_name,
                                "reason": "No available scheduling options found",
                            }
                        )
                        continue

                    # assign the match scheduling to the match
                    match.assign_scheduling(match_scheduling)

                    # Schedule the match using the database interface
                    success = self.schedule_match(match)


                    if success:
                        results["scheduled"] += 1
                        # Calculate quality score for scheduled match
                        quality_score, _ = match.calculate_quality_score()
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

                # Commit transaction if database supports it
                if hasattr(self.db, 'commit_transaction'):
                    self.db.commit_transaction()
                return results

            except Exception as e:
                if hasattr(self.db, 'rollback_transaction'):
                    self.db.rollback_transaction()
                results["errors"].append(
                    {"type": "transaction_error", "message": str(e)}
                )
                raise e

        except Exception as e:
            # Only rollback if we still have an active transaction 
            # (the inner try block may have already handled rollback)
            if hasattr(self.db, 'rollback_transaction') and getattr(self.db, 'transaction_active', False):
                self.db.rollback_transaction()
            raise RuntimeError(f"Error in auto_schedule_matches: {e}")

    def unschedule_match(self, match: Match) -> bool:
        """Unschedule a match using the database interface"""
        try:
            if match.is_scheduled():
                match.unschedule()  # Clear match scheduling details
                # Log the unscheduling action
                print(f"Unscheduling match {match.id} for teams {match.home_team_name} vs {match.visitor_team_name}")

            # update the database to remove the match scheduling
            return self.db.update_match(match)
        
        except Exception as e:
            raise RuntimeError(f"Error unscheduling match: {e}")

    def preview_match_scheduling(
        self, match: Match, date: date, times: List[str], scheduling_mode: str, facility: Optional['Facility'] = None
    ) -> Dict[str, Any]:
        """
        Preview what would happen if scheduling a match without actually doing it.

        Args:
            match: Match object to preview scheduling for
            date: Date object to schedule the match
            times: List of proposed times for the match
            scheduling_mode: Scheduling mode ('same_time', 'split_times', 'custom', etc.)
            facility: Optional facility to use for the preview (if None, uses match facility or home team facility)

        Returns:
            Dictionary with detailed information about conflicts, availability, and proposed schedule
        """
        try:
            lines_needed = match.league.num_lines_per_match if match.league else 3

            # Validate input parameters
            if not isinstance(match, Match):
                raise TypeError(f"Expected Match object, got: {type(match)}")
            if not isinstance(date, date):
                raise TypeError(f"Expected date object, got: {type(date)}")
            if not isinstance(times, list):
                raise TypeError(f"Expected times as list, got: {type(times)}")
            if scheduling_mode not in ["same_time", "split_times", "custom", "auto"]:
                raise ValueError(f"Invalid scheduling mode: {scheduling_mode}")
            if not times:
                raise ValueError("Times list cannot be empty for scheduling preview")

            # Check for team conflicts on the given date
            valid_dates = self.filter_team_conflicts(match, [date])
            if not valid_dates:
                return {
                    "schedulable": False,
                    "conflicts": [
                        {
                            "type": "team_conflict",
                            "message": "Team conflict detected on the given date",
                        }
                    ],
                    "proposed_times": [],
                    "mode": scheduling_mode,
                    "lines_needed": lines_needed,
                }
            date_obj = valid_dates[0]  # Use the first valid date

            # Get facility (use provided facility, or prefer match facility, fall back to home team facility)
            if not facility:
                facility = match.get_facility()
                if not facility and match.home_team:
                    facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None

            if not facility:
                return {
                    "schedulable": False,
                    "conflicts": [
                        {
                            "type": "no_facility",
                            "message": "No facility assigned to match",
                        }
                    ],
                    "proposed_times": [],
                    "mode": scheduling_mode,
                    "lines_needed": lines_needed,
                }

            # Initialize preview result
            preview_result = {
                "schedulable": False,
                "conflicts": [],
                "proposed_times": times,
                "mode": scheduling_mode,
                "lines_needed": lines_needed,
                "date": date,
                "facility_name": facility.name,
                "scheduling_mode": scheduling_mode,
                "scheduling_details": f"Attempting to schedule {lines_needed} lines using {scheduling_mode} mode",
                "success": False,
                "warnings": [],
                "operations": [],
            }

            # Get facility availability
            availability_list = self.db.get_facility_availability(
                facility=facility, dates=[date], max_days=1
            )
            
            # If no availability or facility is not available, return conflict
            if not availability_list or not availability_list[0].available:
                preview_result["conflicts"].append(
                    {
                        "type": "facility_unavailable",
                        "message": f"Facility {facility.name} not available on {date}",
                    }
                )
                return preview_result

            facility_info = availability_list[0]

            # Validate scheduling times based on mode
            proposed_times = []

            # For 'same_time' mode, we need each time slot to accommodate all lines
            if scheduling_mode == "same_time":
                valid_times = facility_info.get_available_times(lines_needed)
                if not valid_times:
                    preview_result["conflicts"].append(
                        {
                            "type": "no_available_times",
                            "message": f"No available times for mode '{scheduling_mode}' with {lines_needed} lines",
                        }
                    )
                    return preview_result
                proposed_times = valid_times

            elif scheduling_mode == "split_times":
                # For 'split_times', we need two time slots that can accommodate half the lines each
                import math
                courts_per_slot = math.ceil(lines_needed / 2)
                valid_times = facility_info.get_available_times(courts_per_slot)
                if len(valid_times) < 2:
                    preview_result["conflicts"].append(
                        {
                            "type": "no_available_times",
                            "message": f"Not enough available times for mode '{scheduling_mode}' with {lines_needed} lines",
                        }
                    )
                    return preview_result
                proposed_times = valid_times[:2]

            elif scheduling_mode == "custom":
                # For custom mode, validate that the proposed times are available
                for time in times:
                    time_slots = [slot for slot in facility_info.time_slots if slot.time == time]
                    if not time_slots or not time_slots[0].has_availability():
                        preview_result["conflicts"].append(
                            {
                                "type": "time_unavailable",
                                "message": f"Time {time} is not available",
                            }
                        )
                        return preview_result
                proposed_times = times

            elif scheduling_mode == "auto":
                # For auto mode, use the best available times
                valid_times = facility_info.get_available_times(lines_needed)
                if not valid_times:
                    preview_result["conflicts"].append(
                        {
                            "type": "no_available_times",
                            "message": f"No available times for auto scheduling with {lines_needed} lines",
                        }
                    )
                    return preview_result
                proposed_times = valid_times[:1]  # Use the first available time

            # If we reach here, we have valid proposed times
            preview_result["schedulable"] = True
            preview_result["proposed_times"] = proposed_times
            preview_result["success"] = True
            preview_result["scheduling_details"] = (
                f"Successfully found {len(proposed_times)} available time slots for {lines_needed} lines using {scheduling_mode} mode"
            )
            preview_result["operations"] = [
                {
                    "type": "update_match",
                    "description": f"Update match {match.id} with {scheduling_mode} scheduling",
                },
                {
                    "type": "set_facility",
                    "description": f"Set facility to {facility.name}",
                },
                {"type": "set_date", "description": f"Set date to {date}"},
                {
                    "type": "set_times",
                    "description": f'Set times to {", ".join(times)}',
                },
            ]

            return preview_result

        except Exception as e:
            return {
                "schedulable": False,
                "conflicts": [{"type": "exception", "message": str(e)}],
                "proposed_times": [],
                "mode": scheduling_mode,
            }

    def get_scheduling_summary(self, league: Optional[League] = None) -> Dict[str, Any]:
        """
        Get scheduling summary statistics using the database interface
        
        Args:
            league: Optional league to filter by
            
        Returns:
            Dictionary with scheduling statistics
        """
        try:
            return self.db.get_scheduling_summary(league)
        except Exception as e:
            raise RuntimeError(f"Error getting scheduling summary: {e}")



    def optimize_auto_schedule(self, matches: List['Match'], max_iterations: int = 10, 
                                progress_callback=None) -> Dict[str, Any]:
            """
            Run auto-schedule optimization with multiple iterations to find best scheduling
            
            Args:
                matches: List of matches to schedule
                max_iterations: Maximum number of iterations to run
                progress_callback: Optional callback function for progress updates
                
            Returns:
                Dictionary with optimization results including best seed and quality metrics
            """
            try:
                import random
                import time
                
                best_result = None
                best_seed = None
                best_unscheduled_count = float('inf')
                best_quality_score = 0
                
                results_history = []

                for iteration in range(max_iterations):

                    # count the number of unscheduled matches
                    unscheduled_count = len([m for m in matches if not m.is_scheduled()])

                    # Generate random seed for this iteration
                    seed = random.randint(1, 1000000)
                    
                    start_time = time.time()
                    
                    # Run auto-schedule in dry-run mode with this seed
                    result = self.auto_schedule_matches(matches, dry_run=True, seed=seed)
                    
                    iteration_time = time.time() - start_time
                    
                    # Calculate metrics
                    unscheduled_count = result['failed']
                    total_quality_score = sum(
                        detail.get('quality_score', 0) 
                        for detail in result.get('scheduling_details', [])
                    )
                    avg_quality_score = (
                        total_quality_score / result['scheduled'] 
                        if result['scheduled'] > 0 else 0
                    )
                    
                    iteration_result = {
                        'iteration': iteration + 1,
                        'seed': seed,
                        'unscheduled_count': unscheduled_count,
                        'scheduled_count': result['scheduled'],
                        'total_quality_score': total_quality_score,
                        'avg_quality_score': avg_quality_score,
                        'execution_time': iteration_time
                    }
                    
                    results_history.append(iteration_result)
                    
                    # Determine if this is the best result so far
                    is_better = False
                    
                    if unscheduled_count < best_unscheduled_count:
                        # Fewer unscheduled matches is always better
                        is_better = True
                    elif unscheduled_count == best_unscheduled_count and avg_quality_score > best_quality_score:
                        # Same unscheduled count, but better quality
                        is_better = True
                    
                    if is_better:
                        best_result = result
                        best_seed = seed
                        best_unscheduled_count = unscheduled_count
                        best_quality_score = avg_quality_score
                    
                    # Call progress callback if provided
                    if progress_callback:
                        progress_callback({
                            'iteration': iteration + 1,
                            'max_iterations': max_iterations,
                            'current_result': iteration_result,
                            'best_seed': best_seed,
                            'best_unscheduled_count': best_unscheduled_count,
                            'best_quality_score': best_quality_score
                        })

                    # unschedule each scheduled match to reset for next iteration
                    for match in matches:
                        if match.is_scheduled():
                            match.unschedule()
                
                # Return comprehensive results
                optimization_result = {
                    'optimization_completed': True,
                    'max_iterations': max_iterations,
                    'best_seed': best_seed,
                    'best_result': best_result,
                    'best_unscheduled_count': best_unscheduled_count,
                    'best_quality_score': best_quality_score,
                    'results_history': results_history,
                    'improvement_found': best_seed is not None
                }
                
                return optimization_result
                
            except Exception as e:
                return {
                    'optimization_completed': False,
                    'error': str(e),
                    'results_history': results_history if 'results_history' in locals() else []
                }

