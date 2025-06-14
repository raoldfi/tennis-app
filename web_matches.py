"""
Updated web_matches.py - Includes bulk operations for auto-schedule, unschedule, and delete
Removes Generate Matches button functionality and adds comprehensive bulk operations
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

            
            # Convert league_id to League object
            league = None
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    flash(f'League with ID {league_id} not found', 'error')
                    league_id = None  # Reset to show all matches
            
            # Convert match_type string to MatchType enum using from_string()
            try:
                match_type = MatchType.from_string(match_type_str)
            except ValueError as e:
                print(f"Invalid match_type '{match_type_str}': {e}")
                flash(f'Invalid match type: {match_type_str}', 'error')
                match_type = MatchType.ALL  # Default to ALL if invalid
            
            # Get matches with proper parameters
            matches_list = db.list_matches(
                league=league,     # Pass League object, not league_id
                match_type=match_type  # Pass MatchType enum, not string
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

    @app.route('/matches/<int:match_id>/schedule-form')
    def get_schedule_form(match_id):
        """Get the schedule form for a specific match"""
        db = get_db()
        if db is None:
            return "Error: No database connected", 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return "Error: Match not found", 404
            
            facilities = db.list_facilities()
            return render_template('schedule_form.html', match=match, facilities=facilities)
            
        except Exception as e:
            print(f"Error loading schedule form for match {match_id}: {str(e)}")
            return f"Error loading form: {str(e)}", 500

    # ==================== BULK OPERATIONS ====================

    @app.route('/api/bulk-auto-schedule', methods=['POST'])
    def bulk_auto_schedule():
        """Bulk auto-schedule matches based on scope using db.auto_schedule_matches"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get filter parameters to determine scope
            league_id = request.args.get('league_id', type=int)
            match_type_str = request.args.get('match_type', 'unscheduled')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            search_query = request.args.get('search', '').strip()
            
            # Get the league object if specified
            league = None
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League with ID {league_id} not found'}), 404
            
            # Get unscheduled matches to determine scope
            try:
                match_type = MatchType.from_string('unscheduled')
            except ValueError:
                match_type = MatchType.UNSCHEDULED
            
            matches_list = db.list_matches(league=league, match_type=match_type)
            
            # Apply additional filters if this is a "selected" scope operation
            if any([start_date, end_date, search_query]):
                matches_list = filter_matches(matches_list, start_date, end_date, search_query)
            
            # Filter to only unscheduled matches
            unscheduled_matches = [m for m in matches_list if not m.is_scheduled()]
            
            if not unscheduled_matches:
                return jsonify({
                    'success': True,
                    'scheduled_count': 0,
                    'message': 'No unscheduled matches found to schedule'
                })
            
            # Use the database's auto_schedule_matches method
            try:
                if hasattr(db, 'auto_schedule_matches'):
                    # Call the database's auto-scheduling method with Match objects
                    result = db.auto_schedule_matches(matches=unscheduled_matches)
                    
                    if isinstance(result, dict):
                        # Extract results from detailed response
                        scheduled_count = result.get('scheduled_successfully', 0)
                        failed_count = result.get('failed_to_schedule', 0)
                        total_count = result.get('total_matches', len(unscheduled_matches))
                        message = result.get('message', f'Auto-scheduling completed')
                        
                        # Build comprehensive response
                        response_data = {
                            'success': True,
                            'scheduled_count': scheduled_count,
                            'failed_count': failed_count,
                            'total_count': total_count,
                            'message': message
                        }
                        
                        # Add details if available
                        if 'scheduling_details' in result:
                            response_data['details'] = result['scheduling_details']
                        
                        if 'failed_matches' in result:
                            response_data['failed_matches'] = result['failed_matches']
                        
                        return jsonify(response_data)
                    else:
                        # If result is just a count or different format
                        scheduled_count = result if isinstance(result, int) else len(unscheduled_matches)
                        return jsonify({
                            'success': True,
                            'scheduled_count': scheduled_count,
                            'total_count': len(unscheduled_matches),
                            'message': f'Successfully scheduled {scheduled_count} matches'
                        })
                else:
                    return jsonify({
                        'error': 'Auto-scheduling functionality not available in this database backend'
                    }), 501
                    
            except Exception as auto_schedule_error:
                print(f"Auto-schedule method error: {str(auto_schedule_error)}")
                traceback.print_exc()
                return jsonify({
                    'error': f'Auto-scheduling failed: {str(auto_schedule_error)}'
                }), 500
            
        except Exception as e:
            print(f"Bulk auto-schedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Bulk scheduling failed: {str(e)}'}), 500


    @app.route('/api/bulk-unschedule', methods=['POST'])
    def bulk_unschedule():
        """Bulk unschedule matches based on scope"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get filter parameters to determine scope
            league_id = request.args.get('league_id', type=int)
            match_type_str = request.args.get('match_type', 'scheduled')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            search_query = request.args.get('search', '').strip()
            
            # Get the league object if specified
            league = None
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League with ID {league_id} not found'}), 404
            
            # Get all matches (we'll filter to scheduled ones)
            try:
                match_type = MatchType.from_string('all')
            except ValueError:
                match_type = MatchType.ALL
            
            matches_list = db.list_matches(league=league, match_type=match_type)
            
            # Apply additional filters if this is a "selected" scope operation
            if any([start_date, end_date, search_query]):
                matches_list = filter_matches(matches_list, start_date, end_date, search_query)
            
            # Filter to only scheduled matches
            scheduled_matches = [m for m in matches_list if m.is_scheduled()]
            
            if not scheduled_matches:
                return jsonify({
                    'success': True,
                    'unscheduled_count': 0,
                    'message': 'No scheduled matches found to unschedule'
                })
            
            unscheduled_count = 0
            
            for match in scheduled_matches:
                try:
                    match.unschedule()
                    db.update_match(match)
                    unscheduled_count += 1
                    
                except Exception as e:
                    print(f"Error unscheduling match {match.id}: {str(e)}")
                    continue
            
            return jsonify({
                'success': True,
                'unscheduled_count': unscheduled_count,
                'message': f'Successfully unscheduled {unscheduled_count} matches'
            })
            
        except Exception as e:
            print(f"Bulk unschedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Bulk unscheduling failed: {str(e)}'}), 500

    @app.route('/api/bulk-delete', methods=['DELETE'])
    def bulk_delete():
        """Bulk delete unscheduled matches based on scope (safety: only unscheduled matches)"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get filter parameters to determine scope
            league_id = request.args.get('league_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            search_query = request.args.get('search', '').strip()
            
            # Get the league object if specified
            league = None
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League with ID {league_id} not found'}), 404
            
            # Get unscheduled matches only (safety measure)
            try:
                match_type = MatchType.from_string('unscheduled')
            except ValueError:
                match_type = MatchType.UNSCHEDULED
            
            matches_list = db.list_matches(league=league, match_type=match_type)
            
            # Apply additional filters if this is a "selected" scope operation
            if any([start_date, end_date, search_query]):
                matches_list = filter_matches(matches_list, start_date, end_date, search_query)
            
            # Double-check: only delete unscheduled matches for safety
            unscheduled_matches = [m for m in matches_list if not m.is_scheduled()]
            
            if not unscheduled_matches:
                return jsonify({
                    'success': True,
                    'deleted_count': 0,
                    'message': 'No unscheduled matches found to delete'
                })
            
            deleted_count = 0
            
            for match in unscheduled_matches:
                try:
                    db.delete_match(match.id)
                    deleted_count += 1
                    
                except Exception as e:
                    print(f"Error deleting match {match.id}: {str(e)}")
                    continue
            
            return jsonify({
                'success': True,
                'deleted_count': deleted_count,
                'message': f'Successfully deleted {deleted_count} unscheduled matches'
            })
            
        except Exception as e:
            print(f"Bulk delete error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Bulk deletion failed: {str(e)}'}), 500

    # ==================== INDIVIDUAL MATCH OPERATIONS ====================

    @app.route('/api/matches/<int:match_id>/unschedule', methods=['POST'])
    def unschedule_single_match(match_id):
        """Unschedule a single match"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            if not match.is_scheduled():
                return jsonify({'error': 'Match is not scheduled'}), 400
            
            match.unschedule()
            db.update_match(match)
            
            return jsonify({
                'success': True,
                'message': 'Match unscheduled successfully'
            })
            
        except Exception as e:
            print(f"Unschedule match error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Unscheduling failed: {str(e)}'}), 500

    @app.route('/api/matches/<int:match_id>', methods=['DELETE'])
    def delete_single_match(match_id):
        """Delete a single match (only if unscheduled for safety)"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            if match.is_scheduled():
                return jsonify({'error': 'Cannot delete scheduled match. Unschedule first for safety.'}), 400
            
            db.delete_match(match_id)
            
            return jsonify({
                'success': True,
                'message': 'Match deleted successfully'
            })
            
        except Exception as e:
            print(f"Delete match error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Deletion failed: {str(e)}'}), 500


# ==================== HELPER FUNCTIONS ====================

def convert_match_to_display(match):
    """Convert a Match object to display-friendly format for templates"""
    try:
        return {
            'id': match.id,
            'home_team_name': match.home_team.name if match.home_team else 'Unknown',
            'visitor_team_name': match.visitor_team.name if match.visitor_team else 'Unknown',
            'home_team_captain': match.home_team.captain if match.home_team else 'Unknown',
            'visitor_team_captain': match.visitor_team.captain if match.visitor_team else 'Unknown',
            'facility_name': match.facility.name if match.facility else 'No Facility Assigned',
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


def parse_match_date(date_value):
    """Parse match date to datetime.date object"""
    if isinstance(date_value, date):
        return date_value
    elif isinstance(date_value, datetime):
        return date_value.date()
    elif isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date()
        except ValueError:
            try:
                return datetime.strptime(date_value, '%m/%d/%Y').date()
            except ValueError:
                return None
    return None


def search_matches(matches_list, search_query):
    """Enhanced search functionality for matches with field-specific search"""
    if not search_query:
        return matches_list
    
    # Parse search query for field-specific searches (e.g., "team:Smith", "facility:North")
    search_terms = [term.strip().lower() for term in search_query.split() if term.strip()]
    field_searches = {}
    general_terms = []
    
    for term in search_terms:
        if ':' in term:
            field, value = term.split(':', 1)
            field = field.strip()
            value = value.strip()
            if field not in field_searches:
                field_searches[field] = []
            field_searches[field].append(value)
        else:
            general_terms.append(term)
    
    filtered_matches = []
    
    for match in matches_list:
        matches_query = True
        
        # Check field-specific searches
        for field, values in field_searches.items():
            field_match = False
            for value in values:
                if field in ['team', 'teams']:
                    # Search both home and visitor teams
                    home_match = (match.home_team and match.home_team.name and 
                                value in match.home_team.name.lower())
                    visitor_match = (match.visitor_team and match.visitor_team.name and 
                                   value in match.visitor_team.name.lower())
                    if home_match or visitor_match:
                        field_match = True
                        break
                elif field in ['facility', 'fac']:
                    if match.facility and match.facility.name and value in match.facility.name.lower():
                        field_match = True
                        break
                elif field in ['league']:
                    if match.league and match.league.name and value in match.league.name.lower():
                        field_match = True
                        break
                elif field in ['captain', 'cap']:
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