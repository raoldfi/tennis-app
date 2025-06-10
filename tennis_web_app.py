from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, g
from tennis_db_interface import TennisDBInterface
from usta import League, Team, Match, Facility, WeeklySchedule, DaySchedule, TimeSlot
import os
import json
from datetime import datetime
import threading
from typing import Optional, Type, Any, Dict
import yaml
import json
from flask import send_file, jsonify
from werkzeug.utils import secure_filename
import tempfile
import os
from io import StringIO, BytesIO
from datetime import datetime
import traceback


app = Flask(__name__)
app.secret_key = 'tennis_db_secret_key_change_in_production'

# Global database configuration
db_config = {
    'backend_class': None,
    'connection_params': {}
}

def configure_database(backend_class: Type[TennisDBInterface], **connection_params):
    """Configure the database backend and connection parameters"""
    global db_config
    db_config['backend_class'] = backend_class
    db_config['connection_params'] = connection_params

def get_db() -> Optional[TennisDBInterface]:
    """Get database connection for current thread"""
    if not hasattr(g, 'db') or g.db is None:
        if db_config['backend_class'] is None:
            return None
        try:
            # Updated to pass connection_params as config dictionary
            g.db = db_config['backend_class'](db_config['connection_params'])
            g.db.connect()
        except Exception as e:
            print(f"Error creating database connection: {e}")
            return None
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Close database connection at end of request"""
    db = getattr(g, 'db', None)
    if db is not None:
        try:
            db.disconnect()
        except:
            pass
        g.db = None

def init_db(backend_class: Type[TennisDBInterface], **connection_params) -> bool:
    """Initialize database with specified backend and parameters"""
    try:
        # Test the connection first - updated to pass config dictionary
        test_db = backend_class(connection_params)
        test_db.connect()
        if test_db.ping():
            test_db.disconnect()
            configure_database(backend_class, **connection_params)
            return True
        else:
            test_db.disconnect()
            return False
    except Exception as e:
        print(f"Error testing database: {e}")
        return False

@app.route('/')
def index():
    """Home page with database connection"""
    if db_config['backend_class'] is None:
        return render_template('connect.html')
    
    # Get connection info for display
    connection_info = str(db_config['connection_params'])
    return render_template('dashboard.html', db_path=connection_info)

@app.route('/connect', methods=['POST'])
def connect_db():
    """Connect to database"""
    db_path = request.form.get('db_path', '').strip()
    backend_type = request.form.get('backend_type', 'sqlite').strip()
    
    if not db_path:
        flash('Please provide a database path', 'error')
        return redirect(url_for('index'))
    
    # Import the appropriate backend class
    try:
        if backend_type.lower() == 'sqlite':
            from sqlite_tennis_db import SQLiteTennisDB
            backend_class = SQLiteTennisDB
            connection_params = {'db_path': db_path}
        else:
            flash(f'Unsupported backend type: {backend_type}', 'error')
            return redirect(url_for('index'))
        
        if init_db(backend_class, **connection_params):
            flash(f'Successfully connected to {db_path}', 'success')
        else:
            flash(f'Failed to connect to {db_path}', 'error')
    
    except ImportError as e:
        flash(f'Database backend not available: {e}', 'error')
    except Exception as e:
        flash(f'Error connecting to database: {e}', 'error')
    
    return redirect(url_for('index'))

@app.route('/disconnect')
def disconnect():
    """Disconnect from database"""
    global db_config
    # Close any existing connection in current thread
    close_db(None)
    db_config = {'backend_class': None, 'connection_params': {}}
    flash('Disconnected from database', 'info')
    return redirect(url_for('index'))

# ==================== FACILITY ROUTES ====================

@app.route('/facilities')
def facilities():
    """View all facilities"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        facilities_list = db.list_facilities()
        return render_template('facilities.html', facilities=facilities_list)
    except Exception as e:
        flash(f'Error loading facilities: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/facilities/<int:facility_id>')
def view_facility(facility_id):
    """View detailed facility information including schedule"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        facility = db.get_facility(facility_id)
        if not facility:
            flash(f'Facility with ID {facility_id} not found', 'error')
            return redirect(url_for('facilities'))
        
        return render_template('view_facility.html', facility=facility)
        
    except Exception as e:
        flash(f'Error loading facility: {e}', 'error')
        return redirect(url_for('facilities'))

@app.route('/facilities/add', methods=['GET', 'POST'])
def add_facility():
    """Add a new facility with schedule and unavailable dates"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            facility_id = int(request.form.get('id'))
            name = request.form.get('name', '').strip()
            location = request.form.get('location', '').strip()
            total_courts = int(request.form.get('total_courts', 0))
            
            if not name:
                flash('Facility name is required', 'error')
                return render_template('add_facility.html')
            
            # Create facility with basic info
            facility = Facility(
                id=facility_id, 
                name=name, 
                location=location,
                total_courts=total_courts
            )
            
            # Process schedule data from form
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                day_schedule = DaySchedule()
                
                # Get time slots for this day
                time_inputs = request.form.getlist(f'{day.lower()}_times')
                court_inputs = request.form.getlist(f'{day.lower()}_courts')
                
                for time_str, courts_str in zip(time_inputs, court_inputs):
                    if time_str.strip() and courts_str.strip():
                        try:
                            courts = int(courts_str)
                            if courts > 0:
                                time_slot = TimeSlot(time=time_str.strip(), available_courts=courts)
                                day_schedule.start_times.append(time_slot)
                        except ValueError:
                            continue  # Skip invalid entries
                
                facility.schedule.set_day_schedule(day, day_schedule)
            
            # Process unavailable dates
            unavailable_dates_str = request.form.get('unavailable_dates', '').strip()
            if unavailable_dates_str:
                dates = [date.strip() for date in unavailable_dates_str.split('\n') if date.strip()]
                facility.unavailable_dates = dates
            
            db.add_facility(facility)
            
            flash(f'Successfully added facility: {name}', 'success')
            return redirect(url_for('facilities'))
            
        except ValueError as e:
            if 'already exists' in str(e):
                flash(f'Facility with ID {facility_id} already exists', 'error')
            else:
                flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error adding facility: {e}', 'error')
        
        return render_template('add_facility.html')
    
    # GET request - show the form
    return render_template('add_facility.html')

@app.route('/facilities/<int:facility_id>/edit', methods=['GET', 'POST'])
def edit_facility(facility_id):
    """Edit an existing facility"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        facility = db.get_facility(facility_id)
        if not facility:
            flash(f'Facility with ID {facility_id} not found', 'error')
            return redirect(url_for('facilities'))
    except Exception as e:
        flash(f'Error loading facility: {e}', 'error')
        return redirect(url_for('facilities'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            location = request.form.get('location', '').strip()
            total_courts = int(request.form.get('total_courts', 0))
            
            if not name:
                flash('Facility name is required', 'error')
                return render_template('edit_facility.html', facility=facility)
            
            # Update facility with basic info
            facility.name = name
            facility.location = location
            facility.total_courts = total_courts
            
            # Process schedule data from form
            facility.schedule = WeeklySchedule()  # Reset schedule
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                day_schedule = DaySchedule()
                
                # Get time slots for this day
                time_inputs = request.form.getlist(f'{day.lower()}_times')
                court_inputs = request.form.getlist(f'{day.lower()}_courts')
                
                for time_str, courts_str in zip(time_inputs, court_inputs):
                    if time_str.strip() and courts_str.strip():
                        try:
                            courts = int(courts_str)
                            if courts > 0:
                                time_slot = TimeSlot(time=time_str.strip(), available_courts=courts)
                                day_schedule.start_times.append(time_slot)
                        except ValueError:
                            continue  # Skip invalid entries
                
                facility.schedule.set_day_schedule(day, day_schedule)
            
            # Process unavailable dates
            unavailable_dates_str = request.form.get('unavailable_dates', '').strip()
            if unavailable_dates_str:
                dates = [date.strip() for date in unavailable_dates_str.split('\n') if date.strip()]
                facility.unavailable_dates = dates
            else:
                facility.unavailable_dates = []
            
            db.update_facility(facility)
            
            flash(f'Successfully updated facility: {name}', 'success')
            return redirect(url_for('facilities'))
            
        except ValueError as e:
            flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error updating facility: {e}', 'error')
        
        return render_template('edit_facility.html', facility=facility)
    
    # GET request - show the form with existing data
    return render_template('edit_facility.html', facility=facility)

# ==================== FACILITY IMPORT/EXPORT ROUTES ====================

@app.route('/facilities/import', methods=['POST'])
def import_facilities():
    """Import facilities from YAML file"""
    db = get_db()
    if db is None:
        return jsonify({'success': False, 'error': 'No database connection'}), 500
    
    try:
        # Check if file was uploaded
        if 'yaml_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['yaml_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Check file extension
        if not file.filename.lower().endswith(('.yaml', '.yml')):
            return jsonify({'success': False, 'error': 'File must be a YAML file (.yaml or .yml)'}), 400
        
        # Read and parse YAML content
        try:
            yaml_content = file.read().decode('utf-8')
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return jsonify({
                'success': False, 
                'error': f'Invalid YAML format: {str(e)}',
                'details': str(e)
            }), 400
        except UnicodeDecodeError as e:
            return jsonify({
                'success': False, 
                'error': f'File encoding error: {str(e)}',
                'details': 'File must be UTF-8 encoded'
            }), 400
        
        # Validate data structure
        if not isinstance(data, dict):
            return jsonify({
                'success': False, 
                'error': 'YAML file must contain a dictionary at the root level'
            }), 400
        
        if 'facilities' not in data:
            return jsonify({
                'success': False, 
                'error': 'YAML file must contain a "facilities" key'
            }), 400
        
        facilities_data = data['facilities']
        if not isinstance(facilities_data, list):
            return jsonify({
                'success': False, 
                'error': 'facilities must be a list'
            }), 400
        
        # Import facilities
        imported_facilities = []
        errors = []
        
        for i, facility_data in enumerate(facilities_data):
            try:
                # Create facility object from YAML data
                facility = Facility.from_yaml_dict(facility_data)
                
                # Check if facility already exists
                existing = db.get_facility(facility.id)
                if existing:
                    # Update existing facility
                    db.update_facility(facility)
                    action = 'updated'
                else:
                    # Add new facility
                    db.add_facility(facility)
                    action = 'created'
                
                imported_facilities.append({
                    'id': facility.id,
                    'name': facility.name,
                    'location': facility.location,
                    'action': action
                })
                
            except Exception as e:
                errors.append(f"Facility {i+1}: {str(e)}")
        
        # Prepare response
        if imported_facilities:
            message = f"Successfully imported {len(imported_facilities)} facilities"
            if errors:
                message += f" ({len(errors)} errors)"
            
            response_data = {
                'success': True,
                'message': message,
                'imported_facilities': imported_facilities
            }
            
            if errors:
                response_data['errors'] = errors
            
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'error': 'No facilities could be imported',
                'details': '\n'.join(errors) if errors else 'Unknown error'
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}',
            'details': traceback.format_exc()
        }), 500


# Enhanced debug version of export routes with comprehensive error handling
# Add these to your tennis_web_app.py

import yaml
import json
from flask import send_file, jsonify, make_response
from werkzeug.utils import secure_filename
import tempfile
import os
from io import StringIO, BytesIO
from datetime import datetime
import traceback

@app.route('/facilities/export')
def export_facilities():
    """Export all facilities to YAML or JSON format with comprehensive error handling"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        export_format = request.args.get('format', 'yaml').lower()
        print(f"Export format requested: {export_format}")  # Debug
        
        facilities_list = db.list_facilities()
        print(f"Found {len(facilities_list)} facilities")  # Debug
        
        # Convert facilities to exportable format
        facilities_data = []
        for i, facility in enumerate(facilities_list):
            try:
                # Check if facility has to_yaml_dict method
                if hasattr(facility, 'to_yaml_dict'):
                    facility_dict = facility.to_yaml_dict()
                else:
                    # Fallback: create dict manually
                    print(f"Warning: Facility {facility.id} missing to_yaml_dict method, using fallback")
                    facility_dict = create_facility_dict_fallback(facility)
                
                facilities_data.append(facility_dict)
                print(f"Processed facility {i+1}: {facility.name}")  # Debug
                
            except Exception as e:
                print(f"Error processing facility {facility.id}: {str(e)}")
                return jsonify({'error': f'Error processing facility {facility.id}: {str(e)}'}), 500
        
        # Prepare export data
        export_data = {
            'facilities': facilities_data,
            'exported_at': datetime.now().isoformat(),
            'exported_count': len(facilities_data)
        }
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'json':
            try:
                # Export as JSON
                json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
                print(f"Generated JSON, length: {len(json_str)}")  # Debug
                
                # Create response with proper headers
                response = make_response(json_str)
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Disposition'] = f'attachment; filename=facilities_export_{timestamp}.json'
                return response
            except Exception as e:
                print(f"JSON export error: {str(e)}")
                return jsonify({'error': f'JSON serialization error: {str(e)}'}), 500
        else:
            try:
                # Export as YAML (default)
                yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
                print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
                
                # Create response with proper headers
                response = make_response(yaml_str)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = f'attachment; filename=facilities_export_{timestamp}.yaml'
                return response
            except Exception as e:
                print(f"YAML export error: {str(e)}")
                return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
    
    except Exception as e:
        print(f"General export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500


@app.route('/facilities/<int:facility_id>/export')
def export_single_facility(facility_id):
    """Export a single facility to YAML format with error handling"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        facility = db.get_facility(facility_id)
        if not facility:
            return jsonify({'error': f'Facility {facility_id} not found'}), 404
        
        print(f"Exporting facility: {facility.name}")  # Debug
        
        # Convert facility to exportable format
        try:
            if hasattr(facility, 'to_yaml_dict'):
                facility_dict = facility.to_yaml_dict()
            else:
                print(f"Warning: Facility {facility_id} missing to_yaml_dict method, using fallback")
                facility_dict = create_facility_dict_fallback(facility)
        except Exception as e:
            print(f"Error converting facility to dict: {str(e)}")
            return jsonify({'error': f'Error converting facility: {str(e)}'}), 500
        
        # Prepare export data
        export_data = {
            'facilities': [facility_dict],
            'exported_at': datetime.now().isoformat(),
            'facility_name': facility.name
        }
        
        try:
            # Generate YAML
            yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            print(f"Generated YAML for facility {facility_id}, length: {len(yaml_str)}")  # Debug
        except Exception as e:
            print(f"YAML generation error: {str(e)}")
            return jsonify({'error': f'YAML generation error: {str(e)}'}), 500
        
        # Generate filename
        safe_name = secure_filename(facility.name.replace(' ', '_'))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'facility_{facility_id}_{safe_name}_{timestamp}.yaml'
        
        # Create response with proper headers
        response = make_response(yaml_str)
        response.headers['Content-Type'] = 'application/x-yaml'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    
    except Exception as e:
        print(f"Single facility export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500


def create_facility_dict_fallback(facility):
    """Fallback function to create facility dictionary if to_yaml_dict method is missing"""
    try:
        # Build schedule dictionary
        schedule_dict = {}
        if hasattr(facility, 'schedule') and facility.schedule:
            for day_name, day_schedule in facility.schedule.get_all_days().items():
                if hasattr(day_schedule, 'start_times') and day_schedule.start_times:
                    # Convert start_times list to dictionary format
                    time_slots = {}
                    for time_str in day_schedule.start_times:
                        # Get courts available for this time slot
                        if hasattr(day_schedule, 'courts_by_time') and day_schedule.courts_by_time:
                            courts = day_schedule.courts_by_time.get(time_str, facility.total_courts)
                        else:
                            courts = facility.total_courts
                        time_slots[time_str] = courts
                    schedule_dict[day_name] = time_slots
        
        # Build the facility dictionary
        facility_dict = {
            'id': facility.id,
            'name': facility.name,
            'location': getattr(facility, 'location', ''),
            'total_courts': getattr(facility, 'total_courts', 0),
            'schedule': schedule_dict,
            'unavailable_dates': getattr(facility, 'unavailable_dates', []) or []
        }
        
        # Add short_name if it exists and is different from name
        if hasattr(facility, 'short_name') and facility.short_name and facility.short_name != facility.name:
            facility_dict['short_name'] = facility.short_name
        
        return facility_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert facility to dictionary: {str(e)}")


# Test route to check if export routes are working
@app.route('/facilities/export/test')
def test_export():
    """Test route to verify export functionality"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection', 'test': 'failed'})
        
        facilities_list = db.list_facilities()
        
        test_result = {
            'test': 'passed',
            'facilities_count': len(facilities_list),
            'yaml_available': 'yaml' in sys.modules,
            'json_available': 'json' in sys.modules,
            'facilities_sample': []
        }
        
        # Test first facility if available
        if facilities_list:
            facility = facilities_list[0]
            test_result['facilities_sample'] = [{
                'id': facility.id,
                'name': facility.name,
                'has_to_yaml_dict': hasattr(facility, 'to_yaml_dict'),
                'has_schedule': hasattr(facility, 'schedule'),
                'schedule_type': str(type(facility.schedule)) if hasattr(facility, 'schedule') else 'none'
            }]
        
        return jsonify(test_result)
        
    except Exception as e:
        return jsonify({
            'test': 'failed',
            'error': str(e),
            'traceback': traceback.format_exc()
        })
# ==================== LEAGUE ROUTES ====================

@app.route('/leagues', methods=['GET', 'POST'])
def leagues():
    """View all leagues and handle match generation"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    # Handle POST request for match generation
    if request.method == 'POST':
        league_id = request.form.get('league_id', type=int)
        if not league_id:
            flash('Please select a league', 'error')
        else:
            try:
                # Get league and teams
                league = db.get_league(league_id)
                if not league:
                    flash(f'League with ID {league_id} not found', 'error')
                else:
                    teams = db.list_teams(league_id=league_id)
                    if len(teams) < 2:
                        flash(f'League "{league.name}" has only {len(teams)} team(s). Need at least 2 teams to generate matches.', 'error')
                        return redirect(url_for('teams', league_id=league_id))
                    
                    # Generate matches using League.generate_matches()
                    matches = league.generate_matches(teams)
                    
                    # Add/update matches in database
                    created_matches = []
                    updated_matches = []
                    failed_matches = []
                    
                    for match in matches:
                        try:
                            # Check if match already exists
                            existing_match = db.get_match(match.id)
                            
                            if existing_match:
                                # Update existing match with new pairing data
                                db.update_match(match)
                                
                                # Find team names for response
                                home_team = next(team for team in teams if team.id == match.home_team_id)
                                visitor_team = next(team for team in teams if team.id == match.visitor_team_id)
                                
                                updated_matches.append({
                                    'match_id': match.id,
                                    'home_team': home_team.name,
                                    'visitor_team': visitor_team.name,
                                    'facility_id': match.facility_id
                                })
                            else:
                                # Create new match
                                db.add_match(match)
                                
                                # Find team names for response
                                home_team = next(team for team in teams if team.id == match.home_team_id)
                                visitor_team = next(team for team in teams if team.id == match.visitor_team_id)
                                
                                created_matches.append({
                                    'match_id': match.id,
                                    'home_team': home_team.name,
                                    'visitor_team': visitor_team.name,
                                    'facility_id': match.facility_id
                                })
                                
                        except Exception as e:
                            print(f"Warning: Could not create/update match {match.id}: {e}")
                            failed_matches.append({
                                'match_id': match.id,
                                'error': str(e)
                            })
                            continue
                    
                    # Show results
                    total_processed = len(created_matches) + len(updated_matches)
                    if total_processed > 0:
                        if created_matches and updated_matches:
                            flash(f'Successfully generated {len(created_matches)} new matches and updated {len(updated_matches)} existing matches for "{league.name}"!', 'success')
                        elif created_matches:
                            flash(f'Successfully generated {len(created_matches)} matches for "{league.name}"!', 'success')
                        elif updated_matches:
                            flash(f'Successfully updated {len(updated_matches)} existing matches for "{league.name}"!', 'success')
                        
                        if failed_matches:
                            flash(f'Warning: {len(failed_matches)} matches could not be processed due to errors', 'warning')
                    else:
                        flash('No matches were processed. Please check for errors.', 'error')
                        
            except Exception as e:
                flash(f'Error generating matches: {e}', 'error')
    
    # Handle GET request - show leagues
    try:
        leagues_list = db.list_leagues()
        return render_template('leagues.html', leagues=leagues_list)
    except Exception as e:
        flash(f'Error loading leagues: {e}', 'error')
        return redirect(url_for('index'))
        

@app.route('/leagues/add', methods=['GET', 'POST'])
def add_league():
    """Add a new league with enhanced scheduling options"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            league_id = int(request.form.get('id'))
            name = request.form.get('name', '').strip()
            year = int(request.form.get('year'))
            section = request.form.get('section', '').strip()
            region = request.form.get('region', '').strip()
            age_group = request.form.get('age_group', '').strip()
            division = request.form.get('division', '').strip()
            num_lines_per_match = int(request.form.get('num_lines_per_match', 3))
            
            # New fields
            num_matches = int(request.form.get('num_matches', 10))
            allow_split_lines = bool(int(request.form.get('allow_split_lines', 0)))
            
            # Get selected days (may be empty lists)
            preferred_days = request.form.getlist('preferred_days')
            backup_days = request.form.getlist('backup_days')
            
            # Get optional date fields
            start_date = request.form.get('start_date', '').strip() or None
            end_date = request.form.get('end_date', '').strip() or None
            
            if not all([name, section, region, age_group, division]):
                flash('All required fields must be filled', 'error')
                return render_template('add_league.html', 
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate number of matches
            if num_matches < 1 or num_matches > 50:
                flash('Number of matches must be between 1 and 50', 'error')
                return render_template('add_league.html', 
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate day selections (no overlap)
            overlapping_days = set(preferred_days) & set(backup_days)
            if overlapping_days:
                flash(f'Days cannot be both preferred and backup: {", ".join(sorted(overlapping_days))}', 'error')
                return render_template('add_league.html', 
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate dates if both are provided
            if start_date and end_date:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    if end_dt <= start_dt:
                        flash('End date must be after start date', 'error')
                        return render_template('add_league.html', 
                                             sections=get_usta_constants()['sections'],
                                             regions=get_usta_constants()['regions'],
                                             age_groups=get_usta_constants()['age_groups'],
                                             divisions=get_usta_constants()['divisions'])
                except ValueError:
                    flash('Invalid date format. Please use the date picker.', 'error')
                    return render_template('add_league.html', 
                                         sections=get_usta_constants()['sections'],
                                         regions=get_usta_constants()['regions'],
                                         age_groups=get_usta_constants()['age_groups'],
                                         divisions=get_usta_constants()['divisions'])
            
            league = League(
                id=league_id,
                name=name,
                year=year,
                section=section,
                region=region,
                age_group=age_group,
                division=division,
                num_lines_per_match=num_lines_per_match,
                num_matches=num_matches,
                allow_split_lines=allow_split_lines,
                preferred_days=preferred_days,
                backup_days=backup_days,
                start_date=start_date,
                end_date=end_date
            )
            db.add_league(league)
            
            # Create descriptive success message
            split_text = "Lines can be split" if allow_split_lines else "All lines start together"
            days_text = ""
            if preferred_days:
                days_text += f"Preferred days: {', '.join(preferred_days)}"
            if backup_days:
                if days_text:
                    days_text += f"; Backup days: {', '.join(backup_days)}"
                else:
                    days_text += f"Backup days: {', '.join(backup_days)}"
            
            flash(f'Successfully added league: {name} ({num_matches} matches per team, {num_lines_per_match} lines per match, {split_text})', 'success')
            if days_text:
                flash(f'Scheduling: {days_text}', 'info')
            
            return redirect(url_for('leagues'))
            
        except ValueError as e:
            if 'already exists' in str(e):
                flash(f'League with ID {league_id} already exists', 'error')
            else:
                flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error adding league: {e}', 'error')
        
        return render_template('add_league.html', 
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    
    # GET request - show the form
    try:
        return render_template('add_league.html', 
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('leagues'))

@app.route('/leagues/<int:league_id>/edit', methods=['GET', 'POST'])
def edit_league(league_id):
    """Edit an existing league"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        league = db.get_league(league_id)
        if not league:
            flash(f'League with ID {league_id} not found', 'error')
            return redirect(url_for('leagues'))
    except Exception as e:
        flash(f'Error loading league: {e}', 'error')
        return redirect(url_for('leagues'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            year = int(request.form.get('year'))
            section = request.form.get('section', '').strip()
            region = request.form.get('region', '').strip()
            age_group = request.form.get('age_group', '').strip()
            division = request.form.get('division', '').strip()
            num_lines_per_match = int(request.form.get('num_lines_per_match', 3))
            
            # New fields
            num_matches = int(request.form.get('num_matches', 10))
            allow_split_lines = bool(int(request.form.get('allow_split_lines', 0)))
            
            # Get selected days (may be empty lists)
            preferred_days = request.form.getlist('preferred_days')
            backup_days = request.form.getlist('backup_days')
            
            # Get optional date fields
            start_date = request.form.get('start_date', '').strip() or None
            end_date = request.form.get('end_date', '').strip() or None
            
            if not all([name, section, region, age_group, division]):
                flash('All required fields must be filled', 'error')
                return render_template('edit_league.html', 
                                     league=league,
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate number of matches
            if num_matches < 1 or num_matches > 50:
                flash('Number of matches must be between 1 and 50', 'error')
                return render_template('edit_league.html', 
                                     league=league,
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate day selections (no overlap)
            overlapping_days = set(preferred_days) & set(backup_days)
            if overlapping_days:
                flash(f'Days cannot be both preferred and backup: {", ".join(sorted(overlapping_days))}', 'error')
                return render_template('edit_league.html', 
                                     league=league,
                                     sections=get_usta_constants()['sections'],
                                     regions=get_usta_constants()['regions'],
                                     age_groups=get_usta_constants()['age_groups'],
                                     divisions=get_usta_constants()['divisions'])
            
            # Validate dates if both are provided
            if start_date and end_date:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    if end_dt <= start_dt:
                        flash('End date must be after start date', 'error')
                        return render_template('edit_league.html', 
                                             league=league,
                                             sections=get_usta_constants()['sections'],
                                             regions=get_usta_constants()['regions'],
                                             age_groups=get_usta_constants()['age_groups'],
                                             divisions=get_usta_constants()['divisions'])
                except ValueError:
                    flash('Invalid date format. Please use the date picker.', 'error')
                    return render_template('edit_league.html', 
                                         league=league,
                                         sections=get_usta_constants()['sections'],
                                         regions=get_usta_constants()['regions'],
                                         age_groups=get_usta_constants()['age_groups'],
                                         divisions=get_usta_constants()['divisions'])
            
            # Update the league object
            league.name = name
            league.year = year
            league.section = section
            league.region = region
            league.age_group = age_group
            league.division = division
            league.num_lines_per_match = num_lines_per_match
            league.num_matches = num_matches
            league.allow_split_lines = allow_split_lines
            league.preferred_days = preferred_days
            league.backup_days = backup_days
            league.start_date = start_date
            league.end_date = end_date
            
            db.update_league(league)
            
            # Create descriptive success message
            split_text = "Lines can be split" if allow_split_lines else "All lines start together"
            days_text = ""
            if preferred_days:
                days_text += f"Preferred days: {', '.join(preferred_days)}"
            if backup_days:
                if days_text:
                    days_text += f"; Backup days: {', '.join(backup_days)}"
                else:
                    days_text += f"Backup days: {', '.join(backup_days)}"
            
            flash(f'Successfully updated league: {name} ({num_matches} matches per team, {num_lines_per_match} lines per match, {split_text})', 'success')
            if days_text:
                flash(f'Scheduling: {days_text}', 'info')
            
            return redirect(url_for('leagues'))
            
        except ValueError as e:
            flash(f'Invalid data: {e}', 'error')
        except Exception as e:
            flash(f'Error updating league: {e}', 'error')
        
        return render_template('edit_league.html', 
                             league=league,
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    
    # GET request - show the form with existing data
    try:
        return render_template('edit_league.html', 
                             league=league,
                             sections=get_usta_constants()['sections'],
                             regions=get_usta_constants()['regions'],
                             age_groups=get_usta_constants()['age_groups'],
                             divisions=get_usta_constants()['divisions'])
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('leagues'))


# ==================== LEAGUE EXPORT/IMPORT ROUTES ====================

@app.route('/leagues/export')
def export_leagues():
    """Export all leagues to YAML or JSON format with comprehensive error handling"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        export_format = request.args.get('format', 'yaml').lower()
        print(f"Export format requested: {export_format}")  # Debug
        
        leagues_list = db.list_leagues()
        print(f"Found {len(leagues_list)} leagues")  # Debug
        
        # Convert leagues to exportable format
        leagues_data = []
        for i, league in enumerate(leagues_list):
            try:
                # Check if league has to_yaml_dict method
                if hasattr(league, 'to_yaml_dict'):
                    league_dict = league.to_yaml_dict()
                else:
                    # Fallback: create dict manually
                    print(f"Warning: League {league.id} missing to_yaml_dict method, using fallback")
                    league_dict = create_league_dict_fallback(league)
                
                leagues_data.append(league_dict)
                print(f"Processed league {i+1}: {league.name}")  # Debug
                
            except Exception as e:
                print(f"Error processing league {league.id}: {str(e)}")
                return jsonify({'error': f'Error processing league {league.id}: {str(e)}'}), 500
        
        # Prepare export data
        export_data = {
            'leagues': leagues_data,
            'exported_at': datetime.now().isoformat(),
            'exported_count': len(leagues_data)
        }
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'json':
            try:
                # Export as JSON
                json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
                print(f"Generated JSON, length: {len(json_str)}")  # Debug
                
                # Create response with proper headers
                response = make_response(json_str)
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Disposition'] = f'attachment; filename=leagues_export_{timestamp}.json'
                return response
            except Exception as e:
                print(f"JSON export error: {str(e)}")
                return jsonify({'error': f'JSON serialization error: {str(e)}'}), 500
        else:
            try:
                # Export as YAML (default)
                yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
                print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
                
                # Create response with proper headers
                response = make_response(yaml_str)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = f'attachment; filename=leagues_export_{timestamp}.yaml'
                return response
            except Exception as e:
                print(f"YAML export error: {str(e)}")
                return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
    
    except Exception as e:
        print(f"General export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500


@app.route('/leagues/<int:league_id>/export')
def export_single_league(league_id):
    """Export a single league to YAML format with error handling"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        league = db.get_league(league_id)
        if not league:
            return jsonify({'error': f'League {league_id} not found'}), 404
        
        print(f"Exporting league: {league.name}")  # Debug
        
        # Convert league to exportable format
        try:
            if hasattr(league, 'to_yaml_dict'):
                league_dict = league.to_yaml_dict()
            else:
                print(f"Warning: League {league_id} missing to_yaml_dict method, using fallback")
                league_dict = create_league_dict_fallback(league)
        except Exception as e:
            print(f"Error converting league to dict: {str(e)}")
            return jsonify({'error': f'Error converting league: {str(e)}'}), 500
        
        # Prepare export data
        export_data = {
            'leagues': [league_dict],
            'exported_at': datetime.now().isoformat(),
            'league_name': league.name
        }
        
        try:
            # Generate YAML
            yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
            
            # Create response with proper headers
            safe_filename = secure_filename(f"{league.name}_{league.year}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            response = make_response(yaml_str)
            response.headers['Content-Type'] = 'application/x-yaml'
            response.headers['Content-Disposition'] = f'attachment; filename=league_{safe_filename}_{timestamp}.yaml'
            return response
            
        except Exception as e:
            print(f"YAML export error: {str(e)}")
            return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
    
    except Exception as e:
        print(f"General export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500


@app.route('/leagues/import', methods=['POST'])
def import_leagues():
    """Import leagues from YAML file"""
    db = get_db()
    if db is None:
        return jsonify({'success': False, 'error': 'No database connection'}), 500
    
    try:
        # Check if file was uploaded
        if 'yaml_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['yaml_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Check file extension
        if not file.filename.lower().endswith(('.yaml', '.yml')):
            return jsonify({'success': False, 'error': 'File must be a YAML file (.yaml or .yml)'}), 400
        
        # Read and parse YAML content
        try:
            yaml_content = file.read().decode('utf-8')
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return jsonify({
                'success': False, 
                'error': f'Invalid YAML format: {str(e)}',
                'details': str(e)
            }), 400
        except UnicodeDecodeError as e:
            return jsonify({
                'success': False, 
                'error': f'File encoding error: {str(e)}',
                'details': 'File must be UTF-8 encoded'
            }), 400
        
        # Validate data structure
        if not isinstance(data, dict):
            return jsonify({
                'success': False, 
                'error': 'Invalid file format: Root element must be a dictionary'
            }), 400
        
        if 'leagues' not in data:
            return jsonify({
                'success': False, 
                'error': 'Invalid file format: Missing "leagues" key'
            }), 400
        
        if not isinstance(data['leagues'], list):
            return jsonify({
                'success': False, 
                'error': 'Invalid file format: "leagues" must be a list'
            }), 400
        
        # Import leagues
        imported_count = 0
        updated_count = 0
        errors = []
        
        for i, league_data in enumerate(data['leagues']):
            try:
                # Check if it's already a League object or needs conversion
                if hasattr(league_data, '__dict__'):
                    league = league_data
                else:
                    # Create League from dict data
                    if hasattr(League, 'from_yaml_dict'):
                        league = League.from_yaml_dict(league_data)
                    else:
                        # Fallback: create League object manually
                        league = create_league_from_dict_fallback(league_data)
                
                # Check if league already exists
                existing_league = None
                try:
                    existing_league = db.get_league(league.id) if hasattr(league, 'id') and league.id else None
                except:
                    pass
                
                if existing_league:
                    # Update existing league
                    db.update_league(league)
                    updated_count += 1
                else:
                    # Insert new league
                    db.add_league(league)
                    imported_count += 1
                    
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")
                continue
        
        result = {
            'success': True,
            'imported_count': imported_count,
            'updated_count': updated_count,
            'total_processed': imported_count + updated_count,
            'error_count': len(errors)
        }
        
        if errors:
            result['errors'] = errors[:10]  # Limit error messages
            if len(errors) > 10:
                result['additional_errors'] = len(errors) - 10
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Import failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


def create_league_dict_fallback(league):
    """Fallback method to convert League object to dictionary"""
    try:
        league_dict = {
            'id': league.id,
            'name': league.name,
            'year': league.year,
            'section': league.section,
            'region': league.region,
            'age_group': league.age_group,
            'division': league.division,
            'num_matches': league.num_matches,
            'num_lines_per_match': league.num_lines_per_match,
            'allow_split_lines': league.allow_split_lines
        }
        
        # Add optional fields if they exist
        if hasattr(league, 'start_date') and league.start_date:
            league_dict['start_date'] = league.start_date
        if hasattr(league, 'end_date') and league.end_date:
            league_dict['end_date'] = league.end_date
        if hasattr(league, 'preferred_days') and league.preferred_days:
            league_dict['preferred_days'] = league.preferred_days
        
        return league_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert league to dictionary: {str(e)}")


def create_league_from_dict_fallback(league_data):
    """Fallback method to create League object from dictionary"""
    try:
        # Create League with required fields
        league = League(
            id=league_data.get('id'),
            name=league_data['name'],
            year=league_data['year'],
            section=league_data['section'],
            region=league_data['region'],
            age_group=league_data['age_group'],
            division=league_data['division'],
            num_matches=league_data.get('num_matches', 6),
            num_lines_per_match=league_data.get('num_lines_per_match', 4),
            allow_split_lines=league_data.get('allow_split_lines', False)
        )
        
        # Add optional fields if they exist
        if 'start_date' in league_data:
            league.start_date = league_data['start_date']
        if 'end_date' in league_data:
            league.end_date = league_data['end_date']
        if 'preferred_days' in league_data:
            league.preferred_days = league_data['preferred_days']
        
        return league
        
    except Exception as e:
        print(f"Fallback creation error: {str(e)}")
        raise Exception(f"Could not create league from dictionary: {str(e)}")

# Test routes for export/import functionality
@app.route('/leagues/export/test')
def test_leagues_export():
    """Test route to verify league export functionality"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection', 'test': 'failed'})
        
        leagues_list = db.list_leagues()
        
        test_result = {
            'test': 'passed',
            'leagues_count': len(leagues_list),
            'yaml_available': 'yaml' in sys.modules,
            'json_available': 'json' in sys.modules,
            'leagues_sample': []
        }
        
        # Test first league if available
        if leagues_list:
            league = leagues_list[0]
            test_result['leagues_sample'] = [{
                'id': league.id,
                'name': league.name,
                'has_to_yaml_dict': hasattr(league, 'to_yaml_dict'),
                'year': league.year,
                'section': league.section
            }]
        
        return jsonify(test_result)
        
    except Exception as e:
        return jsonify({
            'test': 'failed',
            'error': str(e),
            'traceback': traceback.format_exc()
        })


# ==================== TEAM ROUTES ====================

# Fix for the teams() route in tennis_web_app.py

@app.route('/teams')
def teams():
    """View teams with optional league filter and enhanced facility information"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    # Fix: Handle league_id parameter more safely
    league_id = None
    try:
        league_id_str = request.args.get('league_id')
        if league_id_str:
            league_id = int(league_id_str)
    except (ValueError, TypeError):
        # If conversion fails, ignore the parameter
        league_id = None
    
    try:
        teams_list = db.list_teams(league_id=league_id)
        leagues_list = db.list_leagues()  # For filter dropdown
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            selected_league = db.get_league(league_id)
        
        # Create enhanced team objects that match what the template expects
        enhanced_teams = []
        for team in teams_list:
            # Check if the facility exists in the database
            facility_exists = True
            facility_id = None
            facility_name = "Unknown"
            
            try:
                # Try to get the facility by ID if the home_facility has an id
                if hasattr(team.home_facility, 'id') and team.home_facility.id:
                    facility_id = team.home_facility.id
                    facility = db.get_facility(facility_id)
                    facility_exists = facility is not None
                    if facility:
                        facility_name = facility.name
                    else:
                        facility_name = f"Facility ID {facility_id} (Not Found)"
                elif hasattr(team.home_facility, 'name') and team.home_facility.name:
                    # If it's a facility object with name but no/invalid ID
                    facility_name = team.home_facility.name
                    facility_exists = False  # Custom facility name
                else:
                    # Fallback - check if home_facility is a string
                    facility_name = str(team.home_facility) if team.home_facility else "Unknown"
                    facility_exists = False
            except Exception as e:
                print(f"Warning: Error processing facility for team {team.id}: {e}")
                facility_exists = False
                facility_name = "Error loading facility"
            
            # Check if team has preferred days
            has_preferred_days = (hasattr(team, 'preferred_days') and 
                                team.preferred_days and 
                                len(team.preferred_days) > 0)
            
            enhanced_team = {
                'team': team,
                'facility_exists': facility_exists,
                'facility_id': facility_id,
                'facility_name': facility_name,
                'has_preferred_days': has_preferred_days
            }
            enhanced_teams.append(enhanced_team)
        
        return render_template('teams.html', 
                             teams=enhanced_teams,
                             leagues=leagues_list,
                             selected_league=selected_league)
    
    except Exception as e:
        print(f"Error in teams route: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading teams: {e}', 'error')
        return redirect(url_for('index'))


@app.route('/teams/add', methods=['GET', 'POST'])
def add_team():
    # ADD THIS LINE - Get database connection first!
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Get facility object instead of facility name
            facility_id = int(request.form.get('home_facility_id'))
            facility = db.get_facility(facility_id)
            if not facility:
                flash('Invalid facility selected.', 'error')
                return redirect(url_for('add_team'))
            
            # Create team with Facility object
            team = Team(
                id=int(request.form.get('id')),
                name=request.form.get('name'),
                league=db.get_league(int(request.form.get('league_id'))),
                home_facility=facility,  # CHANGED: pass Facility object
                captain=request.form.get('captain') or None,
                preferred_days=request.form.getlist('preferred_days')
            )
            
            db.add_team(team)
            flash('Team added successfully!', 'success')
            return redirect(url_for('teams'))
            
        except Exception as e:
            flash(f'Error adding team: {e}', 'error')
    
    # GET request - show form
    leagues = db.list_leagues()
    facilities = db.list_facilities()  # For dropdown
    return render_template('add_team.html', leagues=leagues, facilities=facilities)


@app.route('/teams/<int:team_id>/edit', methods=['GET', 'POST'])
def edit_team(team_id):
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        team = db.get_team(team_id)
        if not team:
            flash('Team not found.', 'error')
            return redirect(url_for('teams'))
    except Exception as e:
        flash(f'Error loading team: {e}', 'error')
        return redirect(url_for('teams'))
    
    if request.method == 'POST':
        try:
            # Get facility object instead of facility name
            facility_id = int(request.form.get('home_facility_id'))
            facility = db.get_facility(facility_id)
            if not facility:
                flash('Invalid facility selected.', 'error')
                return redirect(url_for('edit_team', team_id=team_id))
            
            # Update team with new Facility object
            updated_team = Team(
                id=team.id,
                name=request.form.get('name'),
                league=db.get_league(int(request.form.get('league_id'))),
                home_facility=facility,  # CHANGED: pass Facility object
                captain=request.form.get('captain') or None,
                preferred_days=request.form.getlist('preferred_days')
            )
            
            db.update_team(updated_team)
            flash('Team updated successfully!', 'success')
            return redirect(url_for('teams'))
            
        except Exception as e:
            flash(f'Error updating team: {e}', 'error')
    
    # GET request - show form
    try:
        leagues = db.list_leagues()
        facilities = db.list_facilities()  # For dropdown
        return render_template('edit_team.html', team=team, leagues=leagues, facilities=facilities)
    except Exception as e:
        flash(f'Error loading form data: {e}', 'error')
        return redirect(url_for('teams'))


@app.route('/teams/<int:team_id>/delete', methods=['DELETE'])
def delete_team_api(team_id):
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        db.delete_team(team_id)
        return jsonify({'success': True, 'message': f'Team {team_id} deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/teams/export')
def export_teams():
    """Export all teams to YAML or JSON format with comprehensive error handling"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        export_format = request.args.get('format', 'yaml').lower()
        league_id = request.args.get('league_id', type=int)
        print(f"Export format requested: {export_format}")  # Debug
        print(f"League filter: {league_id}")  # Debug
        
        teams_list = db.list_teams(league_id=league_id)
        print(f"Found {len(teams_list)} teams")  # Debug
        
        # Convert teams to exportable format
        teams_data = []
        for i, team in enumerate(teams_list):
            try:
                # Check if team has to_yaml_dict method
                if hasattr(team, 'to_yaml_dict'):
                    team_dict = team.to_yaml_dict()
                else:
                    # Fallback: create dict manually
                    print(f"Warning: Team {team.id} missing to_yaml_dict method, using fallback")
                    team_dict = create_team_dict_fallback(team)
                
                teams_data.append(team_dict)
                print(f"Processed team {i+1}: {team.name}")  # Debug
                
            except Exception as e:
                print(f"Error processing team {team.id}: {str(e)}")
                return jsonify({'error': f'Error processing team {team.id}: {str(e)}'}), 500
        
        # Prepare export data
        export_data = {
            'teams': teams_data,
            'exported_at': datetime.now().isoformat(),
            'exported_count': len(teams_data)
        }
        
        if league_id:
            export_data['league_filter'] = league_id
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        league_suffix = f"_league_{league_id}" if league_id else ""
        
        if export_format == 'json':
            try:
                # Export as JSON
                json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
                print(f"Generated JSON, length: {len(json_str)}")  # Debug
                
                # Create response with proper headers
                response = make_response(json_str)
                response.headers['Content-Type'] = 'application/json'
                response.headers['Content-Disposition'] = f'attachment; filename=teams_export{league_suffix}_{timestamp}.json'
                return response
            except Exception as e:
                print(f"JSON export error: {str(e)}")
                return jsonify({'error': f'JSON serialization error: {str(e)}'}), 500
        else:
            try:
                # Export as YAML (default)
                yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
                print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
                
                # Create response with proper headers
                response = make_response(yaml_str)
                response.headers['Content-Type'] = 'application/x-yaml'
                response.headers['Content-Disposition'] = f'attachment; filename=teams_export{league_suffix}_{timestamp}.yaml'
                return response
            except Exception as e:
                print(f"YAML export error: {str(e)}")
                return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
    
    except Exception as e:
        print(f"General export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500


@app.route('/teams/<int:team_id>/export')
def export_single_team(team_id):
    """Export a single team to YAML format with error handling"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection'}), 500
        
        team = db.get_team(team_id)
        if not team:
            return jsonify({'error': f'Team {team_id} not found'}), 404
        
        print(f"Exporting team: {team.name}")  # Debug
        
        # Convert team to exportable format
        try:
            if hasattr(team, 'to_yaml_dict'):
                team_dict = team.to_yaml_dict()
            else:
                print(f"Warning: Team {team_id} missing to_yaml_dict method, using fallback")
                team_dict = create_team_dict_fallback(team)
        except Exception as e:
            print(f"Error converting team to dict: {str(e)}")
            return jsonify({'error': f'Error converting team: {str(e)}'}), 500
        
        # Prepare export data
        export_data = {
            'teams': [team_dict],
            'exported_at': datetime.now().isoformat(),
            'team_name': team.name
        }
        
        try:
            # Generate YAML
            yaml_str = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            print(f"Generated YAML, length: {len(yaml_str)}")  # Debug
            
            # Create response with proper headers
            safe_filename = secure_filename(team.name)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            response = make_response(yaml_str)
            response.headers['Content-Type'] = 'application/x-yaml'
            response.headers['Content-Disposition'] = f'attachment; filename=team_{safe_filename}_{timestamp}.yaml'
            return response
            
        except Exception as e:
            print(f"YAML export error: {str(e)}")
            return jsonify({'error': f'YAML serialization error: {str(e)}'}), 500
    
    except Exception as e:
        print(f"General export error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Export failed: {str(e)}', 'traceback': traceback.format_exc()}), 500


@app.route('/teams/import', methods=['POST'])
def import_teams():
    """Import teams from YAML file"""
    db = get_db()
    if db is None:
        return jsonify({'success': False, 'error': 'No database connection'}), 500
    
    try:
        # Check if file was uploaded
        if 'yaml_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['yaml_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Check file extension
        if not file.filename.lower().endswith(('.yaml', '.yml')):
            return jsonify({'success': False, 'error': 'File must be a YAML file (.yaml or .yml)'}), 400
        
        # Read and parse YAML content
        try:
            yaml_content = file.read().decode('utf-8')
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return jsonify({
                'success': False, 
                'error': f'Invalid YAML format: {str(e)}',
                'details': str(e)
            }), 400
        except UnicodeDecodeError as e:
            return jsonify({
                'success': False, 
                'error': f'File encoding error: {str(e)}',
                'details': 'File must be UTF-8 encoded'
            }), 400
        
        # Validate data structure
        if not isinstance(data, dict):
            return jsonify({
                'success': False, 
                'error': 'Invalid file format: Root element must be a dictionary'
            }), 400
        
        if 'teams' not in data:
            return jsonify({
                'success': False, 
                'error': 'Invalid file format: Missing "teams" key'
            }), 400
        
        if not isinstance(data['teams'], list):
            return jsonify({
                'success': False, 
                'error': 'Invalid file format: "teams" must be a list'
            }), 400
        
        # Import teams
        imported_count = 0
        updated_count = 0
        errors = []
        
        for i, team_data in enumerate(data['teams']):
            try:
                # Check if it's already a Team object or needs conversion
                if hasattr(team_data, '__dict__'):
                    team = team_data
                else:
                    # Create Team from dict data
                    if hasattr(Team, 'from_yaml_dict'):
                        team = Team.from_yaml_dict(team_data)
                    else:
                        # Fallback: create Team object manually
                        team = create_team_from_dict_fallback(team_data, db)
                
                # Check if team already exists
                existing_team = None
                try:
                    existing_team = db.get_team(team.id) if hasattr(team, 'id') and team.id else None
                except:
                    pass
                
                if existing_team:
                    # Update existing team
                    db.update_team(team)
                    updated_count += 1
                else:
                    # Insert new team
                    db.add_team(team)
                    imported_count += 1
                    
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")
                continue
        
        result = {
            'success': True,
            'imported_count': imported_count,
            'updated_count': updated_count,
            'total_processed': imported_count + updated_count,
            'error_count': len(errors)
        }
        
        if errors:
            result['errors'] = errors[:10]  # Limit error messages
            if len(errors) > 10:
                result['additional_errors'] = len(errors) - 10
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Import failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


def create_team_dict_fallback(team):
    """Fallback method to convert Team object to dictionary"""
    try:
        team_dict = {
            'id': team.id,
            'name': team.name,
            'league_id': team.league.id if hasattr(team, 'league') and team.league else None,
            'captain': team.captain
        }
        
        # Handle home facility - export the facility ID if available
        if hasattr(team, 'home_facility') and team.home_facility:
            if hasattr(team.home_facility, 'id') and team.home_facility.id:
                team_dict['home_facility_id'] = team.home_facility.id
            # Also include the facility name for reference
            if hasattr(team.home_facility, 'name'):
                team_dict['home_facility_name'] = team.home_facility.name
        elif hasattr(team, 'home_facility_id') and team.home_facility_id:
            # Fallback if only ID is available
            team_dict['home_facility_id'] = team.home_facility_id
        
        # Add optional fields if they exist
        if hasattr(team, 'preferred_days') and team.preferred_days:
            team_dict['preferred_days'] = team.preferred_days
        if hasattr(team, 'contact_email') and team.contact_email:
            team_dict['contact_email'] = team.contact_email
        if hasattr(team, 'notes') and team.notes:
            team_dict['notes'] = team.notes
        
        return team_dict
        
    except Exception as e:
        print(f"Fallback conversion error: {str(e)}")
        raise Exception(f"Could not convert team to dictionary: {str(e)}")


def create_team_from_dict_fallback(team_data, db):
    """Fallback method to create Team object from dictionary"""
    try:
        # Get league object if league_id is provided
        league = None
        if 'league_id' in team_data and team_data['league_id']:
            try:
                league = db.get_league(team_data['league_id'])
                if not league:
                    raise Exception(f"League with ID {team_data['league_id']} not found")
            except Exception as e:
                raise Exception(f"Invalid league_id {team_data['league_id']}: {str(e)}")
        
        # Handle home facility - get the actual Facility object
        home_facility = None
        
        if 'home_facility_id' in team_data and team_data['home_facility_id']:
            # Primary method: use facility ID to get Facility object
            try:
                home_facility = db.get_facility(team_data['home_facility_id'])
                if not home_facility:
                    raise Exception(f"Facility with ID {team_data['home_facility_id']} not found")
            except Exception as e:
                raise Exception(f"Invalid home_facility_id {team_data['home_facility_id']}: {str(e)}")
                
        elif 'home_facility' in team_data and team_data['home_facility']:
            # Legacy support: try to find facility by name
            facility_name = team_data['home_facility']
            try:
                facilities = db.list_facilities()
                for facility in facilities:
                    if facility.name == facility_name:
                        home_facility = facility
                        break
                
                if not home_facility:
                    # Create a minimal facility object for custom names
                    # This depends on your Facility class constructor
                    print(f"Warning: Facility '{facility_name}' not found in database, creating custom facility reference")
                    # You may need to adjust this based on your Facility class constructor
                    from usta import Facility
                    home_facility = Facility(
                        id=None,
                        name=facility_name,
                        location='Unknown',
                        schedule=None  # or create a default schedule
                    )
            except Exception as e:
                print(f"Error looking up facility by name: {str(e)}")
                # Create minimal facility object as fallback
                from usta import Facility
                home_facility = Facility(
                    id=None,
                    name=facility_name,
                    location='Unknown',
                    schedule=None
                )
        
        # Create Team with required fields
        team = Team(
            id=team_data.get('id'),
            name=team_data['name'],
            league=league,
            captain=team_data.get('captain', ''),
            home_facility=home_facility  # Pass the Facility object
        )
        
        # Add optional fields if they exist
        if 'preferred_days' in team_data:
            team.preferred_days = team_data['preferred_days']
        if 'contact_email' in team_data:
            team.contact_email = team_data['contact_email']
        if 'notes' in team_data:
            team.notes = team_data['notes']
        
        return team
        
    except Exception as e:
        print(f"Fallback creation error: {str(e)}")
        raise Exception(f"Could not create team from dictionary: {str(e)}")


@app.route('/teams/export/test')
def test_teams_export():
    """Test route to verify team export functionality"""
    try:
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connection', 'test': 'failed'})
        
        teams_list = db.list_teams()
        
        test_result = {
            'test': 'passed',
            'teams_count': len(teams_list),
            'yaml_available': 'yaml' in sys.modules,
            'json_available': 'json' in sys.modules,
            'teams_sample': []
        }
        
        # Test first team if available
        if teams_list:
            team = teams_list[0]
            test_result['teams_sample'] = [{
                'id': team.id,
                'name': team.name,
                'has_to_yaml_dict': hasattr(team, 'to_yaml_dict'),
                'captain': team.captain,
                'league_name': team.league.name if hasattr(team, 'league') and team.league else 'Unknown'
            }]
        
        return jsonify(test_result)
        
    except Exception as e:
        return jsonify({
            'test': 'failed',
            'error': str(e),
            'traceback': traceback.format_exc()
        })


# ==================== MATCH ROUTES ====================

@app.route('/matches')
def matches():
    """View matches with optional league filter and unscheduled match support"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    league_id = request.args.get('league_id', type=int)
    show_unscheduled = request.args.get('show_unscheduled', 'true').lower() == 'true'
    
    try:
        matches_list = db.list_matches(league_id=league_id, include_unscheduled=show_unscheduled)
        leagues_list = db.list_leagues()  # For filter dropdown
        facilities_list = db.list_facilities()  # For filter dropdown
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            selected_league = db.get_league(league_id)
        
        # Enhance matches with team and facility names, plus status
        enhanced_matches = []
        for match in matches_list:
            enhanced_match = {
                'id': match.id,
                'league_id': match.league_id,
                'home_team_id': match.home_team_id,
                'visitor_team_id': match.visitor_team_id,
                'facility_id': match.facility_id,
                'date': match.date,
                'time': match.time,
                'home_team_name': 'Unknown',
                'visitor_team_name': 'Unknown',
                'facility_name': 'Unknown',
                'league_name': 'Unassigned',
                'status': match.get_status(),
                'is_scheduled': match.is_scheduled(),
                'missing_fields': match.get_missing_fields()
            }
            
            try:
                home_team = db.get_team(match.home_team_id)
                if home_team:
                    enhanced_match['home_team_name'] = home_team.name
            except Exception as e:
                print(f"Warning: Could not get home team {match.home_team_id}: {e}")
            
            try:
                visitor_team = db.get_team(match.visitor_team_id)
                if visitor_team:
                    enhanced_match['visitor_team_name'] = visitor_team.name
            except Exception as e:
                print(f"Warning: Could not get visitor team {match.visitor_team_id}: {e}")
            
            if match.facility_id: 
                try:
                    facility = db.get_facility(match.facility_id)
                    if facility:
                        enhanced_match['facility_name'] = facility.name
                except Exception as e:
                    print(f"Warning: Could not get facility {match.facility_id}: {e}")
            
            try:
                if match.league_id:
                    league = db.get_league(match.league_id)
                    if league:
                        enhanced_match['league_name'] = league.name
            except Exception as e:
                print(f"Warning: Could not get league {match.league_id}: {e}")
            
            enhanced_matches.append(enhanced_match)
        
        return render_template('matches.html', 
                             matches=enhanced_matches, 
                             leagues=leagues_list,
                             facilities=facilities_list,
                             selected_league=selected_league,
                             show_unscheduled=show_unscheduled)
    except Exception as e:
        flash(f'Error loading matches: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/matches/<int:match_id>/schedule', methods=['POST'])
def schedule_match(match_id):
    """Schedule an existing unscheduled match using auto-scheduling"""
    print(f"\n=== SCHEDULE MATCH DEBUG START ===")
    print(f"Attempting to schedule match ID: {match_id}")
    
    db = get_db()
    if db is None:
        print("ERROR: No database connection")
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        print(f"Database connection established: {type(db)}")
        
        # Get the match object
        print(f"Retrieving match with ID: {match_id}")
        match = db.get_match(match_id)
        if not match:
            print(f"ERROR: Match {match_id} not found")
            return jsonify({'error': f'Match {match_id} not found'}), 404
        
        print(f"Match found:")
        print(f"  ID: {match.id}")
        print(f"  League ID: {match.league_id}")
        print(f"  Home Team ID: {match.home_team_id}")
        print(f"  Visitor Team ID: {match.visitor_team_id}")
        print(f"  Current facility_id: {match.facility_id}")
        print(f"  Current date: {match.date}")
        print(f"  Current time: {match.time}")
        print(f"  Is scheduled: {match.is_scheduled()}")
        
        # Check if database has auto_schedule_matches method
        print(f"Checking if database has auto_schedule_matches method...")
        if hasattr(db, 'auto_schedule_matches'):
            print("✓ auto_schedule_matches method found")
        else:
            print("✗ auto_schedule_matches method NOT found")
            return jsonify({'error': 'Auto-scheduling not available in this database backend'}), 500
        
        # Use the auto-scheduling method with a list containing the single match
        print(f"Calling auto_schedule_matches with single match...")
        try:
            result = db.auto_schedule_matches([match], dry_run=False)
            print(f"Auto-schedule result: {result}")
        except Exception as auto_error:
            print(f"ERROR in auto_schedule_matches: {auto_error}")
            print(f"Auto-schedule error type: {type(auto_error)}")
            import traceback
            print("Auto-schedule traceback:")
            traceback.print_exc()
            raise auto_error
        
        # Check if the match is now scheduled by querying the database
        print(f"Re-checking match status after scheduling attempt...")
        updated_match = db.get_match(match_id)
        if updated_match:
            print(f"Updated match status:")
            print(f"  facility_id: {updated_match.facility_id}")
            print(f"  date: {updated_match.date}")
            print(f"  time: {updated_match.time}")
            print(f"  is_scheduled: {updated_match.is_scheduled()}")
            
            if updated_match.is_scheduled():
                print("✓ Match successfully scheduled!")
                return jsonify({
                    'success': True,
                    'message': f'Match {match_id} has been automatically scheduled',
                    'details': result
                })
            else:
                print("✗ Match is still unscheduled after attempt")
                return jsonify({
                    'error': 'Could not find suitable scheduling option for this match',
                    'details': result
                }), 400
        else:
            print("ERROR: Could not retrieve updated match")
            return jsonify({'error': 'Could not verify match scheduling status'}), 500
            
    except ValueError as e:
        print(f"ValueError in schedule_match: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Exception in schedule_match: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        return jsonify({'error': f'Failed to auto-schedule match: {e}'}), 500
    finally:
        print("=== SCHEDULE MATCH DEBUG END ===\n")


# Fix for tennis_web_app.py - Update the schedule-all route

@app.route('/matches/schedule-all', methods=['POST'])
def schedule_all_matches():
    """Schedule all unscheduled matches, optionally filtered by league"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        league_id = request.form.get('league_id', type=int)
        dry_run = request.form.get('dry_run', 'false').lower() == 'true'
        
        if league_id:
            # Get all matches in the specific league
            all_matches = db.list_matches(league_id=league_id, include_unscheduled=True)
            unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
            scope = f"league {league_id}"
        else:
            # Get all matches across all leagues
            all_matches = db.list_matches(include_unscheduled=True)
            unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
            scope = "all leagues"
        
        if not unscheduled_matches:
            return jsonify({
                'success': True,
                'message': f'No unscheduled matches found in {scope}',
                'scheduled_count': 0,
                'failed_count': 0,
                'total_count': 0
            })
        
        initial_unscheduled_count = len(unscheduled_matches)
        
        # Use auto-scheduling
        try:
            if league_id:
                # Try league-specific scheduling if the method exists
                result = db.auto_schedule_league_matches(league_id, dry_run=dry_run)
            else:
                # Use general match scheduling
                result = db.auto_schedule_matches(unscheduled_matches, dry_run=dry_run)
        except AttributeError:
            # If auto-scheduling methods don't exist, we can't schedule
            return jsonify({
                'error': 'Auto-scheduling functionality not available in this database backend'
            }), 500
        
        if not dry_run:
            # Re-fetch matches to count how many are now scheduled
            if league_id:
                current_matches = db.list_matches(league_id=league_id, include_unscheduled=True)
            else:
                current_matches = db.list_matches(include_unscheduled=True)
            
            current_unscheduled = [match for match in current_matches if not match.is_scheduled()]
            scheduled_count = initial_unscheduled_count - len(current_unscheduled)
            failed_count = len(current_unscheduled)
        else:
            # For dry run, extract from result if possible
            if isinstance(result, dict):
                scheduled_count = result.get('scheduled_count', 0)
                failed_count = result.get('failed_count', 0)
            else:
                scheduled_count = 0
                failed_count = 0
        
        total_count = initial_unscheduled_count
        
        if dry_run:
            message = f"Dry run completed for {scope}: {scheduled_count} of {total_count} matches could be scheduled"
        else:
            message = f"Scheduled {scheduled_count} of {total_count} matches in {scope}"
            
        if failed_count > 0:
            message += f" ({failed_count} failed)"
        
        return jsonify({
            'success': True,
            'message': message,
            'scheduled_count': scheduled_count,
            'failed_count': failed_count,
            'total_count': total_count,
            'details': result if isinstance(result, dict) else {}
        })
        
    except Exception as e:
        import traceback
        print(f"Error in schedule_all_matches: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to schedule matches: {e}'}), 500


        
@app.route('/matches/<int:match_id>/unschedule', methods=['POST'])
def unschedule_match(match_id):
    """Remove scheduling from a match, making it unscheduled"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        db.unschedule_match(match_id)
        
        return jsonify({
            'success': True,
            'message': f'Match {match_id} has been unscheduled'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to unschedule match: {e}'}), 500

@app.route('/matches/delete-all', methods=['POST'])
def delete_all_matches():
    """Delete all matches - useful for regenerating from pairings"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        # Get confirmation from request
        confirm = request.form.get('confirm', '').lower() == 'true'
        if not confirm:
            return jsonify({'error': 'Confirmation required'}), 400
        
        # Count existing matches
        existing_matches = db.list_matches()
        match_count = len(existing_matches)
        
        # Delete all matches
        for match in existing_matches:
            db.delete_match(match.id)
        
        return jsonify({
            'success': True,
            'deleted_count': match_count,
            'message': f'Deleted {match_count} matches'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to delete matches: {e}'}), 500



# ==================== API ROUTES ====================

@app.route('/api/teams/<int:league_id>')
def api_teams_by_league(league_id):
    """API endpoint to get teams by league"""
    return jsonify([])  # Return empty list for now


# Add utility route for facility migration
@app.route('/admin/migrate-teams', methods=['GET', 'POST'])
def migrate_teams_to_facility_names():
    """Admin route to migrate teams from facility IDs to facility names"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            dry_run = request.form.get('dry_run', 'true').lower() == 'true'
            
            # Perform migration using the team manager's migration method
            if hasattr(db.team_manager, 'migrate_teams_to_facility_names'):
                result = db.team_manager.migrate_teams_to_facility_names(dry_run=dry_run)
                
                if result['status'] == 'no_migration_needed':
                    flash(result['message'], 'info')
                elif dry_run:
                    flash(f"Dry run completed: {result['successful_migrations']} teams would be migrated, {result['failed_migrations']} would fail", 'info')
                else:
                    flash(f"Migration completed: {result['successful_migrations']} teams migrated, {result['failed_migrations']} failed", 'success')
                
                return render_template('admin_migrate_teams.html', migration_result=result)
            else:
                flash('Migration functionality not available', 'error')
                
        except Exception as e:
            flash(f'Error during migration: {e}', 'error')
    
    # GET request - show migration form
    return render_template('admin_migrate_teams.html')


# Add utility route to find teams by facility
@app.route('/api/teams/by-facility/<facility_name>')
def api_teams_by_facility_name(facility_name):
    """API endpoint to get teams by facility name"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        exact_match = request.args.get('exact', 'true').lower() == 'true'
        teams_list = db.team_manager.get_teams_by_facility_name(facility_name, exact_match=exact_match)
        
        teams_data = []
        for team in teams_list:
            teams_data.append({
                'id': team.id,
                'name': team.name,
                'captain': team.captain,
                'home_facility': team.home_facility,
                'league_name': team.league.name,
                'league_id': team.league.id
            })
        
        return jsonify({
            'facility_name': facility_name,
            'exact_match': exact_match,
            'teams_count': len(teams_data),
            'teams': teams_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-matches/<int:league_id>')
def api_generate_matches(league_id):
    """API endpoint to generate matches and return JSON with deterministic ID preservation"""
    db = get_db()
    if db is None:
        return jsonify({'error': 'No database connected'}), 500
    
    try:
        # Get league and teams
        league = db.get_league(league_id)
        if not league:
            return jsonify({'error': f'League with ID {league_id} not found'}), 404
        
        teams = db.list_teams(league_id=league_id)
        if len(teams) < 2:
            return jsonify({'error': f'Need at least 2 teams, found {len(teams)}'}), 400
        
        # Generate matches using League.generate_matches()
        matches = league.generate_matches(teams)
        
        # Process matches with deterministic ID preservation
        created_matches = []
        updated_matches = []
        failed_matches = []
        
        for match in matches:
            try:
                # Check if match already exists with this deterministic ID
                existing_match = db.get_match(match.id)
                
                if existing_match:
                    # Update existing match - preserve deterministic ID
                    db.update_match(match)
                    updated_matches.append({
                        'match_id': match.id,
                        'home_team_id': match.home_team_id,
                        'home_team_name': next(team.name for team in teams if team.id == match.home_team_id),
                        'visitor_team_id': match.visitor_team_id,
                        'visitor_team_name': next(team.name for team in teams if team.id == match.visitor_team_id),
                        'facility_id': match.facility_id,
                        'action': 'updated'
                    })
                else:
                    # Create new match with deterministic ID
                    db.add_match(match)
                    created_matches.append({
                        'match_id': match.id,
                        'home_team_id': match.home_team_id,
                        'home_team_name': next(team.name for team in teams if team.id == match.home_team_id),
                        'visitor_team_id': match.visitor_team_id,
                        'visitor_team_name': next(team.name for team in teams if team.id == match.visitor_team_id),
                        'facility_id': match.facility_id,
                        'action': 'created'
                    })
                    
            except Exception as e:
                failed_matches.append({
                    'match_id': match.id,
                    'error': str(e)
                })
        
        # Format results
        all_matches = created_matches + updated_matches
        
        results = {
            'league': {
                'id': league.id,
                'name': league.name,
                'num_matches': league.num_matches,
                'num_lines_per_match': league.num_lines_per_match
            },
            'teams_count': len(teams),
            'total_matches_processed': len(all_matches),
            'created_count': len(created_matches),
            'updated_count': len(updated_matches),
            'failed_count': len(failed_matches),
            'matches': [
                {
                    'match_id': match['match_id'],
                    'match_number': i + 1,
                    'home_team_id': match['home_team_id'],
                    'home_team_name': match['home_team_name'],
                    'visitor_team_id': match['visitor_team_id'],
                    'visitor_team_name': match['visitor_team_name'],
                    'facility_id': match['facility_id'],
                    'action': match['action']
                }
                for i, match in enumerate(all_matches)
            ],
            'deterministic_ids': True,  # Indicate that IDs are deterministic
            'message': f"Processed {len(all_matches)} matches: {len(created_matches)} created, {len(updated_matches)} updated"
        }
        
        if failed_matches:
            results['failed_matches'] = failed_matches
            results['warning'] = f"{len(failed_matches)} matches failed to process"
        
        return jsonify(results)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {e}'}), 500

# ==================== HELPER FUNCTIONS ====================

def get_usta_constants() -> Dict[str, list]:
    """Get USTA constants from the usta module"""
    from usta import USTA_SECTIONS, USTA_REGIONS, USTA_AGE_GROUPS, USTA_DIVISIONS
    return {
        'sections': USTA_SECTIONS,
        'regions': USTA_REGIONS,
        'age_groups': USTA_AGE_GROUPS,
        'divisions': USTA_DIVISIONS
    }

# ==================== OTHER ROUTES ====================

@app.route('/constants')
def constants():
    """View USTA constants"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        constants_data = get_usta_constants()
        return render_template('constants.html', constants=constants_data)
    except Exception as e:
        flash(f'Error loading constants: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/stats')
def stats():
    """Database statistics page"""
    db = get_db()
    if db is None:
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    try:
        stats_data = {
            'facilities_count': len(db.list_facilities()),
            'leagues_count': len(db.list_leagues()),
            'teams_count': len(db.list_teams()),
            'matches_count': len(db.list_matches()),
            'db_path': str(db_config['connection_params'])
        }
        
        # League breakdown
        leagues_list = db.list_leagues()
        league_stats = []
        for league in leagues_list:
            try:
                teams_in_league = len(db.list_teams(league_id=league.id))
                matches_in_league = len(db.list_matches(league_id=league.id))
                league_stats.append({
                    'league': league,
                    'teams_count': teams_in_league,
                    'matches_count': matches_in_league
                })
            except Exception as e:
                print(f"Warning: Could not get stats for league {league.id}: {e}")
        
        stats_data['league_breakdown'] = league_stats
        
        return render_template('stats.html', stats=stats_data)
    except Exception as e:
        flash(f'Error loading statistics: {e}', 'error')
        return redirect(url_for('index'))


# Add this route to tennis_web_app.py after the existing matches route

@app.route('/schedule')
def schedule():
    """View matches organized by date in a schedule format"""
    print("=== SCHEDULE ROUTE DEBUG START ===")
    
    db = get_db()
    if db is None:
        print("ERROR: No database connection")
        flash('No database connection', 'error')
        return redirect(url_for('index'))
    
    league_id = request.args.get('league_id', type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    print(f"Request parameters:")
    print(f"  - league_id: {league_id} (type: {type(league_id)})")
    print(f"  - start_date: '{start_date}'")
    print(f"  - end_date: '{end_date}'")
    
    try:
        # Get all scheduled matches (only those with dates)
        print("\n--- Getting matches from database ---")
        all_matches = db.list_matches(league_id=league_id, include_unscheduled=False)
        print(f"Retrieved {len(all_matches)} matches from database")
        
        leagues_list = db.list_leagues()  # For filter dropdown
        print(f"Retrieved {len(leagues_list)} leagues for dropdown")
        
        # Filter matches that have dates
        scheduled_matches = [match for match in all_matches if match.date]
        print(f"Filtered to {len(scheduled_matches)} scheduled matches (with dates)")
        
        # Debug: Show first few matches
        if scheduled_matches:
            print("\nFirst few scheduled matches:")
            for i, match in enumerate(scheduled_matches[:3]):
                print(f"  Match {i+1}: ID={match.id}, facility_id={match.facility_id} (type: {type(match.facility_id)})")
                print(f"    home_team_id={match.home_team_id}, visitor_team_id={match.visitor_team_id}")
                print(f"    date={match.date}, time={match.time}")
        
        # Apply date range filter if provided
        if start_date:
            before_filter = len(scheduled_matches)
            scheduled_matches = [match for match in scheduled_matches if match.date >= start_date]
            print(f"After start_date filter: {len(scheduled_matches)} matches (was {before_filter})")
        if end_date:
            before_filter = len(scheduled_matches)
            scheduled_matches = [match for match in scheduled_matches if match.date <= end_date]
            print(f"After end_date filter: {len(scheduled_matches)} matches (was {before_filter})")
        
        # Get selected league info if filtering
        selected_league = None
        if league_id:
            print(f"\n--- Getting league info for ID {league_id} ---")
            selected_league = db.get_league(league_id)
            if selected_league:
                print(f"Selected league: {selected_league.name}")
            else:
                print(f"WARNING: League with ID {league_id} not found")
        
        # Enhance matches with team and facility names
        print(f"\n--- Enhancing {len(scheduled_matches)} matches ---")
        enhanced_matches = []
        
        for i, match in enumerate(scheduled_matches):
            print(f"\nProcessing match {i+1}/{len(scheduled_matches)} (ID: {match.id})")
            print(f"  Raw match data:")
            print(f"    facility_id: {match.facility_id} (type: {type(match.facility_id)})")
            print(f"    home_team_id: {match.home_team_id} (type: {type(match.home_team_id)})")
            print(f"    visitor_team_id: {match.visitor_team_id} (type: {type(match.visitor_team_id)})")
            print(f"    league_id: {match.league_id} (type: {type(match.league_id)})")
            
            enhanced_match = {
                'id': match.id,
                'league_id': match.league_id,
                'home_team_id': match.home_team_id,
                'visitor_team_id': match.visitor_team_id,
                'facility_id': match.facility_id,
                'date': match.date,
                'time': match.time,
                'home_team_name': 'Unknown',
                'visitor_team_name': 'Unknown',
                'facility_name': 'Unknown',
                'league_name': 'Unknown',
                'status': match.get_status()
            }
            
            # Get home team
            try:
                print(f"  Getting home team with ID: {match.home_team_id}")
                home_team = db.get_team(match.home_team_id)
                if home_team:
                    enhanced_match['home_team_name'] = home_team.name
                    print(f"    Home team: {home_team.name}")
                else:
                    print(f"    WARNING: Home team with ID {match.home_team_id} not found")
            except Exception as e:
                print(f"    ERROR getting home team {match.home_team_id}: {e}")
                print(f"    Exception type: {type(e)}")
            
            # Get visitor team
            try:
                print(f"  Getting visitor team with ID: {match.visitor_team_id}")
                visitor_team = db.get_team(match.visitor_team_id)
                if visitor_team:
                    enhanced_match['visitor_team_name'] = visitor_team.name
                    print(f"    Visitor team: {visitor_team.name}")
                else:
                    print(f"    WARNING: Visitor team with ID {match.visitor_team_id} not found")
            except Exception as e:
                print(f"    ERROR getting visitor team {match.visitor_team_id}: {e}")
                print(f"    Exception type: {type(e)}")
            
            # Get facility - use home team's facility if match facility_id is not set
            try:
                print(f"  Getting facility with ID: {match.facility_id}")
                
                facility_id_to_use = match.facility_id
                facility_source = "match"
                
                # If match facility_id is None, try to use home team's facility
                if match.facility_id is None:
                    print(f"    WARNING: facility_id is None - trying to use home team's facility")
                    try:
                        # Get the home team to access its facility
                        if 'home_team_name' not in enhanced_match or enhanced_match['home_team_name'] == 'Unknown':
                            # We need to get the home team if we haven't already
                            home_team = db.get_team(match.home_team_id)
                        else:
                            # We already have the home team from earlier
                            home_team = db.get_team(match.home_team_id)
                        
                        if home_team and hasattr(home_team, 'home_facility') and home_team.home_facility:
                            # If home_facility is a Facility object, get its ID
                            if hasattr(home_team.home_facility, 'id'):
                                facility_id_to_use = home_team.home_facility.id
                                facility_source = "home team facility object"
                                print(f"    Using home team's facility ID: {facility_id_to_use}")
                            # If home_facility is a string, try to find the facility by name
                            elif isinstance(home_team.home_facility, str):
                                facilities = db.list_facilities()
                                for fac in facilities:
                                    if fac.name == home_team.home_facility or (fac.short_name and fac.short_name == home_team.home_facility):
                                        facility_id_to_use = fac.id
                                        facility_source = "home team facility name lookup"
                                        print(f"    Found facility '{fac.name}' by name, using ID: {facility_id_to_use}")
                                        break
                                if facility_id_to_use is None:
                                    print(f"    Could not find facility with name: {home_team.home_facility}")
                        else:
                            print(f"    Home team has no facility assigned")
                    except Exception as e:
                        print(f"    ERROR getting home team's facility: {e}")
                
                # Now try to get the facility
                if facility_id_to_use is None:
                    print(f"    No facility available - using fallback")
                    enhanced_match['facility_name'] = 'No Facility Assigned'
                else:
                    facility = db.get_facility(facility_id_to_use)
                    if facility:
                        enhanced_match['facility_name'] = facility.name
                        if facility_source != "match":
                            enhanced_match['facility_name'] += f" (from {facility_source})"
                        print(f"    Facility: {facility.name} (source: {facility_source})")
                    else:
                        print(f"    WARNING: Facility with ID {facility_id_to_use} not found")
                        enhanced_match['facility_name'] = f'Facility ID {facility_id_to_use} (Not Found)'
                        
            except Exception as e:
                print(f"    ERROR getting facility: {e}")
                print(f"    Exception type: {type(e)}")
                print(f"    This is likely the source of your 'Facility ID must be a positive integer' error!")
                # Don't let this break the whole page
                enhanced_match['facility_name'] = f'Error: {str(e)}'
            
            # Get league
            try:
                if match.league_id:
                    print(f"  Getting league with ID: {match.league_id}")
                    league = db.get_league(match.league_id)
                    if league:
                        enhanced_match['league_name'] = league.name
                        print(f"    League: {league.name}")
                    else:
                        print(f"    WARNING: League with ID {match.league_id} not found")
            except Exception as e:
                print(f"    ERROR getting league {match.league_id}: {e}")
                print(f"    Exception type: {type(e)}")
            
            enhanced_matches.append(enhanced_match)
            print(f"  Enhanced match added successfully")
        
        print(f"\n--- Grouping {len(enhanced_matches)} enhanced matches by date ---")
        
        # Group matches by date
        from collections import defaultdict
        from datetime import datetime
        
        matches_by_date = defaultdict(list)
        for match in enhanced_matches:
            matches_by_date[match['date']].append(match)
        
        print(f"Grouped into {len(matches_by_date)} different dates:")
        for date_str, matches in matches_by_date.items():
            print(f"  {date_str}: {len(matches)} matches")
        
        # Sort matches within each date by time
        for date_key in matches_by_date:
            matches_by_date[date_key].sort(key=lambda x: x['time'] or '00:00')
        
        # Convert to sorted list of (date, day_name, matches) tuples
        schedule_data = []
        for date_str in sorted(matches_by_date.keys()):
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                day_name = date_obj.strftime('%A')  # Full day name
                formatted_date = date_obj.strftime('%B %d, %Y')  # "January 15, 2025"
            except ValueError:
                day_name = 'Unknown'
                formatted_date = date_str
            
            schedule_data.append({
                'date_str': date_str,
                'day_name': day_name,
                'formatted_date': formatted_date,
                'matches': matches_by_date[date_str]
            })
        
        print(f"\nFinal schedule_data contains {len(schedule_data)} date entries")
        print(f"Total enhanced matches: {len(enhanced_matches)}")
        
        print("=== SCHEDULE ROUTE DEBUG END ===\n")
        
        return render_template('schedule.html', 
                             schedule_data=schedule_data,
                             leagues=leagues_list,
                             selected_league=selected_league,
                             start_date=start_date,
                             end_date=end_date,
                             total_matches=len(enhanced_matches))
    
    except Exception as e:
        print(f"\n!!! CRITICAL ERROR in schedule route: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        print("=== SCHEDULE ROUTE DEBUG END (ERROR) ===\n")
        
        flash(f'Error loading schedule: {e}', 'error')
        return redirect(url_for('index'))
        

# ==================== APPLICATION CONTEXT ====================

@app.context_processor
def inject_db_path():
    """Inject database path into all templates"""
    if db_config['backend_class'] is not None:
        return {'db_path': str(db_config['connection_params'])}
    return {'db_path': None}

# ==================== STARTUP FUNCTIONS ====================

def create_app_with_sqlite(db_path: str):
    """Create Flask app configured with SQLite backend"""
    from sqlite_tennis_db import SQLiteTennisDB
    
    if init_db(SQLiteTennisDB, db_path=db_path):
        return app
    else:
        raise RuntimeError(f"Failed to initialize database at {db_path}")

def create_app_with_backend(backend_class: Type[TennisDBInterface], **connection_params):
    """Create Flask app configured with specified backend"""
    if init_db(backend_class, **connection_params):
        return app
    else:
        raise RuntimeError(f"Failed to initialize database with {backend_class.__name__}")

if __name__ == '__main__':
    # Print all registered routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule}")
    
    # Default to SQLite if no backend configured
    if db_config['backend_class'] is None:
        print("No database backend configured. Use connect route to configure database.")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)