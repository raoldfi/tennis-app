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
            
            # Calculate comprehensive facility statistics using the unified method
            facility_stats = {}
            utilization_data = {}
            total_utilization = {
                "total_court_time_slots": 0,
                "current_usage": 0,
                "utilization_percentage": 0.0
            }
            per_day_utilization = {day: 0.0 for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
            comprehensive_stats = {}
            
            try:
                # Use the new unified facility_statistics method for comprehensive data
                facility_stats = db.facility_manager.facility_statistics(
                    facility=facility,
                    league=None,  # Get stats for all leagues
                    include_league_breakdown=True,
                    include_per_day_utilization=True,
                    include_peak_demand=True,
                    include_requirements=False
                )
                
                # Extract total utilization from the unified stats
                total_utilization = {
                    "total_court_time_slots": facility_stats.get("total_available_slots", 0),
                    "current_usage": facility_stats.get("total_time_slots_used", 0),
                    "utilization_percentage": facility_stats.get("total_utilization", 0.0)
                }
                
                # Extract per-day utilization
                if "per_day_utilization" in facility_stats:
                    per_day_utilization = facility_stats["per_day_utilization"]
                
                # Extract league breakdown for individual league utilization
                if "league_breakdown" in facility_stats:
                    for league_id, league_data in facility_stats["league_breakdown"].items():
                        utilization_data[int(league_id)] = {
                            "league_name": league_data["league_name"],
                            "league_id": int(league_id),
                            "utilization": {
                                "facility_name": facility.name,
                                "total_court_time_slots": league_data.get("total_available_slots", 0),
                                "current_usage": league_data.get("slots_used", 0),
                                "utilization_percentage": league_data.get("utilization_percentage", 0.0)
                            }
                        }
                
                # Prepare comprehensive stats for detailed display
                comprehensive_stats = {
                    "core_metrics": {
                        "total_scheduled_matches": facility_stats.get("total_scheduled_matches", 0),
                        "total_court_hours_used": facility_stats.get("total_court_hours_used", 0),
                        "unique_dates_with_matches": facility_stats.get("unique_dates_with_matches", 0),
                        "active_leagues": facility_stats.get("active_leagues", 0),
                        "analysis_period": facility_stats.get("analysis_period", {})
                    },
                    "peak_demand": facility_stats.get("peak_demand", {}),
                    "league_breakdown": facility_stats.get("league_breakdown", {}),
                    "message": facility_stats.get("message", "")
                }
                
                # Get additional statistics for teams using this facility
                teams = db.list_teams()
                teams_using_facility = [
                    team for team in teams 
                    if team.preferred_facilities and facility in team.preferred_facilities
                ]
                comprehensive_stats["teams_using_facility"] = teams_using_facility
                
                # Calculate status based on utilization
                utilization_pct = total_utilization.get("utilization_percentage", 0)
                if utilization_pct > 80:
                    status = "HIGH USAGE"
                    status_class = "danger"
                elif utilization_pct > 50:
                    status = "MODERATE USAGE"
                    status_class = "warning"
                elif utilization_pct > 0:
                    status = "LOW USAGE"
                    status_class = "success"
                else:
                    status = "UNUSED"
                    status_class = "secondary"
                
                comprehensive_stats["status"] = {
                    "label": status,
                    "class": status_class
                }
                
            except Exception as util_error:
                print(f"Error calculating facility statistics: {util_error}")
                import traceback
                traceback.print_exc()
                # Continue with default values if there's an error
                comprehensive_stats = {
                    "core_metrics": {},
                    "peak_demand": {},
                    "league_breakdown": {},
                    "teams_using_facility": [],
                    "message": f"Error calculating statistics: {util_error}",
                    "status": {"label": "ERROR", "class": "danger"}
                }
            
            return render_template('view_facility.html', 
                                 facility=facility, 
                                 utilization_data=utilization_data, 
                                 total_utilization=total_utilization,
                                 per_day_utilization=per_day_utilization,
                                 comprehensive_stats=comprehensive_stats)
            
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

