"""
Refactored web_matches.py - Uses Match.is_scheduled() method consistently
Removes redundant status calculation logic and consolidates search functionality
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, date, timedelta
import traceback
import json

from usta import Match, MatchType, League


def register_routes(app, get_db):
    """Register match-related routes with Flask app"""
    
    @app.route('/matches')
    def matches():
        """Display matches with filtering and search"""
        db = get_db()
        if not db:
            return redirect(url_for('connect'))
        
        try:
            # Get filter parameters
            league_id = request.args.get('league_id', type=int)
            match_type_str = request.args.get('match_type', 'all')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            search_query = request.args.get('search', '').strip()
            show_scheduled = request.args.get('show_scheduled', 'true') == 'true'
            show_unscheduled = request.args.get('show_unscheduled', 'true') == 'true'

            
            # FIX 1: Convert league_id to League object
            league = None
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    flash(f'League with ID {league_id} not found', 'error')
                    league_id = None  # Reset to show all matches
            
            # FIXED: Convert match_type string to MatchType enum using from_string()
            try:
                match_type = MatchType.from_string(match_type_str)
            except ValueError as e:
                print(f"Invalid match_type '{match_type_str}': {e}")
                flash(f'Invalid match type: {match_type_str}', 'error')
                match_type = MatchType.ALL  # Default to ALL if invalid
            
            # FIXED: Get matches with proper parameters
            matches_list = db.list_matches(
                league=league,     # ✅ Pass League object, not league_id
                match_type=match_type  # ✅ Pass MatchType enum, not string
            )
            
            # Apply filters
            filtered_matches = filter_matches(matches_list, start_date, end_date, search_query)
            
            # Apply scheduling filters
            if not show_scheduled:
                filtered_matches = [m for m in filtered_matches if not m.is_scheduled()]
            if not show_unscheduled:
                filtered_matches = [m for m in filtered_matches if m.is_scheduled()]
            
            # Convert to display format
            matches_display = [convert_match_to_display(match) for match in filtered_matches]
            
            # Get leagues for filter dropdown
            leagues = db.list_leagues()
            selected_league = db.get_league(league_id) if league_id else None
            
            return render_template('matches.html',
                                 matches=matches_display,
                                 leagues=leagues,
                                 selected_league=selected_league,
                                 match_type=str(match_type),
                                 start_date=start_date,
                                 end_date=end_date,
                                 search_query=search_query,
                                 show_scheduled=show_scheduled,
                                 show_unscheduled=show_unscheduled)
        
        except Exception as e:
            print(f"Error in matches route: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading matches: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
    
    @app.route('/match/<int:match_id>')
    def view_match(match_id):
        """View match details"""
        db = get_db()
        if not db:
            return redirect(url_for('connect'))
        
        try:
            match = db.get_match(match_id)
            if not match:
                flash('Match not found', 'error')
                return redirect(url_for('matches'))
            
            return render_template('view_match.html', match=match)
            
        except Exception as e:
            print(f"Error loading match {match_id}: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading match: {str(e)}', 'error')
            return redirect(url_for('matches'))

    @app.route('/matches/<int:match_id>/schedule', methods=['POST'])
    def schedule_match(match_id):
        """Schedule a match"""
        print(f"\n=== SCHEDULE MATCH {match_id} ===")
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            data = request.get_json()
            facility_id = data.get('facility_id')
            date_str = data.get('date')
            times = data.get('times', [])
            
            if not facility_id or not date_str:
                return jsonify({'error': 'Facility and date are required'}), 400
            
            # Get match and facility
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            facility = db.get_facility(facility_id)
            if not facility:
                return jsonify({'error': 'Facility not found'}), 404
            
            # Schedule the match
            if times:
                # Schedule with specific times
                for time in times:
                    match.add_scheduled_time(time)
                match.facility = facility
                match.date = date_str
            else:
                # Just set facility and date (partial scheduling)
                match.facility = facility
                match.date = date_str
            
            # Update in database
            db.update_match(match)
            
            # Return updated status using Match methods
            return jsonify({
                'success': True,
                'message': 'Match scheduled successfully',
                'is_scheduled': match.is_scheduled(),
                'is_fully_scheduled': match.is_fully_scheduled(),
                'status': match.get_status()
            })
            
        except Exception as e:
            print(f"Schedule match error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Scheduling failed: {str(e)}'}), 500

    @app.route('/matches/<int:match_id>/unschedule', methods=['POST'])
    def unschedule_match(match_id):
        """Unschedule a match (remove facility, date, and all times)"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            # Unschedule the match using the Match class method
            match.unschedule()
            
            # Update in database
            db.update_match(match)
            
            return jsonify({
                'success': True,
                'message': 'Match unscheduled successfully',
                'is_scheduled': match.is_scheduled(),
                'status': match.get_status()
            })
            
        except Exception as e:
            print(f"Unschedule match error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Unscheduling failed: {str(e)}'}), 500

    @app.route('/matches/auto-schedule', methods=['POST'])
    def auto_schedule_matches():
        """Auto-schedule matches using intelligent algorithm"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            data = request.get_json()
            league_id = data.get('league_id')
            facility_id = data.get('facility_id')
            
            # Determine scope
            if league_id:
                matches_to_schedule = [m for m in db.list_matches(league_id=league_id) 
                                     if not m.is_scheduled()]
                scope_description = f"league {league_id}"
            elif facility_id:
                all_matches = db.list_matches()
                matches_to_schedule = [m for m in all_matches 
                                     if not m.is_scheduled() and 
                                     (not m.facility or m.facility.id == facility_id)]
                scope_description = f"facility {facility_id}"
            else:
                matches_to_schedule = [m for m in db.list_matches() if not m.is_scheduled()]
                scope_description = "all matches"
            
            if not matches_to_schedule:
                return jsonify({
                    'success': True,
                    'message': f'No unscheduled matches found for {scope_description}',
                    'scheduled_count': 0,
                    'failed_count': 0,
                    'total_count': 0
                })
            
            initial_unscheduled_count = len(matches_to_schedule)
            
            # Use database auto-scheduling if available
            if hasattr(db, 'auto_schedule_matches'):
                scheduling_results = db.auto_schedule_matches(
                    league_id=league_id,
                    facility_id=facility_id
                )
            else:
                # Fallback: basic scheduling logic
                scheduled_count = 0
                failed_count = 0
                
                for match in matches_to_schedule:
                    try:
                        # Simple auto-scheduling: use home team facility if available
                        if match.home_team and match.home_team.home_facility:
                            match.facility = match.home_team.home_facility
                            match.date = "2025-07-01"  # Default date
                            match.add_scheduled_time("09:00")
                            db.update_match(match)
                            scheduled_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        print(f"Failed to schedule match {match.id}: {e}")
                        failed_count += 1
                
                scheduling_results = {
                    'scheduled_matches': [{'match_id': m.id} for m in matches_to_schedule[:scheduled_count]],
                    'failed_matches': [{'match_id': m.id, 'error': 'No facility available'} 
                                     for m in matches_to_schedule[scheduled_count:]],
                    'scheduling_details': []
                }
            
            final_scheduled_count = len(scheduling_results.get('scheduled_matches', []))
            final_failed_count = len(scheduling_results.get('failed_matches', []))
            
            response_data = {
                'success': True,
                'message': f'Auto-scheduling completed for {scope_description}',
                'scheduled_count': final_scheduled_count,
                'failed_count': final_failed_count,
                'total_count': initial_unscheduled_count
            }
            
            if scheduling_results.get('failed_matches'):
                response_data['failed_matches'] = scheduling_results['failed_matches']
                response_data['message'] += f' ({final_failed_count} failed)'
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f"Auto-schedule route error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Auto-scheduling failed: {str(e)}'}), 500


def convert_match_to_display(match):
    """Convert a Match object to display format using Match class methods"""
    try:
        return {
            'id': match.id,
            'home_team_name': match.home_team.name if match.home_team else 'Unknown',
            'visitor_team_name': match.visitor_team.name if match.visitor_team else 'Unknown',
            'home_team_captain': match.home_team.captain if match.home_team else 'Unknown',
            'visitor_team_captain': match.visitor_team.captain if match.visitor_team else 'Unknown',
            'facility_name': match.facility.name if match.facility else 'Unscheduled',
            'facility_id': match.facility.id if match.facility else None,
            'league_name': match.league.name if match.league else 'Unknown',
            'league_id': match.league.id if match.league else None,
            'league_division': match.league.division if match.league else 'Unknown',
            'league_year': match.league.year if match.league else None,
            'date': match.date,
            'scheduled_times': match.scheduled_times,
            'times_display': ', '.join(match.scheduled_times) if match.scheduled_times else 'No times',
            'num_scheduled_lines': match.get_num_scheduled_lines(),
            'expected_lines': match.get_expected_lines(),
            
            # Use Match class methods for status
            'is_scheduled': match.is_scheduled(),
            'is_unscheduled': match.is_unscheduled(),
            'is_partially_scheduled': match.is_partially_scheduled(),
            'is_fully_scheduled': match.is_fully_scheduled(),
            'status': match.get_status()
        }
    except Exception as e:
        print(f"Error converting match {match.id}: {e}")
        return {
            'id': match.id,
            'home_team_name': 'Error loading',
            'visitor_team_name': 'Error loading',
            'facility_name': 'Error loading',
            'league_name': 'Error loading',
            'is_scheduled': False,
            'status': 'error'
        }


def filter_matches(matches_list, start_date, end_date, search_query):
    """Filter matches based on date range and search query"""
    filtered_matches = matches_list
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            filtered_matches = [m for m in filtered_matches 
                              if m.date and parse_match_date(m.date) >= start_date_obj]
        except ValueError:
            pass  # Invalid date format, skip filter
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            filtered_matches = [m for m in filtered_matches 
                              if m.date and parse_match_date(m.date) <= end_date_obj]
        except ValueError:
            pass  # Invalid date format, skip filter
    
    # Apply search filter
    if search_query:
        filtered_matches = search_matches(filtered_matches, search_query)
    
    return filtered_matches


def parse_match_date(match_date):
    """Parse match date consistently, handling different formats"""
    if isinstance(match_date, str):
        try:
            return datetime.strptime(match_date, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(match_date, '%m/%d/%Y').date()
            except ValueError:
                return None
    elif hasattr(match_date, 'date'):
        return match_date.date()
    else:
        return match_date


def search_matches(matches_list, search_query):
    """
    Unified search functionality with field-specific matching
    Supports queries like: home:lightning facility:club date:2025-01 status:scheduled
    """
    if not search_query:
        return matches_list
    
    # Parse field-specific search terms
    field_searches = {}
    general_terms = []
    
    # Split by spaces and look for field:value patterns
    terms = search_query.split()
    for term in terms:
        if ':' in term and len(term.split(':', 1)) == 2:
            field, value = term.split(':', 1)
            field = field.lower().strip()
            value = value.lower().strip()
            if field and value:
                if field not in field_searches:
                    field_searches[field] = []
                field_searches[field].append(value)
        else:
            general_terms.append(term.lower().strip())
    
    filtered_matches = []
    
    for match in matches_list:
        matches_query = True
        
        # Check field-specific searches
        for field, values in field_searches.items():
            field_match = False
            
            for value in values:
                if field in ['home', 'home_team']:
                    if match.home_team and value in match.home_team.name.lower():
                        field_match = True
                        break
                elif field in ['visitor', 'visitor_team', 'away']:
                    if match.visitor_team and value in match.visitor_team.name.lower():
                        field_match = True
                        break
                elif field in ['team', 'teams']:
                    home_match = match.home_team and value in match.home_team.name.lower()
                    visitor_match = match.visitor_team and value in match.visitor_team.name.lower()
                    if home_match or visitor_match:
                        field_match = True
                        break
                elif field in ['facility', 'venue']:
                    if match.facility and value in match.facility.name.lower():
                        field_match = True
                        break
                elif field in ['league', 'lg']:
                    if match.league and value in match.league.name.lower():
                        field_match = True
                        break
                elif field in ['date', 'day']:
                    if match.date and value in str(match.date).lower():
                        field_match = True
                        break
                elif field in ['time']:
                    if match.scheduled_times and any(value in time.lower() for time in match.scheduled_times):
                        field_match = True
                        break
                elif field in ['status']:
                    # Use Match class status method
                    if value in match.get_status().lower():
                        field_match = True
                        break
                    # Also check boolean status methods
                    if value == 'scheduled' and match.is_scheduled():
                        field_match = True
                        break
                    elif value == 'unscheduled' and match.is_unscheduled():
                        field_match = True
                        break
                    elif value == 'partial' and match.is_partially_scheduled():
                        field_match = True
                        break
                    elif value == 'full' and match.is_fully_scheduled():
                        field_match = True
                        break
                elif field in ['id', 'match_id']:
                    if value in str(match.id):
                        field_match = True
                        break
                elif field in ['captain']:
                    home_captain_match = (match.home_team and match.home_team.captain and 
                                        value in match.home_team.captain.lower())
                    visitor_captain_match = (match.visitor_team and match.visitor_team.captain and 
                                           value in match.visitor_team.captain.lower())
                    if home_captain_match or visitor_captain_match:
                        field_match = True
                        break
                elif field in ['division', 'div']:
                    if match.league and match.league.division and value in match.league.division.lower():
                        field_match = True
                        break
                elif field in ['year']:
                    if match.league and match.league.year and value in str(match.league.year):
                        field_match = True
                        break
            
            if not field_match:
                matches_query = False
                break
        
        # Check general search terms (search across all fields)
        if matches_query and general_terms:
            searchable_text = []
            
            if match.home_team:
                searchable_text.append(match.home_team.name.lower())
            if match.visitor_team:
                searchable_text.append(match.visitor_team.name.lower())
            if match.facility:
                searchable_text.append(match.facility.name.lower())
            if match.league:
                searchable_text.append(match.league.name.lower())
            if match.date:
                searchable_text.append(str(match.date).lower())
            if match.scheduled_times:
                searchable_text.extend([time.lower() for time in match.scheduled_times])
            
            # Add status using Match class method
            searchable_text.append(match.get_status().lower())
            searchable_text.append(str(match.id))
            
            combined_text = ' '.join(searchable_text)
            
            for term in general_terms:
                if term not in combined_text:
                    matches_query = False
                    break
        
        if matches_query:
            filtered_matches.append(match)
    
    return filtered_matches


# Export the register function for use in main app
__all__ = ['register_routes']