"""
Flask Route Handler for Manual Match Scheduling
Fixed version with proper routes, data handling, and error handling
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from typing import Optional
import traceback
import math
from datetime import datetime, timedelta
from usta import League, Match, Facility, FacilityAvailabilityInfo, TimeSlotAvailability
from web_database import get_db, close_db
# Ensure we have the correct imports

from typing import List, Dict, Any, Tuple


# Create blueprint for scheduling routes
schedule_bp = Blueprint('schedule', __name__)

from usta import League, Match, Facility, FacilityAvailabilityInfo, TimeSlotAvailability





@schedule_bp.route('/matches/<int:match_id>/schedule')
def schedule_match_form(match_id: int):
    """
    Display the manual scheduling form for a specific match
    Updated to use db.get_facility_availability properly
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
        
        # Use the facility from the match
        facility = match.get_facility()
        if not facility:
            flash('No facility assigned to this match', 'warning')
            return redirect(url_for('matches'))

        print(f"\n\n\n============ Schedule Match Form =============\n\n\n")
        
        # Get scheduling options using facility availability
        try:
            # Get prioritized dates for this match
            num_dates = int(request.args.get('max_dates', 20))
            prioritized_dates = match.get_prioritized_scheduling_dates(num_dates=num_dates)
            
            if not prioritized_dates:
                flash('No prioritized dates available for scheduling', 'warning')
                return redirect(url_for('matches'))
            
            print(f"Checking facility availability for {len(prioritized_dates)} dates")
            
            # Get facility availability for all prioritized dates at once
            facility_availability_list = db.facility_manager.get_facility_availability(
                facility=facility, 
                dates=prioritized_dates, 
                max_days=num_dates * 2  # Allow some buffer
            )
            
            if not facility_availability_list:
                flash('No facility availability information found', 'warning')
                return redirect(url_for('matches'))
            
            print(f"Got {len(facility_availability_list)} facility availability records")
            
            # Convert FacilityAvailabilityInfo objects to format expected by template
            available_dates = []
            lines_needed = match.league.num_lines_per_match if match.league else 3
            allow_split_lines = league.allow_split_lines if league else False
            
            # If split lines are allowed, we need fewer courts per time slot
            courts_needed_per_slot = lines_needed
            if allow_split_lines:
                courts_needed_per_slot = math.ceil(lines_needed / 2)
            
            for facility_info in facility_availability_list:
                try:
                    print(f"\nProcessing date: {facility_info.date}, available: {facility_info.available}")
                    
                    # Skip unavailable dates
                    if not facility_info.available:
                        print(f"Skipping {facility_info.date}: {facility_info.reason}")
                        continue
                    
                    # Extract available times that can accommodate the needed courts
                    available_times = []
                    time_slot_details = []
                    
                    for time_slot in facility_info.time_slots:
                        if time_slot.can_accommodate(courts_needed_per_slot):
                            available_times.append(time_slot.time)
                            
                            # Add detailed time slot info for the template
                            time_slot_details.append({
                                'time': time_slot.time,
                                'available_courts': time_slot.available_courts,
                                'total_courts': time_slot.total_courts,
                                'utilization_percentage': time_slot.utilization_percentage,
                                'can_accommodate': time_slot.can_accommodate(courts_needed_per_slot)
                            })
                    
                    # Skip dates with no suitable times
                    if not available_times:
                        print(f"Skipping {facility_info.date}: no times can accommodate {courts_needed_per_slot} courts")
                        continue
                    
                    # Parse date for formatting
                    date_obj = datetime.strptime(facility_info.date, '%Y-%m-%d')
                    day_name = facility_info.day_of_week
                    
                    # Calculate scheduling score based on facility availability and match preferences
                    score = calculate_facility_scheduling_score(facility_info, match, lines_needed)
                    
                    # Check for team conflicts (optional - can be resource intensive)
                    conflicts = []
                    try:
                        conflicts = check_team_conflicts(db, match, facility_info.date)
                    except Exception as conflict_error:
                        print(f"Error checking conflicts for {facility_info.date}: {conflict_error}")
                        # Continue without conflicts info rather than failing
                    
                    # Create date option in the format expected by the template
                    date_option = {
                        'date': facility_info.date,
                        'day_name': day_name,
                        'formatted_date': date_obj.strftime('%B %d, %Y'),
                        'available_times': available_times,
                        'time_slot_details': time_slot_details,  # Enhanced court info per time
                        'score': max(0, score),
                        'conflicts': conflicts,
                        'courts_available': facility_info.available_court_slots,
                        'total_court_slots': facility_info.total_court_slots,
                        'utilization_percentage': facility_info.overall_utilization_percentage,
                        'facility_name': facility_info.facility_name
                    }
                    
                    available_dates.append(date_option)
                    print(f"Added date option: {facility_info.date} with {len(available_times)} times, score: {score}")
                    
                except Exception as date_processing_error:
                    print(f"Error processing facility info for {facility_info.date}: {date_processing_error}")
                    continue
            
            # Sort by score (highest first)
            available_dates.sort(key=lambda x: x['score'], reverse=True)
            
            print(f"Final available dates: {len(available_dates)}")
            
            scheduling_options = {
                'success': True,
                'available_dates': available_dates,
                'search_params': {
                    'start_date': request.args.get('start_date'),
                    'end_date': request.args.get('end_date'),
                    'max_dates': num_dates
                }
            }
            
        except Exception as scheduling_error:
            print(f"Error getting scheduling options: {scheduling_error}")
            import traceback
            traceback.print_exc()
            scheduling_options = {
                'success': False,
                'error': f'Error getting scheduling options: {str(scheduling_error)}',
                'available_dates': []
            }
        
        # Transform match data for template
        match_info = {
            'id': match.id,
            'match_id': match.id,
            'home_team': match.home_team.name if match.home_team else 'TBD',
            'visitor_team': match.visitor_team.name if match.visitor_team else 'TBD',
            'league': match.league.name if match.league else 'Unknown',
            'lines_needed': match.league.num_lines_per_match if match.league else 3,
            'allow_split_lines': allow_split_lines
        }
        
        # Transform facility data for template
        facility_info = {
            'id': facility.id,
            'name': facility.name,
            'location': getattr(facility, 'location', getattr(facility, 'address', None)),
            'total_courts': getattr(facility, 'total_courts', getattr(facility, 'court_count', 3))
        }
        
        # Get all facilities for dropdown
        all_facilities = db.list_facilities()
        
        return render_template(
            'schedule_match.html',
            match_info=match_info,
            facility_info=facility_info,
            available_dates=scheduling_options.get('available_dates', []),
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


# ====== Helper Functions for Scheduling Logic ======
def calculate_facility_scheduling_score(facility_info: FacilityAvailabilityInfo, match: Match, lines_needed: int) -> float:
    """
    Calculate a scheduling score based on facility availability and match preferences
    
    Args:
        facility_info: FacilityAvailabilityInfo object with detailed availability data
        match: Match object with league preferences
        lines_needed: Number of lines/courts needed
        
    Returns:
        Float score (higher is better)
    """
    base_score = 10.0
    
    # Prefer dates with lower overall utilization (more availability)
    utilization_bonus = (100 - facility_info.overall_utilization_percentage) / 10.0
    
    # Prefer dates that match league preferences
    day_preference_bonus = 0.0
    if match.league:
        if facility_info.day_of_week in getattr(match.league, 'preferred_days', []):
            day_preference_bonus = 5.0
        elif facility_info.day_of_week in getattr(match.league, 'backup_days', []):
            day_preference_bonus = 2.0
    
    # Bonus for having multiple suitable time slots (flexibility)
    suitable_slots = [slot for slot in facility_info.time_slots if slot.can_accommodate(lines_needed)]
    flexibility_bonus = min(len(suitable_slots) - 1, 3.0)  # Cap at 3 bonus points
    
    # Prefer weekends for recreational play (general bonus)
    weekend_bonus = 1.0 if facility_info.day_of_week in ['Saturday', 'Sunday'] else 0.0
    
    total_score = base_score + utilization_bonus + day_preference_bonus + flexibility_bonus + weekend_bonus
    return round(total_score, 1)


def check_team_conflicts(db, match, date):
    """Simple team conflict checking"""
    if match.home_team and db.check_team_date_conflict(match.home_team, date, exclude_match=match):
        return f'Home team {match.home_team.name} has a conflict on {date}'
    
    if match.visitor_team and db.check_team_date_conflict(match.visitor_team, date, exclude_match=match):
        return f'Visitor team {match.visitor_team.name} has a conflict on {date}'
    
    return None

# ======= Enhanced API Endpoint for Match Scheduling =======

# API endpoint to handle match scheduling with enhanced split times support
@schedule_bp.route('/api/schedule/match', methods=['POST'])
def api_schedule_match():
    """Simplified API endpoint using enhanced database validation"""
    try:
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
        
        # Basic validation
        if not all([match_id, date, times]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Get objects
        match = db.get_match(match_id)
        if not match:
            return jsonify({'success': False, 'error': 'Match not found'})
        
        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        if not facility:
            return jsonify({'success': False, 'error': 'No facility available'})
        
        # Check team conflicts (existing logic)
        team_conflict_error = check_team_conflicts(db, match, date)
        if team_conflict_error:
            return jsonify({'success': False, 'error': team_conflict_error})
        
        # Use the enhanced database method with validation
        result = db.schedule_match_with_validation(
            match=match,
            facility=facility,
            date=date,
            times=times,
            scheduling_mode=scheduling_mode
        )
        
        return jsonify(result)
        
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
        
        # Get facility availability using db.get_facility_availability
        try:
            facility_availability_list = db.facility_manager.get_facility_availability(
                facility=facility,
                dates=[date],
                max_days=1
            )
            
            if facility_availability_list and len(facility_availability_list) > 0:
                facility_info = facility_availability_list[0]
                
                if facility_info.available:
                    # Extract available and busy times
                    available_times = [slot.time for slot in facility_info.time_slots if slot.has_availability()]
                    busy_times = [slot.time for slot in facility_info.time_slots if slot.is_fully_booked()]
                    
                    availability = {
                        'available_times': available_times,
                        'busy_times': busy_times,
                        'time_slots': [slot.to_dict() for slot in facility_info.time_slots],
                        'overall_utilization': facility_info.overall_utilization_percentage,
                        'total_court_slots': facility_info.total_court_slots,
                        'available_court_slots': facility_info.available_court_slots,
                        'message': f'Found {len(available_times)} available time slots'
                    }
                else:
                    availability = {
                        'available_times': [],
                        'busy_times': [],
                        'message': facility_info.reason or 'Facility not available on this date'
                    }
            else:
                availability = {
                    'available_times': [],
                    'busy_times': [],
                    'message': 'No availability information found for this date'
                }
                
        except Exception as e:
            availability = {
                'available_times': [],
                'busy_times': [],
                'message': f'Error checking availability: {str(e)}'
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
        scheduling_options = get_scheduling_options_from_facility_availability(
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


@schedule_bp.route('/api/schedule/match/preview', methods=['POST'])
def api_preview_schedule_match():
    """Simplified preview endpoint"""
    try:
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
        
        # Basic validation
        if not all([match_id, facility_id, date, times]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Get objects
        match = db.get_match(match_id)
        if not match:
            return jsonify({'success': False, 'error': 'Match not found'})
        
        facility = db.get_facility(facility_id)
        if not facility:
            return jsonify({'success': False, 'error': 'Facility not found'})
        
        # Use the enhanced database preview method
        result = db.preview_match_scheduling(
            match=match,
            facility=facility,
            date=date,
            times=times,
            scheduling_mode=scheduling_mode
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error previewing schedule: {str(e)}'})



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


# ======== Scheduling Options Retrieval ========


# NEW: Using db.get_facility_availability
def get_scheduling_options_from_facility_availability(db, match, facility, start_date=None, end_date=None, max_dates=20):
    """
    Get scheduling options using db.get_facility_availability instead of utils.get_scheduling_options
    
    Returns:
        Dictionary with 'success', 'available_dates', and 'search_params' keys
    """
    try:
        # Generate date range to check
        from datetime import datetime, timedelta
        
        # Use provided dates or generate default range
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = datetime.now()
        
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_dt = start_dt + timedelta(days=max_dates * 2)  # Give buffer for finding enough dates
        
        # Generate list of dates to check
        dates_to_check = []
        current_dt = start_dt
        while current_dt <= end_dt and len(dates_to_check) < max_dates * 3:  # Extra buffer
            dates_to_check.append(current_dt.strftime('%Y-%m-%d'))
            current_dt += timedelta(days=1)
        
        # Get facility availability for all dates at once
        facility_availability_list = db.facility_manager.get_facility_availability(
            facility=facility,
            dates=dates_to_check,
            max_days=max_dates * 2
        )
        
        # Convert FacilityAvailabilityInfo objects to the format expected by the template
        available_dates = []
        lines_needed = match.league.num_lines_per_match if match.league else 3
        
        for facility_info in facility_availability_list:
            if not facility_info.available:
                continue  # Skip unavailable dates
            
            # Extract available times that can accommodate the needed lines
            available_times = []
            for time_slot in facility_info.time_slots:
                if time_slot.can_accommodate(lines_needed):
                    available_times.append(time_slot.time)
            
            if not available_times:
                continue  # Skip dates with no suitable times
            
            # Calculate scheduling score based on availability
            score = calculate_scheduling_score(facility_info, match, lines_needed)
            
            # Check for conflicts (team conflicts, etc.)
            conflicts = check_match_conflicts(db, match, facility_info.date, available_times)
            
            # Create date option in expected format
            date_option = {
                'date': facility_info.date,
                'day_name': facility_info.day_of_week,
                'formatted_date': format_date_for_display(facility_info.date),
                'available_times': available_times,
                'score': score,
                'conflicts': conflicts,
                'courts_available': facility_info.available_court_slots,
                'facility_name': facility_info.facility_name,
                'utilization_percentage': facility_info.overall_utilization_percentage
            }
            
            available_dates.append(date_option)
            
            # Stop once we have enough good options
            if len(available_dates) >= max_dates:
                break
        
        # Sort by score (highest first)
        available_dates.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'success': True,
            'available_dates': available_dates[:max_dates],
            'search_params': {
                'start_date': start_date,
                'end_date': end_date,
                'max_dates': max_dates
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error getting scheduling options: {str(e)}',
            'available_dates': []
        }

def calculate_scheduling_score(facility_info, match, lines_needed):
    """Calculate a scheduling score based on facility availability and match preferences"""
    base_score = 5
    
    # Prefer dates with lower overall utilization
    utilization_bonus = (100 - facility_info.overall_utilization_percentage) / 20
    
    # Prefer weekends for recreational leagues (if that info is available)
    weekend_bonus = 1 if facility_info.day_of_week in ['Saturday', 'Sunday'] else 0
    
    # Bonus for having multiple time options
    time_options_bonus = min(len([slot for slot in facility_info.time_slots if slot.can_accommodate(lines_needed)]) - 1, 3)
    
    return base_score + utilization_bonus + weekend_bonus + time_options_bonus

def check_match_conflicts(db, match, date, available_times):
    """Check for team conflicts on the given date/times"""
    conflicts = []
    
    for team in [match.home_team, match.visitor_team]:
        if team:
            for time in available_times[:3]:  # Check first few times only
                team_conflicts = db.scheduling_manager.get_team_conflicts(
                    team.id, date, time, duration_hours=3
                )
                conflicts.extend(team_conflicts)
    
    return conflicts

def format_date_for_display(date_str):
    """Format date string for display in template"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%B %d, %Y')
    except ValueError:
        return date_str



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
        
        return get_scheduling_options_from_facility_availability(
            db=db,
            match=match,
            facility=facility
        )
        
    except Exception as e:
        return {'success': False, 'error': str(e)}




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