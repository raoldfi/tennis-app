from flask import render_template, jsonify, request, redirect, url_for, flash
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import calendar

def register_routes(app):
    """Register court utilization calendar routes"""
    
    @app.route('/facilities/<int:facility_id>/utilization')
    def facility_utilization_calendar(facility_id: int):
        """Display utilization calendar for a specific facility"""
        from web_database import get_db
        
        db = get_db()
        if db is None:
            flash('No database connection', 'error')
            return redirect(url_for('index'))
        
        try:
            facility = db.facility_manager.get_facility(facility_id)
            if not facility:
                flash(f'Facility with ID {facility_id} not found', 'error')
                return redirect(url_for('facilities'))
            
            # Get current month/year or from query params
            month = request.args.get('month', type=int)
            year = request.args.get('year', type=int)
            
            if not month or not year:
                today = datetime.now()
                month = today.month
                year = today.year
            
            return render_template('facility_utilization.html', 
                                 facility=facility,
                                 current_month=month,
                                 current_year=year)
            
        except Exception as e:
            flash(f'Error loading utilization calendar: {e}', 'error')
            return redirect(url_for('view_facility', facility_id=facility_id))
    
    @app.route('/api/facilities/<int:facility_id>/utilization')
    def get_facility_utilization(facility_id: int):
        """Get utilization data for a specific facility and date range"""
        from web_database import get_db
        
        print(f"\n=== DEBUG: get_facility_utilization called ===")
        print(f"Facility ID: {facility_id}")
        print(f"Request args: {request.args}")
        
        try:
            db = get_db()
            if db is None:
                return jsonify({'success': False, 'error': 'No database connection'})
            
            # Get facility
            facility = db.facility_manager.get_facility(facility_id)
            if not facility:
                return jsonify({'success': False, 'error': 'Facility not found'})
            
            # Get date range from query params
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not start_date or not end_date:
                # Default to current month
                today = datetime.now()
                start_date = datetime(today.year, today.month, 1).strftime('%Y-%m-%d')
                
                # Get last day of month
                if today.month == 12:
                    end_date = datetime(today.year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
                end_date = end_date.strftime('%Y-%m-%d')
            
            # Generate list of dates
            dates = []
            current = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            while current <= end:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            
            # Get facility availability for all dates
            availability_list = db.facility_manager.get_facility_availability(
                facility=facility,
                dates=dates,
                max_days=len(dates)
            )
            
            # Convert to dictionary for easy lookup
            availability_by_date = {
                info.date: info for info in availability_list
            }
            
            # Build utilization data
            utilization_data = []
            for date in dates:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                
                if date in availability_by_date:
                    info = availability_by_date[date]
                    
                    # Calculate matches scheduled
                    matches_scheduled = 0
                    total_courts_used = 0
                    
                    if info.available and info.time_slots:
                        for slot in info.time_slots:
                            if slot.used_courts > 0:
                                matches_scheduled += 1
                                total_courts_used += slot.used_courts
                    
                    utilization_data.append({
                        'date': date,
                        'day': date_obj.day,
                        'day_of_week': date_obj.strftime('%A'),
                        'is_available': info.available,
                        'reason': info.reason if not info.available else None,
                        'total_court_slots': info.total_court_slots,
                        'used_court_slots': info.used_court_slots,
                        'available_court_slots': info.available_court_slots,
                        'utilization_percentage': info.overall_utilization_percentage,
                        'matches_scheduled': matches_scheduled,
                        'time_slots': [
                            {
                                'time': slot.time,
                                'total_courts': slot.total_courts,
                                'used_courts': slot.used_courts,
                                'available_courts': slot.available_courts,
                                'utilization_percentage': slot.utilization_percentage
                            }
                            for slot in info.time_slots
                        ] if info.time_slots else []
                    })
                else:
                    # No data for this date
                    utilization_data.append({
                        'date': date,
                        'day': date_obj.day,
                        'day_of_week': date_obj.strftime('%A'),
                        'is_available': False,
                        'reason': 'No schedule data',
                        'total_court_slots': 0,
                        'used_court_slots': 0,
                        'available_court_slots': 0,
                        'utilization_percentage': 0,
                        'matches_scheduled': 0,
                        'time_slots': []
                    })
            
            # Calculate summary statistics
            total_available_slots = sum(d['total_court_slots'] for d in utilization_data)
            total_used_slots = sum(d['used_court_slots'] for d in utilization_data)
            overall_utilization = (total_used_slots / total_available_slots * 100) if total_available_slots > 0 else 0
            
            return jsonify({
                'success': True,
                'facility': {
                    'id': facility.id,
                    'name': facility.name,
                    'total_courts': facility.total_courts
                },
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'summary': {
                    'total_days': len(dates),
                    'available_days': sum(1 for d in utilization_data if d['is_available']),
                    'total_court_slots': total_available_slots,
                    'used_court_slots': total_used_slots,
                    'available_court_slots': total_available_slots - total_used_slots,
                    'overall_utilization_percentage': round(overall_utilization, 1),
                    'total_matches': sum(d['matches_scheduled'] for d in utilization_data)
                },
                'utilization_data': utilization_data
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    
    @app.route('/api/facilities/<int:facility_id>/utilization/monthly')
    def get_monthly_utilization(facility_id: int):
        """Get utilization data formatted for monthly calendar view"""
        from web_database import get_db
        
        print(f"\n=== DEBUG: get_monthly_utilization called ===")
        print(f"Facility ID: {facility_id}")
        print(f"Request args: {request.args}")

        try:
            db = get_db()
            if db is None:
                return jsonify({'success': False, 'error': 'No database connection'})
            
            # Get month and year from query params
            month = request.args.get('month', type=int)
            year = request.args.get('year', type=int)
            
            if not month or not year:
                today = datetime.now()
                month = today.month
                year = today.year
            
            # Validate month/year
            if month < 1 or month > 12:
                return jsonify({'success': False, 'error': 'Invalid month'})
            
            # Get facility
            facility = db.facility_manager.get_facility(facility_id)
            if not facility:
                return jsonify({'success': False, 'error': 'Facility not found'})
            
            # Get first and last day of month
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
            
            # Generate all dates for the month
            dates = []
            current = first_day
            while current <= last_day:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
            
            # Get facility availability
            availability_list = db.facility_manager.get_facility_availability(
                facility=facility,
                dates=dates,
                max_days=len(dates)
            )
            
            # Convert to dictionary
            availability_by_date = {
                info.date: info for info in availability_list
            }
            
            # Build calendar data
            cal = calendar.monthcalendar(year, month)
            calendar_data = []
            
            for week in cal:
                week_data = []
                for day in week:
                    if day == 0:
                        # Empty cell for days outside the month
                        week_data.append(None)
                    else:
                        date = datetime(year, month, day).strftime('%Y-%m-%d')
                        
                        if date in availability_by_date:
                            info = availability_by_date[date]
                            
                            # Count matches scheduled
                            matches_scheduled = 0
                            if info.available and info.time_slots:
                                for slot in info.time_slots:
                                    if slot.used_courts > 0:
                                        matches_scheduled += 1
                            
                            week_data.append({
                                'day': day,
                                'date': date,
                                'is_available': info.available,
                                'courts_available': info.available_court_slots,
                                'courts_used': info.used_court_slots,
                                'total_courts': info.total_court_slots,
                                'utilization': info.overall_utilization_percentage,
                                'matches': matches_scheduled,
                                'is_blackout': not info.available and info.reason == 'Blackout date'
                            })
                        else:
                            week_data.append({
                                'day': day,
                                'date': date,
                                'is_available': False,
                                'courts_available': 0,
                                'courts_used': 0,
                                'total_courts': 0,
                                'utilization': 0,
                                'matches': 0,
                                'is_blackout': False
                            })
                
                calendar_data.append(week_data)
            
            # Calculate month summary
            month_data = [d for week in calendar_data for d in week if d is not None]
            total_available_slots = sum(d['total_courts'] for d in month_data)
            total_used_slots = sum(d['courts_used'] for d in month_data)
            overall_utilization = (total_used_slots / total_available_slots * 100) if total_available_slots > 0 else 0
            
            return jsonify({
                'success': True,
                'facility': {
                    'id': facility.id,
                    'name': facility.name,
                    'total_courts': facility.total_courts
                },
                'month_info': {
                    'year': year,
                    'month': month,
                    'month_name': calendar.month_name[month],
                    'first_day': first_day.strftime('%Y-%m-%d'),
                    'last_day': last_day.strftime('%Y-%m-%d'),
                    'weekday_names': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
                },
                'summary': {
                    'total_days': len(month_data),
                    'available_days': sum(1 for d in month_data if d['is_available']),
                    'blackout_days': sum(1 for d in month_data if d['is_blackout']),
                    'total_court_slots': total_available_slots,
                    'used_court_slots': total_used_slots,
                    'overall_utilization': round(overall_utilization, 1),
                    'total_matches': sum(d['matches'] for d in month_data)
                },
                'calendar_data': calendar_data
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})