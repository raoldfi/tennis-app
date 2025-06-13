"""
Web routes for tennis match management
Fixed version addressing all identified issues
"""

from typing import Optional, Type, Dict, Any
from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import traceback

from web_database import get_db
from web_utils import enhance_match_for_template, filter_matches


def register_routes(app):
    """Register match-related routes"""

    @app.route('/matches')
    def matches():
        """Matches page - FIXED all parameter and template issues"""
        db = get_db()
        if db is None:
            return redirect(url_for('connect'))
        
        # Get filter parameters - Handle both parameter names for compatibility
        league_id = request.args.get('league_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_query = request.args.get('search', '').strip()
        
        # FIXED: Handle both 'show_unscheduled' (template) and 'include_unscheduled' (backend)
        show_unscheduled = request.args.get('show_unscheduled', 'false').lower() == 'true'
        include_unscheduled = request.args.get('include_unscheduled', 'true').lower() == 'true'
        
        # Use either parameter name - prioritize show_unscheduled since that's what the template uses
        include_unscheduled = show_unscheduled or include_unscheduled
        
        try:
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
                if not selected_league:
                    flash(f'League with ID {league_id} not found', 'warning')
                    return redirect(url_for('matches'))
            
            # Get matches - Pass League object instead of ID
            matches_list = db.list_matches(selected_league, include_unscheduled)
            print(f"Retrieved {len(matches_list)} matches from database")
            
            # Apply additional filters
            if start_date or end_date or search_query:
                matches_list = filter_matches(matches_list, start_date, end_date, search_query)
                print(f"After filtering: {len(matches_list)} matches")
            
            # Enhance matches for template display
            enhanced_matches = []
            for match in matches_list:
                enhanced_match = enhance_match_for_template(match)
                enhanced_matches.append(enhanced_match)
            
            # Get leagues for filter dropdown
            leagues_list = db.list_leagues()
            
            return render_template('matches.html', 
                                 matches=enhanced_matches,
                                 leagues=leagues_list,
                                 selected_league=selected_league,
                                 search_query=search_query,
                                 start_date=start_date,
                                 end_date=end_date,
                                 show_unscheduled=include_unscheduled,
                                 include_unscheduled=include_unscheduled)
            
        except Exception as e:
            print(f"Error in matches route: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading matches: {str(e)}', 'error')
            return render_template('matches.html', 
                                 matches=[],
                                 leagues=[],
                                 selected_league=None,
                                 search_query='',
                                 start_date='',
                                 end_date='',
                                 show_unscheduled=False,
                                 include_unscheduled=True)

    @app.route('/match/<int:match_id>')
    def view_match(match_id):
        """View match details - with proper error handling"""
        db = get_db()
        if not db:
            return redirect(url_for('connect'))
        
        try:
            match = db.get_match(match_id)
            if not match:
                flash('Match not found', 'error')
                return redirect(url_for('matches'))
            
            # All data is directly available from the match object
            return render_template('view_match.html', match=match)
            
        except Exception as e:
            print(f"Error loading match {match_id}: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading match: {str(e)}', 'error')
            return redirect(url_for('matches'))

    @app.route('/matches/<int:match_id>/schedule', methods=['POST'])
    def schedule_match(match_id):
        """Schedule a match - updated to work with scheduled_times"""
        print(f"\\n=== SCHEDULE MATCH DEBUG START ===")
        print(f"Attempting to schedule match ID: {match_id}")
        
        db = get_db()
        if db is None:
            print("ERROR: No database connection")
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get the match object
            match = db.get_match(match_id)
            if not match:
                print("ERROR: Match not found")
                return jsonify({'error': 'Match not found'}), 404
            
            print(f"Found match: {getattr(match, 'id', 'Unknown ID')}")
            
            # Get form data
            facility_id = request.form.get('facility_id', type=int)
            date_str = request.form.get('date', '').strip()
            scheduling_type = request.form.get('scheduling_type', 'all_same_time')
            
            print(f"Form data - Facility ID: {facility_id}, Date: {date_str}, Type: {scheduling_type}")
            
            if not facility_id or not date_str:
                return jsonify({'error': 'Facility and date are required'}), 400
            
            # Get facility
            facility = db.get_facility(facility_id)
            if not facility:
                return jsonify({'error': 'Facility not found'}), 404
            
            print(f"Found facility: {facility.name}")
            
            # Schedule based on type
            if scheduling_type == 'all_same_time':
                time_str = request.form.get('time', '09:00').strip()
                print(f"Scheduling all lines at same time: {time_str}")
                match.schedule_lines_all_same_time(facility, date_str, time_str)
                
            elif scheduling_type == 'sequential':
                start_time = request.form.get('start_time', '09:00').strip()
                interval = int(request.form.get('interval', 180))
                print(f"Scheduling sequential lines starting at {start_time} with {interval} min intervals")
                match.schedule_lines_sequential(facility, date_str, start_time, interval)
                
            elif scheduling_type == 'custom':
                times_input = request.form.get('custom_times', '').strip()
                if not times_input:
                    return jsonify({'error': 'Custom times are required'}), 400
                
                times = [t.strip() for t in times_input.split(',') if t.strip()]
                if len(times) != match.league.num_lines_per_match:
                    return jsonify({
                        'error': f'Must provide exactly {match.league.num_lines_per_match} times'
                    }), 400
                
                print(f"Scheduling custom times: {times}")
                match.schedule_lines_custom_times(facility, date_str, times)
            
            else:
                return jsonify({'error': 'Invalid scheduling type'}), 400
            
            # Update the match in database
            db.update_match(match)
            print("Match updated successfully in database")
            
            return jsonify({
                'success': True,
                'message': f'Match scheduled successfully at {facility.name} on {date_str}',
                'facility': facility.name,
                'date': date_str,
                'times': match.scheduled_times,
                'scheduling_type': scheduling_type
            })
            
        except ValueError as e:
            print(f"ValueError: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Scheduling failed: {str(e)}'}), 500
        finally:
            print("=== SCHEDULE MATCH DEBUG END ===\\n")

    @app.route('/matches/auto-schedule', methods=['POST'])
    def auto_schedule_all():
        """Auto-schedule all unscheduled matches or matches in a specific league"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get scope parameter
            scope = request.form.get('scope', 'all')  # 'all' or 'league'
            league_id = request.form.get('league_id', type=int) if scope == 'league' else None
            
            print(f"Auto-scheduling scope: {scope}, League ID: {league_id}")
            
            # Get matches to schedule
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League with ID {league_id} not found'}), 404
                
                all_matches = db.list_matches(league, include_unscheduled=True)
                scope = f"league '{league.name}'"
            else:
                all_matches = db.list_matches(include_unscheduled=True)
                scope = "all leagues"
            
            # Filter to unscheduled matches
            unscheduled_matches = [match for match in all_matches if not match.is_scheduled()]
            
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
                # Use general match scheduling
                result = db.auto_schedule_matches(unscheduled_matches)
            except AttributeError:
                # If auto-scheduling methods don't exist, we can't schedule
                return jsonify({
                    'error': 'Auto-scheduling functionality not available in this database backend'
                }), 500
            
            # Re-fetch matches to count how many are now scheduled
            if league_id:
                current_matches = db.list_matches(league, include_unscheduled=True)
            else:
                current_matches = db.list_matches(include_unscheduled=True)
            
            current_unscheduled = [match for match in current_matches if not match.is_scheduled()]
            scheduled_count = initial_unscheduled_count - len(current_unscheduled)
            failed_count = len(current_unscheduled)
            
            total_count = initial_unscheduled_count
            
            message = f"Scheduled {scheduled_count} of {total_count} matches in {scope}"
                
            if failed_count > 0:
                message += f" ({failed_count} failed)"
            
            return jsonify({
                'success': True,
                'message': message,
                'scheduled_count': scheduled_count,
                'failed_count': failed_count,
                'total_count': total_count,
                'details': result.get('scheduling_details', [])
            })
            
        except Exception as e:
            print(f"Auto-schedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Auto-scheduling failed: {str(e)}'}), 500

    @app.route('/schedule')
    def schedule():
        """Schedule page - displays scheduled matches grouped by date"""
        db = get_db()
        if db is None:
            return redirect(url_for('connect'))
        
        # Get filter parameters
        league_id = request.args.get('league_id', type=int)
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        search_query = request.args.get('search', '').strip()
        
        try:
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
            
            # Get ALL matches
            all_matches = db.list_matches(selected_league, include_unscheduled=True)
            
            # FIXED: More flexible filtering - matches with facility and date are considered "scheduled"
            # Don't require times since some matches might have location/date but no specific times yet
            scheduled_matches = []
            for match in all_matches:
                # Check if match has the essential scheduling information
                has_facility = hasattr(match, 'facility') and match.facility is not None
                has_date = hasattr(match, 'date') and match.date is not None
                
                # Only require facility and date - times can be optional for display
                if has_facility and has_date:
                    scheduled_matches.append(match)
            
            print(f"Found {len(scheduled_matches)} scheduled matches out of {len(all_matches)} total matches")
            
            # Apply date range filters
            if start_date:
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    scheduled_matches = [m for m in scheduled_matches 
                                       if convert_to_date(m.date) >= start_date_obj]
                except ValueError:
                    print(f"Invalid start_date format: {start_date}")
            
            if end_date:
                try:
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    scheduled_matches = [m for m in scheduled_matches 
                                       if convert_to_date(m.date) <= end_date_obj]
                except ValueError:
                    print(f"Invalid end_date format: {end_date}")
            
            # Apply search filter
            if search_query:
                scheduled_matches = search_matches(scheduled_matches, search_query)
            
            # Group matches by date
            schedule_data = build_schedule_data(scheduled_matches)
            
            # Calculate total matches for template
            total_matches = len(scheduled_matches)
            
            # SOLUTION 3: Calculate total_lines in Python before template rendering
            total_lines = 0
            for match in scheduled_matches:
                if hasattr(match, 'num_scheduled_lines') and match.num_scheduled_lines is not None:
                    # Handle both integer and potential list cases
                    if isinstance(match.num_scheduled_lines, (int, float)):
                        total_lines += int(match.num_scheduled_lines)
                    elif isinstance(match.num_scheduled_lines, list):
                        total_lines += len(match.num_scheduled_lines)
                    else:
                        print(f"Warning: Unexpected num_scheduled_lines type for match {match.id}: {type(match.num_scheduled_lines)}")
            
            # Convert schedule_data to list format expected by template
            schedule_data_list = []
            for date_str, day_data in schedule_data.items():
                day_data_formatted = {
                    'date': day_data['date'],
                    'date_str': date_str,
                    'day_name': day_data['date'].strftime('%A'),
                    'formatted_date': day_data['date'].strftime('%A, %B %d, %Y'),
                    'matches': day_data['matches']
                }
                schedule_data_list.append(day_data_formatted)
            
            # Get leagues for filter dropdown
            leagues_list = db.list_leagues()
            
            return render_template('schedule.html',
                                 schedule_data=schedule_data_list,
                                 total_matches=total_matches,
                                 total_lines=total_lines,  # Add total_lines to template context
                                 leagues=leagues_list,
                                 selected_league=selected_league,
                                 search_query=search_query,
                                 start_date=start_date,
                                 end_date=end_date)
                                 
        except Exception as e:
            print(f"Error in schedule route: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading schedule: {str(e)}', 'error')
            return redirect(url_for('matches'))


def convert_to_date(date_value):
    """Helper function to convert various date formats to date object"""
    if date_value is None:
        return None
    
    # If it's already a date or datetime object
    if hasattr(date_value, 'date'):
        if callable(date_value.date):
            return date_value.date()  # datetime object
        else:
            return date_value  # date object
    
    # If it's a string, try to parse it
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(date_value, '%m/%d/%Y').date()
            except ValueError:
                print(f"Could not parse date: {date_value}")
                return None
    
    return None


def search_matches(matches, search_query):
    """Search matches by various fields"""
    if not search_query:
        return matches
    
    search_terms = [term.lower().strip() for term in search_query.split() if term.strip()]
    filtered_matches = []
    
    for match in matches:
        # Build searchable text
        searchable_parts = []
        
        # Team names
        if hasattr(match, 'home_team') and match.home_team:
            searchable_parts.append(match.home_team.name.lower())
        if hasattr(match, 'visitor_team') and match.visitor_team:
            searchable_parts.append(match.visitor_team.name.lower())
        
        # Facility name
        if hasattr(match, 'facility') and match.facility:
            searchable_parts.append(match.facility.name.lower())
        
        # League name
        if hasattr(match, 'league') and match.league:
            searchable_parts.append(match.league.name.lower())
        
        # Date
        if hasattr(match, 'date') and match.date:
            searchable_parts.append(str(match.date).lower())
        
        # Times
        if hasattr(match, 'scheduled_times') and match.scheduled_times:
            searchable_parts.extend([time.lower() for time in match.scheduled_times])
        
        # Match ID
        searchable_parts.append(str(match.id))
        
        # Check if all search terms are found
        searchable_text = ' '.join(searchable_parts)
        if all(term in searchable_text for term in search_terms):
            filtered_matches.append(match)
    
    return filtered_matches


def build_schedule_data(matches):
    """Group matches by date for schedule display"""
    schedule_data = {}
    
    for match in matches:
        try:
            date_obj = convert_to_date(match.date)
            if date_obj:
                date_str = date_obj.strftime('%Y-%m-%d')
                if date_str not in schedule_data:
                    schedule_data[date_str] = {
                        'date': date_obj,
                        'matches': []
                    }
                
                # Enhance match for template
                enhanced_match = enhance_match_for_template(match)
                schedule_data[date_str]['matches'].append(enhanced_match)
        except Exception as e:
            print(f"Error processing match {match.id} for schedule: {str(e)}")
    
    # Sort by date
    sorted_schedule = dict(sorted(schedule_data.items()))
    
    return sorted_schedule