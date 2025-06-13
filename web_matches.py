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

from usta import Match, MatchType, League, Team


def register_routes(app):
    """Register match-related routes"""



    @app.route('/matches')
    def matches():
        """Matches page - Updated to use MatchType enum"""
        db = get_db()
        if db is None:
            return redirect(url_for('connect'))
        
        # Get filter parameters
        league_id = request.args.get('league_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search_query = request.args.get('search', '').strip()
        
        # Handle match type filtering - convert from web parameters to enum
        show_scheduled = request.args.get('show_scheduled', 'true').lower() == 'true'
        show_unscheduled = request.args.get('show_unscheduled', 'true').lower() == 'true'
        
        # Determine match type from parameters
        if show_scheduled and show_unscheduled:
            match_type = MatchType.ALL
        elif show_scheduled and not show_unscheduled:
            match_type = MatchType.SCHEDULED
        elif not show_scheduled and show_unscheduled:
            match_type = MatchType.UNSCHEDULED
        else:
            match_type = MatchType.ALL  # Default to all if both are false
        
        # Alternative: Direct match_type parameter (more explicit)
        match_type_param = request.args.get('match_type')
        if match_type_param:
            try:
                match_type = MatchType.from_string(match_type_param)
            except ValueError:
                flash(f'Invalid match type: {match_type_param}', 'warning')
                match_type = MatchType.ALL
        
        try:
            # Get selected league if filtering
            selected_league = None
            if league_id:
                selected_league = db.get_league(league_id)
                if not selected_league:
                    flash(f'League with ID {league_id} not found', 'warning')
                    return redirect(url_for('matches'))
            
            # Get matches using new enum-based function
            matches_list = db.list_matches(league=selected_league, match_type=match_type)
            print(f"Retrieved {len(matches_list)} matches from database (type: {match_type})")
            
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
            leagues = db.list_leagues()
            
            return render_template('matches.html', 
                                 matches=enhanced_matches,
                                 leagues=leagues,
                                 selected_league=selected_league,
                                 start_date=start_date,
                                 end_date=end_date,
                                 search_query=search_query,
                                 show_scheduled=show_scheduled,
                                 show_unscheduled=show_unscheduled,
                                 match_type=match_type.value)  # Pass enum value to template
        
        except Exception as e:
            print(f"Error in matches route: {str(e)}")
            traceback.print_exc()
            flash(f'Error loading matches: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
    
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
            
            # Get matches to schedule using enum
            if league_id:
                league = db.get_league(league_id)
                if not league:
                    return jsonify({'error': f'League with ID {league_id} not found'}), 404

            unscheduled_matches = db.list_matches(league, MatchType.UNSCHEDULED)
            
            if not unscheduled_matches:
                return jsonify({
                    'success': True,
                    'message': f'No unscheduled matches found in {scope_description}',
                    'scheduled_count': 0,
                    'failed_count': 0,
                    'total_count': 0,
                    'details': []
                })
            
            initial_unscheduled_count = len(unscheduled_matches)
            
            # Initialize results tracking
            scheduling_results = {
                'scheduled_matches': [],
                'failed_matches': [],
                'scheduling_details': []
            }
            
            # Auto-schedule matches
            print(f"Starting auto-scheduling for {initial_unscheduled_count} matches...")
            
            try:
                # Check if database has auto-scheduling capability
                if hasattr(db, 'auto_schedule_matches'):
                    # Use database's built-in auto-scheduling method
                    print("Using database auto-scheduling method")
                    result = db.auto_schedule_matches(
                        unscheduled_matches,
                        max_attempts=max_attempts,
                        allow_split_lines=allow_split_lines
                    )
                    scheduling_results.update(result)
                    
                else:
                    # No scheduling methods available
                    return jsonify({
                        'error': 'Auto-scheduling functionality not available in this database backend'
                    }), 500
            
            except Exception as e:
                print(f"Auto-scheduling error: {str(e)}")
                traceback.print_exc()
                return jsonify({'error': f'Scheduling algorithm failed: {str(e)}'}), 500
            
            # Re-fetch matches to get current state using MatchType enum
            print("Re-fetching matches to verify results...")
            current_all_matches = db.list_matches(league=selected_league, match_type=MatchType.ALL)
            current_unscheduled = [match for match in current_all_matches if not match.is_scheduled()]
            
            # Calculate final results
            final_scheduled_count = initial_unscheduled_count - len(current_unscheduled)
            final_failed_count = len(current_unscheduled)
            total_count = initial_unscheduled_count
            
            # Build response message
            if final_scheduled_count == total_count:
                message = f"✅ Successfully scheduled all {final_scheduled_count} matches in {scope_description}"
            elif final_scheduled_count > 0:
                message = f"⚠️ Scheduled {final_scheduled_count} of {total_count} matches in {scope_description}"
                if final_failed_count > 0:
                    message += f" ({final_failed_count} failed)"
            else:
                message = f"❌ Unable to schedule any matches in {scope_description}"
            
            # Prepare detailed response
            response_data = {
                'success': True,
                'message': message,
                'scheduled_count': final_scheduled_count,
                'failed_count': final_failed_count,
                'total_count': total_count,
                'scope': scope_description,
                'details': scheduling_results.get('scheduling_details', [])
            }
            
            # Add breakdown by status if we have details
            if scheduling_results.get('scheduling_details'):
                status_breakdown = {}
                for detail in scheduling_results['scheduling_details']:
                    status = detail.get('status', 'unknown')
                    status_breakdown[status] = status_breakdown.get(status, 0) + 1
                response_data['status_breakdown'] = status_breakdown
            
            print(f"Auto-scheduling complete: {final_scheduled_count} scheduled, {final_failed_count} failed")
            return jsonify(response_data)
            
        except Exception as e:
            print(f"Auto-schedule route error: {str(e)}")
            traceback.print_exc()
            return jsonify({'error': f'Auto-scheduling failed: {str(e)}'}), 500


    def unschedule_match(match_id):
        """Unschedule a match (remove facility, date, and all times)"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Get the match
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            # Unschedule the match
            if hasattr(db, 'unschedule_match'):
                db.unschedule_match(match)
            elif hasattr(match, 'unschedule'):
                match.unschedule()
                db.update_match(match)
            else:
                # Fallback: manually clear scheduling fields
                match.facility = None
                match.facility_id = None
                match.date = None
                match.scheduled_times = []
                db.update_match(match)
            
            return jsonify({
                'success': True,
                'message': f'Match {match_id} unscheduled successfully'
            })
            
        except Exception as e:
            print(f"Error unscheduling match {match_id}: {str(e)}")
            return jsonify({'error': f'Failed to unschedule match: {str(e)}'}), 500
    
    
    @app.route('/matches/<int:match_id>/delete', methods=['DELETE'])
    def delete_match(match_id):
        """Delete a match"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            # Check if match exists
            match = db.get_match(match_id)
            if not match:
                return jsonify({'error': 'Match not found'}), 404
            
            # Delete the match
            if hasattr(db, 'delete_match'):
                # If using a method that expects a match object
                if hasattr(db.delete_match, '__code__') and db.delete_match.__code__.co_argcount > 2:
                    db.delete_match(match)
                else:
                    # If using a method that expects match_id
                    db.delete_match(match_id)
            elif hasattr(db, 'match_manager') and hasattr(db.match_manager, 'delete_match'):
                db.match_manager.delete_match(match_id)
            else:
                return jsonify({'error': 'Delete functionality not available'}), 500
            
            return jsonify({
                'success': True,
                'message': f'Match {match_id} deleted successfully'
            })
            
        except Exception as e:
            print(f"Error deleting match {match_id}: {str(e)}")
            return jsonify({'error': f'Failed to delete match: {str(e)}'}), 500
    
    
    @app.route('/matches/bulk/unschedule', methods=['POST'])
    def bulk_unschedule_matches():
        """Unschedule multiple matches"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            data = request.get_json()
            if not data or 'match_ids' not in data:
                return jsonify({'error': 'match_ids required'}), 400
            
            match_ids = data['match_ids']
            if not isinstance(match_ids, list) or not match_ids:
                return jsonify({'error': 'match_ids must be a non-empty list'}), 400
            
            unscheduled_count = 0
            failed_matches = []
            
            for match_id in match_ids:
                try:
                    match = db.get_match(match_id)
                    if not match:
                        failed_matches.append(f"Match {match_id} not found")
                        continue
                    
                    # Unschedule the match
                    if hasattr(db, 'unschedule_match'):
                        db.unschedule_match(match)
                    elif hasattr(match, 'unschedule'):
                        match.unschedule()
                        db.update_match(match)
                    else:
                        # Fallback: manually clear scheduling fields
                        match.facility = None
                        match.facility_id = None
                        match.date = None
                        match.scheduled_times = []
                        db.update_match(match)
                    
                    unscheduled_count += 1
                    
                except Exception as e:
                    failed_matches.append(f"Match {match_id}: {str(e)}")
            
            result = {
                'success': True,
                'unscheduled_count': unscheduled_count,
                'total_requested': len(match_ids),
                'message': f'Unscheduled {unscheduled_count} of {len(match_ids)} matches'
            }
            
            if failed_matches:
                result['failed_matches'] = failed_matches
                result['message'] += f' ({len(failed_matches)} failed)'
            
            return jsonify(result)
            
        except Exception as e:
            print(f"Error in bulk unschedule: {str(e)}")
            return jsonify({'error': f'Bulk unschedule failed: {str(e)}'}), 500
    
    
    @app.route('/matches/bulk/delete', methods=['DELETE'])
    def bulk_delete_matches():
        """Delete multiple matches"""
        db = get_db()
        if db is None:
            return jsonify({'error': 'No database connected'}), 500
        
        try:
            data = request.get_json()
            if not data or 'match_ids' not in data:
                return jsonify({'error': 'match_ids required'}), 400
            
            match_ids = data['match_ids']
            if not isinstance(match_ids, list) or not match_ids:
                return jsonify({'error': 'match_ids must be a non-empty list'}), 400
            
            deleted_count = 0
            failed_matches = []
            
            for match_id in match_ids:
                try:
                    # Check if match exists
                    match = db.get_match(match_id)
                    if not match:
                        failed_matches.append(f"Match {match_id} not found")
                        continue
                    
                    # Delete the match
                    if hasattr(db, 'delete_match'):
                        # Check if method expects match object or match_id
                        if hasattr(db.delete_match, '__code__') and db.delete_match.__code__.co_argcount > 2:
                            db.delete_match(match)
                        else:
                            db.delete_match(match_id)
                    elif hasattr(db, 'match_manager') and hasattr(db.match_manager, 'delete_match'):
                        db.match_manager.delete_match(match_id)
                    else:
                        failed_matches.append(f"Match {match_id}: Delete functionality not available")
                        continue
                    
                    deleted_count += 1
                    
                except Exception as e:
                    failed_matches.append(f"Match {match_id}: {str(e)}")
            
            result = {
                'success': True,
                'deleted_count': deleted_count,
                'total_requested': len(match_ids),
                'message': f'Deleted {deleted_count} of {len(match_ids)} matches'
            }
            
            if failed_matches:
                result['failed_matches'] = failed_matches
                result['message'] += f' ({len(failed_matches)} failed)'
            
            return jsonify(result)
            
        except Exception as e:
            print(f"Error in bulk delete: {str(e)}")
            return jsonify({'error': f'Bulk delete failed: {str(e)}'}), 500



# ========== Helper Functions ==============

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