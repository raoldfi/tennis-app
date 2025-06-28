"""
Flask Route Handler for Manual Match Scheduling
Fixed version with proper routes, data handling, and error handling
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from typing import Optional
import traceback
import math

# Create blueprint for scheduling routes
schedule_bp = Blueprint('schedule', __name__)




@schedule_bp.route('/matches/<int:match_id>/schedule')
def schedule_match_form(match_id: int):
    """
    Display the manual scheduling form for a specific match
    Fixed to properly format data for template cards
    """
    from web_database import get_db
    from datetime import datetime
    
    try:
        # Get database interface
        db = get_db()
        if db is None:
            flash('No database connection available', 'danger')
            return redirect(url_for('matches'))
        
        # Get match object
        match = db.get_match(match_id)
        if not match:
            flash(f'Match with ID {match_id} not found', 'danger')
            return redirect(url_for('matches'))

        league = match.league
        
        # Check if match is already scheduled
        if match.is_scheduled():
            flash(f'Match is already scheduled for {match.date} at {match.facility.name}', 'info')
            return redirect(url_for('view_match', match_id=match_id))
        
        # Get facility
        facility_id = request.args.get('facility_id', type=int)
        facility = None
        
        if facility_id:
            facility = db.get_facility(facility_id)
            if not facility:
                flash(f'Facility with ID {facility_id} not found', 'warning')
        
        if not facility and match.home_team:
            facility = match.home_team.home_facility

        print(f"\n\n\n============ Schedule Match Form =============\n\n\n")
        
        if not facility:
            flash('No facility available for this match. Please assign a home facility to the home team or specify a facility.', 'danger')
            return redirect(url_for('matches'))
        
        # Get scheduling options
        try:

            # This will return dates based on match and league preferences and priorities
            # optimal_dates = utils.get_optimal_scheduling_dates(
            #     match,
            #     num_dates=int(request.args.get('max_dates', 20))
            # )
            prioritized_dates = match.get_prioritized_scheduling_dates(
                num_dates= int(request.args.get('max_dates', 20)))
            

            # Filter these dates based on facility availability
            available_dates = []
            for current_date_str in prioritized_dates:
                try:
                    allow_split_lines = league.allow_split_lines
                    print(f"\n\n\n============ Checking is_schedulable({current_date_str}) =============\n\n\n")

                    schedulable = False
                    try:
                        schedulable = db.is_schedulable(match=match, 
                                                        date=current_date_str, 
                                                        facility=facility,
                                                        allow_split_lines=allow_split_lines)
                    except Exception as sched_error:
                        print(f"\n\n==== SCHED ERROR {sched_error}")
                        raise sched_error
                    
                    if schedulable:
                        
                        print(f"\n\n\n============ Parsing {current_date_str} =============\n\n\n")

                        # Parse date for formatting
                        date_obj = datetime.strptime(current_date_str, '%Y-%m-%d')
                        day_name = date_obj.strftime('%A')

                        print(f"\n\n\n============ Calculating score ({current_date_str}) =============\n\n\n")

                        # calculate a priority score
                        score = 10  # Base score
                        if day_name in match.league.preferred_days:
                            score += 5
                        elif day_name in match.league.backup_days:
                            score += 2

                                                
                        print(f"\n\n\n============ Score ({score}) =============\n\n\n")


                        courts_needed = match.league.num_lines_per_match
                        if allow_split_lines:
                            courts_needed = math.ceil(courts_needed/2)
                        
                        # Use tennis_db_interface to check availability
                        available_times = db.get_available_times_at_facility(
                            facility, 
                            current_date_str, 
                            courts_needed=courts_needed
                        )
                        
                        # Get detailed court availability for each time slot
                        # Get detailed court availability for each time slot
                        time_slot_details = []
                        for time in available_times:
                            # Get available courts for this specific time
                            available_courts = db.facility_manager.get_available_courts_at_time(
                                facility, current_date_str, time
                            )
                            
                            # Get total courts for this time slot
                            total_courts = db.facility_manager.get_total_courts_at_time(
                                facility, current_date_str, time
                            )
                            
                            time_slot_details.append({
                                'time': time,
                                'available_courts': available_courts,
                                'total_courts': total_courts
                            })
                        
                        date_option = {
                            'date': current_date_str,
                            'day_name': day_name,
                            'formatted_date': date_obj.strftime('%B %d, %Y'),
                            'available_times': available_times,
                            'time_slot_details': time_slot_details,  # NEW: detailed court info per time
                            'score': max(0, score),
                            'courts_available': getattr(facility, 'total_courts', getattr(facility, 'court_count', 3)),
                            'facility_name': facility.name
                        }

                        available_dates.append(date_option)
                
                except Exception as e:
                    print(f"Error processing date: {current_date_str}: {e}")
                    continue

            available_dates.sort(key=lambda x: x['score'], reverse=True)

            scheduling_options = {
                'success': True,
                'available_dates': available_dates,
                'search_params': {
                    'start_date': request.args.get('start_date'),
                    'end_date': request.args.get('end_date'),
                    'max_dates': request.args.get('max_dates', 20)
                }
            }
            
        
        except Exception as e:
            print(f"Error getting scheduling options: {e}")
            scheduling_options = {
                'success': False,
                'error': f'Error getting scheduling options: {str(e)}',
                'available_dates': []
            }
        
        # Transform match data for template
        match_info = {
            'id': match.id,
            'match_id': match.id,
            'home_team': match.home_team.name if match.home_team else 'TBD',
            'visitor_team': match.visitor_team.name if match.visitor_team else 'TBD',
            'league': match.league.name if match.league else 'Unknown',
            'lines_needed': match.league.num_lines_per_match if match.league else 3
        }
        
        # Transform facility data for template
        facility_info = {
            'id': facility.id,
            'name': facility.name,
            'location': getattr(facility, 'location', getattr(facility, 'address', None)),
            'total_courts': getattr(facility, 'total_courts', getattr(facility, 'court_count', 3))
        }
        
        # # CRITICAL FIX: Transform available dates to have all required properties
        # available_dates = []
        # if scheduling_options.get('success', False) and scheduling_options.get('available_dates'):
        #     for i, date_option in enumerate(scheduling_options['available_dates']):
        #         try:
        #             # Handle different possible date format inputs
        #             date_str = date_option.get('date', '')
        #             if not date_str:
        #                 continue
                    
        #             # Parse the date
        #             date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    
        #             # Extract or default all the properties the template expects
        #             enhanced_date = {
        #                 # Core date info
        #                 'date': date_str,
        #                 'day_name': date_option.get('day_name', 
        #                            date_option.get('day_of_week', 
        #                            date_obj.strftime('%A'))),
        #                 'formatted_date': date_option.get('formatted_date', 
        #                                  date_obj.strftime('%B %d, %Y')),
                        
        #                 # Time and availability info
        #                 'available_times': date_option.get('available_times', []),
                        
        #                 # Scoring and conflicts
        #                 'score': date_option.get('score', 
        #                         date_option.get('optimal_score', 
        #                         5 + i)),  # Default score with variety
        #                 'conflicts': date_option.get('conflicts', []),
                        
        #                 # Additional helpful info
        #                 'courts_available': facility_info['total_courts'],
        #                 'facility_name': facility_info['name'],
        #                 'is_weekend': date_obj.weekday() >= 5,
        #                 'short_date': date_obj.strftime('%m/%d')
        #             }
                    
        #             available_dates.append(enhanced_date)
                    
        #         except (ValueError, TypeError) as e:
        #             print(f"Error processing date option {date_option}: {e}")
        #             # Create a minimal valid date option
        #             try:
        #                 fallback_date = {
        #                     'date': date_option.get('date', ''),
        #                     'day_name': 'Unknown',
        #                     'formatted_date': 'Unknown Date',
        #                     'available_times': [],
        #                     'score': 1,
        #                     'conflicts': ['Error loading date'],
        #                     'courts_available': facility_info['total_courts'],
        #                     'facility_name': facility_info['name']
        #                 }
        #                 available_dates.append(fallback_date)
        #             except:
        #                 continue
        
        # # If no dates were successfully processed, create some sample dates for testing
        # if not available_dates and scheduling_options.get('success', False):
        #     print("No dates processed successfully, creating sample dates")
        #     from datetime import timedelta
        #     base_date = datetime.now().date()
            
        #     for i in range(5):
        #         sample_date = base_date + timedelta(days=i*7)  # Weekly intervals
        #         sample_date_str = sample_date.strftime('%Y-%m-%d')
        #         sample_date_obj = datetime.combine(sample_date, datetime.min.time())
                
        #         sample_option = {
        #             'date': sample_date_str,
        #             'day_name': sample_date_obj.strftime('%A'),
        #             'formatted_date': sample_date_obj.strftime('%B %d, %Y'),
        #             'available_times': ['09:00', '10:00', '14:00', '15:00'],
        #             'score': 5 - i,  # Decreasing scores
        #             'conflicts': [],
        #             'courts_available': facility_info['total_courts'],
        #             'facility_name': facility_info['name']
        #         }
        #         available_dates.append(sample_option)
        
        # print(f"Final available_dates count: {len(available_dates)}")
        # for date in available_dates[:2]:  # Print first 2 for debugging
        #     print(f"Date option: {date}")
        
        # Get all facilities for dropdown
        all_facilities = db.list_facilities()
        
        return render_template(
            'schedule_match.html',
            match_info=match_info,
            facility_info=facility_info,
            available_dates=available_dates,
            success=scheduling_options.get('success', False),
            error=scheduling_options.get('error', None),
            search_params=scheduling_options.get('search_params', {}),
            all_facilities=all_facilities
        )
        
    except Exception as e:
        print(f"Error in schedule_match_form: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading scheduling options: {str(e)}', 'danger')
        return redirect(url_for('matches'))


@schedule_bp.route('/matches/<int:match_id>/schedule/debug')
def debug_schedule_match_form(match_id: int):
    """
    Debug version with hardcoded data to test template rendering
    """
    from datetime import datetime, timedelta
    
    # Create mock data for testing
    base_date = datetime.now()
    
    mock_available_dates = []
    for i in range(5):
        date_obj = base_date + timedelta(days=i*7)
        date_str = date_obj.strftime('%Y-%m-%d')
        
        mock_date = {
            'date': date_str,
            'day_name': date_obj.strftime('%A'),
            'formatted_date': date_obj.strftime('%B %d, %Y'),
            'available_times': ['09:00', '10:00', '11:00', '14:00', '15:00'],
            'score': 8 - i,
            'conflicts': ['Team conflict'] if i == 2 else [],
            'courts_available': 6,
            'facility_name': 'Test Tennis Center'
        }
        mock_available_dates.append(mock_date)
    
    mock_match_info = {
        'id': match_id,
        'match_id': match_id,
        'home_team': 'Test Home Team',
        'visitor_team': 'Test Visitor Team',
        'league': 'Test League',
        'lines_needed': 3
    }
    
    mock_facility_info = {
        'id': 1,
        'name': 'Test Tennis Center',
        'location': '123 Tennis St, Tennis City, TC 12345',
        'total_courts': 6
    }
    
    return render_template(
        'schedule_match.html',
        match_info=mock_match_info,
        facility_info=mock_facility_info,
        available_dates=mock_available_dates,
        success=True,
        error=None,
        search_params={},
        all_facilities=[]
    )


@schedule_bp.route('/api/schedule/match', methods=['POST'])
def api_schedule_match():
    """
    API endpoint to schedule a match with enhanced split times support
    """
    try:
        from web_database import get_db
        
        # Get database connection
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'No database connection available'})
        
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        match_id = data.get('match_id')
        facility_id = data.get('facility_id')
        date = data.get('date')
        times = data.get('times', [])
        scheduling_mode = data.get('scheduling_mode', 'custom')


        
        # Validation
        if not all([match_id, date, times]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Get match and facility objects
        match = db.match_manager.get_match(match_id)
        if not match:
            return jsonify({'success': False, 'error': 'Match not found'})
        
        facility = None
        if facility_id:
            facility = db.facility_manager.get_facility(facility_id)
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        if not facility:
            return jsonify({'success': False, 'error': 'No facility available'})
        
        # Check for team conflicts (existing logic)
        if match.home_team:
            home_conflict = db.team_manager.check_team_date_conflict(
                team=match.home_team, date=date, exclude_match=match
            )
            if home_conflict:
                return jsonify({
                    'success': False, 
                    'error': f'Home team {match.home_team.name} has a conflict on {date}'
                })
        
        if match.visitor_team:
            visitor_conflict = db.team_manager.check_team_date_conflict(
                match.visitor_team, date, exclude_match=match
            )
            if visitor_conflict:
                return jsonify({
                    'success': False, 
                    'error': f'Visitor team {match.visitor_team.name} has a conflict on {date}'
                })
        
        # Enhanced validation for different scheduling modes
        lines_needed = match.league.num_lines_per_match if match.league else 3
        
        if scheduling_mode == 'custom':
            if len(times) != lines_needed:
                return jsonify({
                    'success': False, 
                    'error': f'Custom mode requires {lines_needed} times, got {len(times)}'
                })
        elif scheduling_mode in ['same_time', 'sequential']:
            if len(times) != 1:
                return jsonify({
                    'success': False, 
                    'error': f'{scheduling_mode} mode requires 1 time, got {len(times)}'
                })
        elif scheduling_mode == 'split_times':
            # NEW: Validation for split times mode
            if len(times) != 2:
                return jsonify({
                    'success': False, 
                    'error': f'Split times mode requires exactly 2 times, got {len(times)}'
                })
            
            # Validate that the two times are different and properly spaced
            time1, time2 = times[0], times[1]
            if time1 == time2:
                return jsonify({
                    'success': False, 
                    'error': 'Split times mode requires two different time slots'
                })
            
            # Sort times to ensure proper order
            times = sorted(times)
        
        # Perform the scheduling based on mode
        success = False
        error_message = None
        
        try:
            if scheduling_mode == 'same_time':
                success = db.schedule_match_all_lines_same_time(
                    match=match,
                    date=date,
                    time=times[0],
                    facility=facility
                )
            elif scheduling_mode == 'sequential':
                # Default to 3 hours (180 minutes) between lines
                success = db.schedule_match_sequential_times(
                    match=match,
                    date=date,
                    start_time=times[0],
                    interval_minutes=180,
                    facility=facility
                )
            elif scheduling_mode == 'split_times':
                # NEW: Handle split times scheduling
                
                # For split matches, the match_timeslots needs to have a time for every line
                match_timeslots = []
                
                # the times only has the two start times, but the 
                # scheduler wants times for every match.  Since we 
                # asked for ceil(num_lines)/2, we can assign
                # half and half.  TODO: make this a param
                num_lines = match.league.num_lines_per_match
                for i in range(0,math.ceil(num_lines/2)):
                    match_timeslots.append(times[0])
                for j in range(math.ceil(num_lines/2), num_lines):
                    match_timeslots.append(times[1])
                    
                if len(match_timeslots) != num_lines:
                    raise ValueError("WEB_SCHEDULE_MATCH: invalid number of timeslots")

                success = db.schedule_match_split_times(
                    match=match,
                    date=date,
                    timeslots=match_timeslots,
                    facility=facility
                )
            else:  # custom mode
                success = db.schedule_match_custom_times(
                    match=match,
                    facility=facility,
                    date=date,
                    times=times
                )
            
            if success:
                # Get updated match info
                updated_match = db.match_manager.get_match(match_id)
                
                # Prepare response with detailed scheduling info
                response_data = {
                    'success': True,
                    'message': 'Match scheduled successfully',
                    'match_details': {
                        'match_id': match_id,
                        'home_team': match.home_team.name if match.home_team else 'TBD',
                        'visitor_team': match.visitor_team.name if match.visitor_team else 'TBD',
                        'league': match.league.name if match.league else 'Unknown',
                        'date': date,
                        'facility': facility.name,
                        'scheduling_mode': scheduling_mode,
                        'selected_times': times,
                        'actual_scheduled_times': updated_match.scheduled_times if updated_match else []
                    }
                }
                
                # Add mode-specific details
                if scheduling_mode == 'split_times':
                    lines_in_first_slot = (lines_needed + 1) // 2
                    lines_in_second_slot = lines_needed - lines_in_first_slot
                    response_data['match_details']['split_info'] = {
                        'first_slot': {
                            'time': times[0],
                            'lines_count': lines_in_first_slot
                        },
                        'second_slot': {
                            'time': times[1],
                            'lines_count': lines_in_second_slot
                        }
                    }
                
                return jsonify(response_data)
            else:
                return jsonify({'success': False, 'error': 'Scheduling failed - facility conflicts or other issues'})
            
        except Exception as e:
            error_message = str(e)
            return jsonify({'success': False, 'error': f'Scheduling error: {error_message}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'})


@schedule_bp.route('/api/schedule/facility-availability/<int:facility_id>/<date>')
def api_facility_availability(facility_id: int, date: str):
    """
    API endpoint to get detailed facility availability for a specific date
    """
    from web_database import get_db
    
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'No database connection available'})
        
        facility = db.facility_manager.get_facility(facility_id)
        if not facility:
            return jsonify({'success': False, 'error': 'Facility not found'})
        
        # Get facility availability using manual schedule capability
        try:
            availability = db.get_facility_availability(facility, date)
        except ImportError:
            # Fallback if ManualScheduleMatchCapability not available
            availability = {
                'available_times': [],
                'busy_times': [],
                'message': 'Detailed availability checking not available'
            }
        
        return jsonify({
            'success': True,
            'availability': availability
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting facility availability: {str(e)}'
        })


@schedule_bp.route('/matches/<int:match_id>/schedule/refresh-options')
def refresh_scheduling_options(match_id: int):
    """
    Refresh scheduling options with different parameters
    """
    from web_database import get_db
    
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'No database connection available'})
        
        # Get match object
        match = db.get_match(match_id)
        if not match:
            return jsonify({'success': False, 'error': 'Match not found'})
        
        # Get parameters from request
        facility_id = request.args.get('facility_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        max_dates = int(request.args.get('max_dates', 20))
        
        # Get facility
        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)
        
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        
        if not facility:
            return jsonify({
                'success': False, 
                'error': 'No facility available for this match'
            })
        
        # Get fresh scheduling options
        scheduling_options = utils.get_scheduling_options(
            db=db,
            match=match,
            facility=facility,
            start_date=start_date,
            end_date=end_date,
            max_dates=max_dates
        )
        
        return jsonify(scheduling_options)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error refreshing options: {str(e)}'
        })



# Add to the route registration function
def add_scheduling_routes_to_app(app):
    """
    Register all scheduling routes with the Flask app
    Enhanced with split times support
    """
    # Register the blueprint
    app.register_blueprint(schedule_bp)
    
    # Add any additional configuration for split times
    app.config.setdefault('TENNIS_SPLIT_TIMES_ENABLED', True)
    app.config.setdefault('TENNIS_SPLIT_TIMES_MIN_GAP_HOURS', 1)
    app.config.setdefault('TENNIS_SPLIT_TIMES_DEFAULT_DISTRIBUTION', 'balanced')  # or 'majority_first'


# Alternative manual scheduling functions for direct use

def get_match_scheduling_data(match_id: int, facility_id: Optional[int] = None) -> dict:
    """
    Get scheduling data for a match (for use in other contexts)
    
    Args:
        match_id: Match ID to get scheduling options for
        facility_id: Optional facility ID (defaults to home team's facility)
        
    Returns:
        Dictionary with scheduling data
    """
    from web_database import get_db
    
    try:
        db = get_db()
        if db is None:
            return {'success': False, 'error': 'No database connection available'}
        match = db.get_match(match_id)
        if not match:
            return {'success': False, 'error': 'Match not found'}
        
        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)
        
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        
        if not facility:
            return {'success': False, 'error': 'No facility available'}
        
        return utils.get_scheduling_options(
            db=db,
            match=match,
            facility=facility
        )
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def schedule_match_from_optimal_date(match_id: int, selected_date: str, 
                                   selected_times: list, scheduling_mode: str = 'custom',
                                   facility_id: Optional[int] = None) -> dict:
    """
    Enhanced version with split_times support
    """
    from web_database import get_db
    
    try:
        db = get_db()
        if db is None:
            return {'success': False, 'error': 'No database connection available'}
        
        match = db.match_manager.get_match(match_id)
        if not match:
            return {'success': False, 'error': 'Match not found'}
        
        facility = None
        if facility_id:
            facility = db.facility_manager.get_facility(facility_id)
        
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        
        if not facility:
            return {'success': False, 'error': 'No facility available'}
        
        # Validate scheduling mode and times
        lines_needed = match.league.num_lines_per_match if match.league else 3
        
        if scheduling_mode == 'custom' and len(selected_times) != lines_needed:
            return {
                'success': False, 
                'error': f'Custom mode requires {lines_needed} times, got {len(selected_times)}'
            }
        
        if scheduling_mode in ['same_time', 'sequential'] and len(selected_times) != 1:
            return {
                'success': False, 
                'error': f'{scheduling_mode} mode requires 1 time, got {len(selected_times)}'
            }
        
        # NEW: Validate split_times mode
        if scheduling_mode == 'split_times' and len(selected_times) != 2:
            return {
                'success': False, 
                'error': f'Split times mode requires exactly 2 times, got {len(selected_times)}'
            }
        
        # Perform scheduling
        if scheduling_mode == 'same_time':
            success = db.schedule_match_all_lines_same_time(
                match, selected_date, selected_times[0], facility
            )
        elif scheduling_mode == 'sequential':
            success = db.schedule_match_sequential_times(
                match, selected_date, selected_times[0], 180, facility
            )
        elif scheduling_mode == 'split_times':
            # NEW: Handle split times scheduling
            success = db.schedule_match_split_times(
                match, selected_date, selected_times[0], selected_times[1], facility
            )
        else:  # custom
            success = db.schedule_match_custom_times(
                match, facility, selected_date, selected_times
            )
        
        if success:
            return {
                'success': True,
                'message': 'Match scheduled successfully',
                'match_id': match_id,
                'date': selected_date,
                'times': selected_times,
                'facility': facility.name,
                'mode': scheduling_mode
            }
        else:
            return {'success': False, 'error': 'Scheduling failed'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


# Enhanced helper function for split times validation
def validate_split_times(times, facility, date, lines_needed):
    """
    Validate that split times can accommodate the required lines
    
    Args:
        times: List of two time strings
        facility: Facility object
        date: Date string
        lines_needed: Number of lines to schedule
        
    Returns:
        (is_valid, error_message)
    """
    if len(times) != 2:
        return False, "Split times requires exactly 2 time slots"
    
    time1, time2 = sorted(times)
    
    # Check minimum gap between slots (should be at least 1 hour)
    try:
        from datetime import datetime, timedelta
        
        dt1 = datetime.strptime(time1, '%H:%M')
        dt2 = datetime.strptime(time2, '%H:%M')
        
        # Handle day rollover
        if dt2 < dt1:
            dt2 += timedelta(days=1)
        
        gap = dt2 - dt1
        if gap < timedelta(hours=1):
            return False, "Split time slots must be at least 1 hour apart"
        
    except ValueError:
        return False, "Invalid time format"
    
    # Calculate lines distribution
    lines_in_first_slot = (lines_needed + 1) // 2
    lines_in_second_slot = lines_needed - lines_in_first_slot
    
    # Check if both slots can accommodate their lines sequentially
    # This would require checking facility availability, but for now we'll assume it's valid
    # if the basic validation passes
    
    return True, None

# Example usage in a Flask app setup
"""
# In your main Flask app file:

from web_schedule_match import add_scheduling_routes_to_app

app = Flask(__name__)

# Add the scheduling routes to your app
add_scheduling_routes_to_app(app)

# Now the following routes will be available:
# GET  /matches/<match_id>/schedule  - Show scheduling form
# POST /api/schedule/match         - Schedule the match
# GET  /api/schedule/facility-availability/<facility_id>/<date> - Check availability
# GET  /matches/<match_id>/schedule/refresh-options - Refresh scheduling options
"""