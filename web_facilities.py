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
            # Add current date to template context
            today = datetime.now().strftime('%Y-%m-%d')
            return render_template('facilities.html', facilities=facilities_list, today=today)
        except Exception as e:
            flash(f'Error loading facilities: {e}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/facilities/<int:facility_id>')
    def view_facility(facility_id):
        """View detailed facility information including schedule and utilization"""
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            facility = db.get_facility(facility_id)
            if not facility:
                flash(f'Facility with ID {facility_id} not found', 'error')
                return redirect(url_for('facilities'))
            
            # Calculate utilization data for all leagues using this facility
            utilization_data = {}
            try:
                # Get all leagues that have teams using this facility
                leagues = db.list_leagues()
                for league in leagues:
                    teams = db.list_teams(league)
                    # Check if any teams in this league use this facility
                    facility_teams = [team for team in teams if team.home_facility.id == facility_id]
                    if facility_teams:
                        # Create the facilities_used list in the correct format
                        facilities_used = [{
                            "facility_id": facility_id,
                            "facility_name": facility.name,
                            "total_courts": facility.total_courts
                        }]
                        # Calculate utilization for this league
                        league_utilization = db.facility_manager._calculate_current_utilization(
                            league, facilities_used
                        )
                        if league_utilization and str(facility_id) in league_utilization:
                            utilization_data[league.id] = {
                                "league_name": league.name,
                                "league_id": league.id,
                                "utilization": league_utilization[str(facility_id)]
                            }
            except Exception as util_error:
                print(f"Error calculating utilization: {util_error}")
                import traceback
                traceback.print_exc()
                # Continue without utilization data if there's an error
                utilization_data = {}
            
            return render_template('view_facility.html', facility=facility, utilization_data=utilization_data)
            
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
                short_name = request.form.get('short_name', '').strip()
                location = request.form.get('location', '').strip()
                total_courts = int(request.form.get('total_courts', 0))
                
                if not name:
                    flash('Facility name is required', 'error')
                    return render_template('facility_form.html')
                
                # Create facility with basic info
                facility = Facility(
                    id=facility_id, 
                    name=name,
                    short_name=short_name if short_name else None,
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
            
            return render_template('facility_form.html')
        
        # GET request - show the form
        return render_template('facility_form.html')
    
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
                short_name = request.form.get('short_name', '').strip()
                location = request.form.get('location', '').strip()
                total_courts = int(request.form.get('total_courts', 0))
                
                if not name:
                    flash('Facility name is required', 'error')
                    return render_template('facility_form.html', facility=facility)
                
                # Update facility with basic info
                facility.name = name
                facility.short_name = short_name if short_name else None
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
            
            return render_template('facility_form.html', facility=facility)
        
        # GET request - show the form with existing data
        return render_template('facility_form.html', facility=facility)
    
    # ==================== FACILITY IMPORT/EXPORT ROUTES ====================
    


# ========= Helper Functions ==============

