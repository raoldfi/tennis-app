"""
Flask Route Handler for Manual Match Scheduling
Fixed version with proper routes, data handling, and error handling
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from typing import Optional
import traceback
import utils

# Create blueprint for scheduling routes
schedule_bp = Blueprint('schedule', __name__)



# Replace the schedule_match_form function in web_schedule_match.py with this debug version:

@schedule_bp.route('/matches/<int:match_id>/schedule')
def schedule_match_form(match_id: int):
    """
    Display the manual scheduling form for a specific match
    Uses utils.get_scheduling_options to get optimal dates
    """
    from web_database import get_db
    import utils  # Add local import
    
    try:
        # Get database interface using the standard pattern
        db = get_db()
        if db is None:
            flash('No database connection available', 'danger')
            return redirect(url_for('matches'))
        
        # Get match object
        match = db.get_match(match_id)
        if not match:
            flash(f'Match with ID {match_id} not found', 'danger')
            return redirect(url_for('matches'))
        
        # Check if match is already scheduled
        if match.is_scheduled():
            flash(f'Match is already scheduled for {match.date} at {match.facility.name}', 'info')
            return redirect(url_for('view_match', match_id=match_id))
        
        # Get facility (default to home team's facility)
        facility_id = request.args.get('facility_id', type=int)
        facility = None
        
        if facility_id:
            facility = db.get_facility(facility_id)
            if not facility:
                flash(f'Facility with ID {facility_id} not found', 'warning')
        
        # Use home team's facility if no facility specified
        if not facility and match.home_team:
            facility = match.home_team.home_facility
        
        if not facility:
            flash('No facility available for this match. Please assign a home facility to the home team or specify a facility.', 'danger')
            return redirect(url_for('view_match', match_id=match_id))
        
        # Get scheduling options using utils function
        scheduling_options = utils.get_scheduling_options(
            db=db,
            match=match,
            facility=facility,
            start_date=request.args.get('start_date'),
            end_date=request.args.get('end_date'),
            max_dates=int(request.args.get('max_dates', 20))
        )
        
        # Transform match data for template
        match_info = {
            'id': match.id,
            'home_team': match.home_team.name if match.home_team else 'TBD',
            'visitor_team': match.visitor_team.name if match.visitor_team else 'TBD',
            'league': match.league.name if match.league else 'Unknown',
            'lines_needed': match.league.num_lines_per_match if match.league else 3
        }
        
        # Transform facility data for template
        facility_info = {
            'id': facility.id,
            'name': facility.name,
            'location': getattr(facility, 'location', None),
            'total_courts': getattr(facility, 'court_count', getattr(facility, 'total_courts', 'Unknown'))
        }
        
        # Get all facilities for facility selection dropdown (optional feature)
        all_facilities = db.list_facilities()
        
        return render_template(
            'schedule_match.html',
            match_info=match_info,
            facility_info=facility_info,
            available_dates=scheduling_options.get('available_dates', []),
            success=scheduling_options.get('success', False),
            error=scheduling_options.get('error', 'Unknown error'),
            search_params=scheduling_options.get('search_params', {}),
            all_facilities=all_facilities
        )
        
    except Exception as e:
        flash(f'Error loading scheduling options: {str(e)}', 'danger')
        return redirect(url_for('matches'))


@schedule_bp.route('/api/schedule/match', methods=['POST'])
def api_schedule_match():
    """
    API endpoint to actually schedule a match
    """
    from web_database import get_db
    
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'No database connection available'})
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['match_id', 'date', 'times', 'scheduling_mode']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'})
        
        match_id = data['match_id']
        facility_id = data.get('facility_id')
        date = data['date']
        times = data['times']
        scheduling_mode = data['scheduling_mode']
        
        # Get match object
        match = db.match_manager.get_match(match_id)
        if not match:
            return jsonify({'success': False, 'error': 'Match not found'})
        
        # Get facility
        if facility_id:
            facility = db.facility_manager.get_facility(facility_id)
            if not facility:
                return jsonify({'success': False, 'error': 'Facility not found'})
        else:
            facility = match.home_team.home_facility if match.home_team else None
            if not facility:
                return jsonify({'success': False, 'error': 'No facility available'})
        
        # Validate times based on scheduling mode
        lines_needed = match.league.num_lines_per_match if match.league else 3
        
        if scheduling_mode == 'custom':
            if len(times) != lines_needed:
                return jsonify({
                    'success': False, 
                    'error': f'Custom mode requires exactly {lines_needed} times, got {len(times)}'
                })
        elif scheduling_mode in ['same_time', 'sequential']:
            if len(times) != 1:
                return jsonify({
                    'success': False, 
                    'error': f'{scheduling_mode} mode requires exactly 1 time, got {len(times)}'
                })
        
        # Validate that facility is available on the selected date
        if hasattr(facility, 'is_available_on_date') and not facility.is_available_on_date(date):
            return jsonify({
                'success': False, 
                'error': f'Facility {facility.name} is not available on {date}'
            })
        
        # Check for team conflicts
        if hasattr(db, 'team_manager'):
            home_conflict = db.team_manager.check_team_date_conflict(
                match.home_team.id, date, exclude_match_id=match.id
            ) if match.home_team else False
            
            if home_conflict:
                return jsonify({
                    'success': False, 
                    'error': f'Home team {match.home_team.name} has a conflict on {date}'
                })
            
            visitor_conflict = db.team_manager.check_team_date_conflict(
                match.visitor_team.id, date, exclude_match_id=match.id
            ) if match.visitor_team else False
            
            if visitor_conflict:
                return jsonify({
                    'success': False, 
                    'error': f'Visitor team {match.visitor_team.name} has a conflict on {date}'
                })
        
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
                return jsonify({
                    'success': True,
                    'message': 'Match scheduled successfully',
                    'match_details': {
                        'match_id': match_id,
                        'home_team': match.home_team.name if match.home_team else 'TBD',
                        'visitor_team': match.visitor_team.name if match.visitor_team else 'TBD',
                        'facility': facility.name,
                        'date': date,
                        'scheduled_times': updated_match.get_scheduled_times() if updated_match else times,
                        'scheduling_mode': scheduling_mode
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to schedule match - unknown scheduling error'
                })
                
        except Exception as scheduling_error:
            return jsonify({
                'success': False,
                'error': f'Scheduling error: {str(scheduling_error)}'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })


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
    import utils  # Add local import
    
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



def register_routes(app):
    """
    Helper function to add scheduling routes to Flask app
    
    Args:
        app: Flask application instance
    """
    # Register the blueprint
    app.register_blueprint(schedule_bp)


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
    import utils  # Add local import
    
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
    Schedule a match using selected optimal date and times
    
    Args:
        match_id: Match ID to schedule
        selected_date: Selected date from optimal dates
        selected_times: List of times for the match
        scheduling_mode: 'custom', 'same_time', or 'sequential'
        facility_id: Optional facility ID
        
    Returns:
        Dictionary with scheduling result
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
        
        # Perform scheduling
        if scheduling_mode == 'same_time':
            success = db.schedule_match_all_lines_same_time(
                match, selected_date, selected_times[0], facility
            )
        elif scheduling_mode == 'sequential':
            success = db.schedule_match_sequential_times(
                match, selected_date, selected_times[0], 180, facility
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