from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from typing import Optional, Type, Dict, Any
from werkzeug.utils import secure_filename
import yaml
import json
import tempfile
import os
from datetime import datetime
import traceback
import sys

from usta_facility import Facility, WeeklySchedule, DaySchedule, TimeSlot
from web_database import get_db


def register_routes(app):
    """Register facility-related routes"""

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
