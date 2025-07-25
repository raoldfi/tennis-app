"""
Updated web_matches.py - Includes bulk operations for auto-schedule, unschedule, and delete
Fixed to pass Match objects to template instead of dictionaries
"""

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
)
from datetime import datetime, date, timedelta
import traceback
import json
import yaml
import time

from usta import Match, MatchType, League
from web_matches_calendar import create_calendar_context


def format_score_description() -> str:
    """Format quality score description as colored HTML list using Match.get_quality_score_description()"""
    # Get the raw description from the Match class
    raw_description = Match.get_quality_score_description()
    
    # Parse the description to extract individual score items
    # Format: "Quality scores: 20 = poor - scheduled..., 40 = acceptable - league..., ..."
    description_part = raw_description.replace("Quality scores: ", "")
    score_items = description_part.split(", ")
    
    # Define color mapping for each score level
    color_map = {
        "20": "#dc3545",  # Red - Poor
        "40": "#fd7e14",  # Orange - Acceptable  
        "60": "#ffc107",  # Yellow - Fair
        "80": "#0dcaf0",  # Blue - Good
        "100": "#198754"  # Green - Optimal
    }
    
    # Build compact HTML
    items_html = ""
    for item in score_items:
        if " = " in item:
            score_part, desc_part = item.split(" = ", 1)
            score = score_part.strip()
            
            # Split description into label and detail
            if " - " in desc_part:
                label_part, detail_part = desc_part.split(" - ", 1)
                label = label_part.strip()
                detail = detail_part.strip()
            else:
                label = desc_part.strip()
                detail = ""
            
            # Get color for this score
            border_color = color_map.get(score, "#6c757d")
            
            # Add compact HTML for this score item
            detail_html = f'<div style="margin-top:2px;color:#666;font-size:0.9em;text-transform:capitalize">{detail}</div>' if detail else ''
            items_html += f'<div style="border-left:6px solid {border_color};padding:8px 12px;margin:8px 0;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.08);border-radius:4px;font-size:0.85em"><div style="font-weight:600;color:#333;text-transform:capitalize">{score} – {label}</div>{detail_html}</div>'
    
    return f'<div style="margin:0;padding:0">{items_html}</div>'


def register_routes(app, get_db):
    """Register match-related routes with Flask app"""

    @app.route("/matches")
    def matches():
        """Display matches with filtering and search"""
        db = get_db()
        if not db:
            return redirect(url_for("index"))

        try:
            # Get filter parameters
            league_id = request.args.get("league_id", type=int)
            facility_id = request.args.get("facility_id", type=int)  # NEW
            team_id = request.args.get("team_id", type=int)  # NEW
            match_type_str = request.args.get("match_type", "all")
            start_date = request.args.get("start_date", "").strip()
            end_date = request.args.get("end_date", "").strip()
            search_query = request.args.get("search_query", "").strip()
            show_scheduled = request.args.get("show_scheduled", "1") == "1"
            show_unscheduled = request.args.get("show_unscheduled", "1") == "1"
            view_type = request.args.get("view_type", "table")  # NEW: view toggle parameter

            # Get filter objects
            league = db.get_league(league_id) if league_id else None
            facility = db.get_facility(facility_id) if facility_id else None  # NEW
            team = db.get_team(team_id) if team_id else None  # NEW

            print(
                f"Trying to get Matches for League = {league_id}, match_type={match_type_str}"
            )

            # Convert match_type string to MatchType enum using from_string()
            try:
                match_type = MatchType.from_string(match_type_str)
            except ValueError as e:
                print(f"Invalid match_type '{match_type_str}': {e}")
                flash(f"Invalid match type: {match_type_str}", "error")
                match_type = MatchType.ALL  # Default to ALL if invalid

            # Get matches with proper parameters
            matches_list = db.list_matches(
                facility=facility,
                league=league,
                team=team,
                match_type=match_type,  # Pass MatchType enum, not string
            )

            # Apply filters
            filtered_matches = filter_matches(
                matches_list, start_date, end_date, search_query
            )

            # Apply scheduling filter
            if not show_scheduled:
                filtered_matches = [m for m in filtered_matches if not m.is_scheduled()]
            if not show_unscheduled:
                filtered_matches = [m for m in filtered_matches if m.is_scheduled()]

            # FIXED: Pass original Match objects to template instead of converting to dicts
            # The template expects Match objects with methods like get_scheduled_times()
            # Sort matches with proper None handling for dates
            # In web_matches.py, around line 85, replace the sort_key function with this:

            def sort_key(match):
                if match.date is None:
                    return (1, "")  # Put None dates last

                # match.date is already a string in YYYY-MM-DD format
                return (0, match.date)

            matches_display = sorted(filtered_matches, key=sort_key)

            # Calculate quality score statistics for matches that are scheduled
            quality_scores = []
            for match in matches_display:
                if match.is_scheduled() and match.date:
                    try:
                        quality_score = match.get_quality_score()
                        quality_scores.append(quality_score)
                    except Exception:
                        continue  # Skip matches that can't calculate quality

            # Calculate sum and average
            if quality_scores:
                quality_sum = sum(quality_scores)
                quality_average = quality_sum / len(quality_scores)
                quality_stats = {
                    "sum": quality_sum,
                    "average": round(quality_average, 2),
                    "count": len(quality_scores),
                    "total_matches": len(matches_display),
                }
            else:
                quality_stats = {
                    "sum": 0,
                    "average": 0,
                    "count": 0,
                    "total_matches": len(matches_display),
                }

            # Get data for filter dropdowns
            selected_league = db.get_league(league_id) if league_id else None
            selected_facility = (
                db.get_facility(facility_id) if facility_id else None
            )  # NEW
            selected_team = db.get_team(team_id) if team_id else None  # NEW
            leagues = db.list_leagues()
            facilities = db.list_facilities()  # NEW
            teams = db.list_teams(league=selected_league)  # NEW

            # Get formatted quality score description using helper function
            quality_description = format_score_description()

            # Generate calendar data if calendar view is selected
            calendar_context = {}
            if view_type == 'calendar':
                # Get month/year parameters for calendar navigation
                month = request.args.get("month", type=int)
                year = request.args.get("year", type=int)
                
                try:
                    calendar_context = create_calendar_context(
                        db_interface=db,
                        month=month,
                        year=year
                    )
                except Exception as e:
                    print(f"Error generating calendar context: {str(e)}")
                    # Continue without calendar data if there's an error
                    calendar_context = {}

            return render_template(
                "matches.html",
                matches=matches_display,
                leagues=leagues,
                facilities=facilities,  # NEW
                teams=teams,  # NEW
                selected_league=selected_league,
                selected_facility=selected_facility,  # NEW
                selected_team=selected_team,  # NEW
                facility_id=facility_id,  # NEW
                team_id=team_id,  # NEW
                match_type=str(match_type_str),
                start_date=start_date,
                end_date=end_date,
                search_query=search_query,
                show_scheduled=show_scheduled,
                show_unscheduled=show_unscheduled,
                quality_stats=quality_stats,
                quality_description=quality_description,  # Add quality description
                view_type=view_type,  # NEW: view toggle parameter
                **calendar_context  # Add calendar data when in calendar view
            )

        except Exception as e:
            print(f"Error in matches route: {str(e)}")
            traceback.print_exc()
            flash(f"Error loading matches: {str(e)}", "error")
            return redirect(url_for("dashboard"))

    @app.route("/matches/<int:match_id>")
    def view_match(match_id):
        """View a single match with full details"""
        db = get_db()
        if db is None:
            flash("No database connection", "error")
            return redirect(url_for("index"))

        try:
            match = db.get_match(match_id)
            if not match:
                flash(f"Match #{match_id} not found", "error")
                return redirect(url_for("matches"))

            # Get additional data for the match view
            leagues = db.list_leagues()  # For breadcrumb/navigation

            return render_template("view_match.html", match=match, leagues=leagues)

        except Exception as e:
            flash(f"Error loading match: {str(e)}", "error")
            return redirect(url_for("matches"))

    @app.route("/matches/<int:match_id>/schedule", methods=["DELETE"])
    def unschedule_match(match_id):
        """Unschedule a match - remove all scheduling information"""
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connected"}), 500

        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({"error": "Match not found"}), 404

            if match.is_unscheduled():
                return jsonify({"warning": f"match {match_id} is already unscheduled"})

            success = db.unschedule_match(match)

            if success:
                return jsonify(
                    {
                        "success": True,
                        "message": f"Match {match_id} has been unscheduled successfully",
                    }
                )
            else:
                return jsonify({"error": f"Could not unschedule match_id {match_id}"})

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/matches/<int:match_id>/schedule", methods=["POST"])
    def schedule_match(match_id):
        """Schedule a match"""
        print(f"\n=== SCHEDULE MATCH {match_id} ===")
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connected"}), 500

        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({"error": "Match not found"}), 404

            # Get form data
            facility_id = request.form.get("facility_id", type=int)
            date_str = request.form.get("date")
            times = request.form.getlist("times")

            print(
                f"Scheduling data: facility_id={facility_id}, date={date_str}, times={times}"
            )

            # Validate inputs
            if not facility_id:
                return jsonify({"error": "Facility is required"}), 400

            if not date_str:
                return jsonify({"error": "Date is required"}), 400

            if not times:
                return jsonify({"error": "At least one time slot is required"}), 400

            # Get facility
            facility = db.get_facility(facility_id)
            if not facility:
                return jsonify({"error": "Invalid facility"}), 400

            # Parse date
            try:
                match_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Invalid date format"}), 400

            # Update match
            match.facility = facility
            match.date = date_str  # Store as string in YYYY-MM-DD format
            match.scheduled_times = times

            # Save to database
            db.schedule_match_split_times(
                match=match, facility=facility, date=match_date, timeslots=times
            )

            print(f"Match {match_id} scheduled successfully")

            return jsonify(
                {
                    "success": True,
                    "message": f"Match scheduled for {date_str} at {facility.name}",
                }
            )

        except Exception as e:
            print(f"Schedule match error: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": f"Scheduling failed: {str(e)}"}), 500

    @app.route("/matches/<int:match_id>", methods=["DELETE"])
    def delete_match(match_id):
        """Delete an unscheduled match"""
        print(f"\n=== DELETE MATCH {match_id} ===")
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connected"}), 500

        try:
            match = db.get_match(match_id)
            if not match:
                return jsonify({"error": "Match not found"}), 404

            # Safety check - only allow deletion of unscheduled matches
            if match.is_scheduled():
                return (
                    jsonify(
                        {
                            "error": "Cannot delete scheduled matches. Unschedule first for safety."
                        }
                    ),
                    400,
                )

            db.delete_match(match_id)

            return jsonify({"success": True, "message": "Match deleted successfully"})

        except Exception as e:
            print(f"Delete match error: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": f"Deletion failed: {str(e)}"}), 500

    # ==================== Bulk Operations ====================

    @app.route("/api/import-matches", methods=["POST"])
    def api_import_matches():
        """API endpoint for importing matches from YAML"""
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connection"}), 500

        try:
            # Validate file upload
            if "yaml_file" not in request.files:
                return jsonify({"error": "No file uploaded"}), 400

            file = request.files["yaml_file"]
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            if not file.filename.lower().endswith((".yaml", ".yml")):
                return (
                    jsonify({"error": "File must be a YAML file (.yaml or .yml)"}),
                    400,
                )

            # Read and parse YAML content
            try:
                yaml_content = file.read().decode("utf-8")
                data = yaml.safe_load(yaml_content)
            except UnicodeDecodeError:
                return jsonify({"error": "File must be valid UTF-8 text"}), 400
            except yaml.YAMLError as e:
                return jsonify({"error": f"Invalid YAML format: {str(e)}"}), 400

            # Validate data structure
            if not isinstance(data, list):
                return jsonify({"error": "YAML must contain a list of matches"}), 400

            return jsonify(
                {
                    "message": "Match import endpoint not yet implemented",
                    "imported_count": 0,
                }
            )

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ==================== Bulk Operations ====================

    @app.route("/api/bulk-auto-schedule", methods=["POST"])
    def bulk_auto_schedule():
        """Bulk auto-schedule matches using db.match_manager.auto_schedule_matches"""
        print(f"\n=== BULK AUTO-SCHEDULE ===")
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connected"}), 500

        try:
            # Get scope and parameters
            scope = request.form.get("scope", "all")
            league_id = request.form.get("league_id", type=int)

            print(f"Bulk auto-schedule scope: {scope}, league_id: {league_id}")

            # Get the matches to schedule based on scope
            matches_to_schedule = []

            if scope == "all":
                # All unscheduled matches - use MatchType.UNSCHEDULED directly
                matches_to_schedule = db.list_matches(match_type=MatchType.UNSCHEDULED)
                print(
                    f"Auto-scheduling all unscheduled matches: {len(matches_to_schedule)} found"
                )

            elif scope == "league" and league_id:
                # Specific league only - get unscheduled matches for that league
                league = db.get_league(league_id)
                if not league:
                    return jsonify({"error": f"League {league_id} not found"}), 400

                matches_to_schedule = db.list_matches(
                    league=league, match_type=MatchType.UNSCHEDULED
                )
                print(
                    f"Auto-scheduling unscheduled matches for league '{league.name}': {len(matches_to_schedule)} found"
                )

            elif scope == "selected":
                # Apply current filter parameters to get the same matches as displayed
                league_id_filter = request.form.get("league_id", type=int)
                match_type_str = request.form.get("match_type", "all")
                start_date = request.form.get("start_date")
                end_date = request.form.get("end_date")
                search_query = request.form.get("search", "").strip()

                # Get filtered matches - for auto-scheduling, we want unscheduled matches from the current view
                league = db.get_league(league_id_filter) if league_id_filter else None

                # For selected scope, we want unscheduled matches from the current view
                # So we use UNSCHEDULED regardless of the original match_type filter
                all_matches = db.list_matches(
                    league=league, match_type=MatchType.UNSCHEDULED
                )
                matches_to_schedule = filter_matches(
                    all_matches, start_date, end_date, search_query
                )
                print(
                    f"Auto-scheduling filtered unscheduled matches: {len(matches_to_schedule)} found"
                )

            else:
                return jsonify({"error": "Invalid scope or missing parameters"}), 400

            if not matches_to_schedule:
                return jsonify(
                    {
                        "success": True,
                        "message": "No unscheduled matches found to auto-schedule",
                        "scheduled_count": 0,
                        "failed_count": 0,
                        "total_count": 0,
                    }
                )

            print(
                f"Found {len(matches_to_schedule)} unscheduled matches to auto-schedule"
            )

            # Call the database auto_schedule_matches method with list of Match objects
            try:
                print(
                    f"Calling db.match_manager.auto_schedule_matches with {len(matches_to_schedule)} matches"
                )
                # Get dry_run parameter from form, default to True
                dry_run = request.form.get("dry_run", "true").lower() in [
                    "true",
                    "1",
                    "yes",
                ]

                # Generate a random seed for reproducible scheduling
                import random
                
                # Check if a seed was provided (for Execute Scheduling button)
                provided_seed = request.form.get("seed")
                if provided_seed:
                    try:
                        seed = int(provided_seed)
                        print(f"Using provided seed for reproducible scheduling: {seed}")
                    except (ValueError, TypeError):
                        # If provided seed is invalid, generate a new one
                        seed = int(time.time() * 1000) % 2**31
                        print(f"Invalid provided seed, generated new seed: {seed}")
                else:
                    # Generate a new random seed based on current time
                    seed = int(time.time() * 1000) % 2**31
                    print(f"Generated new seed for reproducible scheduling: {seed}")

                # UPDATED: Use match_manager instead of scheduling_manager
                scheduling_results = db.match_manager.auto_schedule_matches(
                    matches=matches_to_schedule, dry_run=dry_run, seed=seed
                )

                # Extract results based on match_manager return format
                scheduled_count = scheduling_results.get("scheduled", 0)
                failed_count = scheduling_results.get("failed", 0)
                total_count = scheduling_results.get(
                    "total_matches", len(matches_to_schedule)
                )
                scheduling_details = scheduling_results.get("scheduling_details", [])
                errors = scheduling_results.get("errors", [])

                # Calculate success rate
                success_rate = round(
                    (scheduled_count / total_count * 100) if total_count > 0 else 0, 1
                )
                
                # Calculate average quality score for scheduled matches
                scheduled_matches_with_quality = [
                    detail for detail in scheduling_details 
                    if detail.get('quality_score') is not None
                ]
                average_quality_score = round(
                    sum(detail['quality_score'] for detail in scheduled_matches_with_quality) / len(scheduled_matches_with_quality)
                    if scheduled_matches_with_quality else 0, 1
                )

                print(
                    f"Auto-scheduling results: {scheduled_count} scheduled, {failed_count} failed, success rate: {success_rate}%"
                )

                # Enhanced warning output when not all matches are scheduled
                if failed_count > 0:
                    warning_message = f"⚠️ WARNING: Auto-scheduling incomplete!"
                    print(f"\n{warning_message}")
                    print(f"Results structure:")
                    print(f"  - Total matches processed: {total_count}")
                    print(f"  - Successfully scheduled: {scheduled_count}")
                    print(f"  - Failed to schedule: {failed_count}")
                    print(f"  - Success rate: {success_rate}%")

                    # Log detailed error information
                    if errors:
                        print(f"  - Error details:")
                        for i, error in enumerate(errors[:5], 1):  # Show first 5 errors
                            print(f"    {i}. {error}")
                        if len(errors) > 5:
                            print(f"    ... and {len(errors) - 5} more errors")

                    # Log scheduling details for failed matches
                    failed_details = [
                        detail
                        for detail in scheduling_details
                        if detail.get("status") == "scheduling_failed"
                    ]
                    if failed_details:
                        print(f"  - Failed match details:")
                        for i, detail in enumerate(
                            failed_details[:3], 1
                        ):  # Show first 3 failed matches
                            match_info = f"Match {detail.get('match_id', 'Unknown')}"
                            home_team = detail.get("home_team", "")
                            visitor_team = detail.get("visitor_team", "")
                            if home_team and visitor_team:
                                match_info += f" ({home_team} vs {visitor_team})"
                            print(
                                f"    {i}. {match_info}: {detail.get('reason', 'Unknown reason')}"
                            )
                        if len(failed_details) > 3:
                            print(
                                f"    ... and {len(failed_details) - 3} more failed matches"
                            )

                    print(f"⚠️ End warning\n")

                # Prepare response message based on results
                if total_count == 0:
                    response_message = "No unscheduled matches found to auto-schedule"
                elif scheduled_count > 0 and failed_count == 0:
                    response_message = (
                        f"✅ Successfully auto-scheduled all {scheduled_count} matches"
                    )
                elif scheduled_count > 0 and failed_count > 0:
                    response_message = f"⚠️ Auto-scheduled {scheduled_count} of {total_count} matches. {failed_count} could not be scheduled (no available time slots)."
                elif scheduled_count == 0 and total_count > 0:
                    response_message = f"❌ Could not auto-schedule any of the {total_count} matches. No available time slots found."
                else:
                    response_message = f"Auto-scheduled {scheduled_count} matches"

                # Include success rate in message if meaningful
                if total_count > 0:
                    response_message += f" (Success rate: {success_rate}%)"

                # Enhanced response structure for partial failures
                response_data = {
                    "success": True,
                    "total_matches": len(matches_to_schedule),
                    "scheduled": scheduled_count,
                    "failed": failed_count,
                    "dry_run": dry_run,
                    "seed": seed,  # Include seed for reproducible execution
                    "scheduling_details": scheduling_details,
                    "average_quality_score": average_quality_score,
                    "operations": (
                        scheduling_results.get("operations_performed", [])
                        if dry_run
                        else []
                    ),
                }

                # Update message based on mode
                if dry_run:
                    if response_data["scheduled"] > 0:
                        response_data["message"] = (
                            f'Preview: Would schedule {response_data["scheduled"]} matches'
                        )
                    else:
                        response_data["message"] = (
                            f"Preview: No matches can be scheduled"
                        )
                else:
                    response_data["message"] = response_message

                # Add warning flag and refresh option for partial failures
                if failed_count > 0:
                    response_data["warning"] = True
                    response_data["warning_message"] = (
                        f"Not all matches could be scheduled. {failed_count} of {total_count} matches failed."
                    )
                    response_data["show_refresh"] = True
                    response_data["refresh_text"] = "Refresh Page"

                    # Include detailed failure information in response
                    response_data["failure_summary"] = {
                        "failed_matches": failed_count,
                        "success_rate": success_rate,
                        "common_issues": _extract_common_scheduling_issues(errors),
                        "failed_match_details": [
                            {
                                "match_id": detail.get("match_id"),
                                "home_team": detail.get("home_team", ""),
                                "visitor_team": detail.get("visitor_team", ""),
                                "reason": detail.get("reason", "Unknown reason"),
                            }
                            for detail in failed_details[
                                :5
                            ]  # Limit to first 5 failed matches
                        ],
                    }

                return jsonify(response_data)

            except Exception as db_error:
                print(f"Database auto-scheduling error: {str(db_error)}")
                traceback.print_exc()
                return (
                    jsonify({"error": f"Auto-scheduling failed: {str(db_error)}"}),
                    500,
                )

        except Exception as e:
            print(f"Bulk auto-schedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": f"Bulk auto-schedule failed: {str(e)}"}), 500

    @app.route("/api/bulk-unschedule", methods=["POST"])
    def bulk_unschedule():
        """Bulk unschedule matches"""
        print(f"\n=== BULK UNSCHEDULE ===")
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connected"}), 500

        try:
            # Get scope and parameters
            scope = request.form.get("scope", "all")
            league_id = request.form.get("league_id", type=int)

            print(f"Bulk unschedule scope: {scope}, league_id: {league_id}")

            # Determine which matches to unschedule - use MatchType.SCHEDULED directly
            matches_to_unschedule = []

            if scope == "all":
                # All scheduled matches - use MatchType.SCHEDULED directly
                matches_to_unschedule = db.list_matches(match_type=MatchType.SCHEDULED)

            elif scope == "league" and league_id:
                # Specific league only - get scheduled matches for that league
                league = db.get_league(league_id)
                if not league:
                    return jsonify({"error": f"League {league_id} not found"}), 400

                matches_to_unschedule = db.list_matches(
                    league=league, match_type=MatchType.SCHEDULED
                )

            elif scope == "selected":
                # Apply current filter parameters to get the same matches as displayed
                league_id_filter = request.form.get("league_id", type=int)
                match_type_str = request.form.get("match_type", "all")
                start_date = request.form.get("start_date")
                end_date = request.form.get("end_date")
                search_query = request.form.get("search", "").strip()

                # Get filtered matches - for unscheduling, we want scheduled matches from the current view
                league = db.get_league(league_id_filter) if league_id_filter else None

                # For selected scope, we want scheduled matches from the current view
                # So we use SCHEDULED regardless of the original match_type filter
                all_matches = db.list_matches(
                    league=league, match_type=MatchType.SCHEDULED
                )
                matches_to_unschedule = filter_matches(
                    all_matches, start_date, end_date, search_query
                )

            else:
                return jsonify({"error": "Invalid scope or missing parameters"}), 400

            if not matches_to_unschedule:
                return jsonify(
                    {
                        "success": True,
                        "message": "No scheduled matches found to unschedule",
                        "unscheduled_count": 0,
                        "total_count": 0,
                    }
                )

            print(f"Found {len(matches_to_unschedule)} scheduled matches to unschedule")

            # Unschedule each match
            unscheduled_count = 0
            errors = []

            for match in matches_to_unschedule:
                try:
                    # Save to database
                    if db.unschedule_match(match):
                        unscheduled_count += 1
                        print(f"Successfully unscheduled match {match.id}")

                except Exception as e:
                    errors.append(f"Error unscheduling match {match.id}: {str(e)}")
                    print(f"Error unscheduling match {match.id}: {str(e)}")

            # Prepare response
            message = f"Unscheduled {unscheduled_count} of {len(matches_to_unschedule)} matches"
            if errors:
                message += f". {len(errors)} matches could not be unscheduled."

            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "unscheduled_count": unscheduled_count,
                    "total_count": len(matches_to_unschedule),
                    "errors": errors[:5],  # Limit error details
                }
            )

        except Exception as e:
            print(f"Bulk unschedule error: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": f"Bulk unschedule failed: {str(e)}"}), 500

    @app.route("/api/bulk-delete", methods=["POST"])
    def bulk_delete():
        """Bulk delete unscheduled matches (safety restriction)"""
        print(f"\n=== BULK DELETE ===")
        db = get_db()
        if db is None:
            return jsonify({"error": "No database connected"}), 500

        try:
            # Get scope and parameters
            scope = request.form.get(
                "scope", "unscheduled"
            )  # Default to unscheduled only
            league_id = request.form.get("league_id", type=int)

            print(f"Bulk delete scope: {scope}, league_id: {league_id}")

            # Determine which matches to delete - use MatchType.UNSCHEDULED directly for safety
            matches_to_delete = []

            if scope == "unscheduled":
                # All unscheduled matches - use MatchType.UNSCHEDULED directly
                matches_to_delete = db.list_matches(match_type=MatchType.UNSCHEDULED)

            elif scope == "league" and league_id:
                # Unscheduled matches in specific league only
                league = db.get_league(league_id)
                if not league:
                    return jsonify({"error": f"League {league_id} not found"}), 400

                matches_to_delete = db.list_matches(
                    league=league, match_type=MatchType.UNSCHEDULED
                )

            elif scope == "selected":
                # Apply current filter parameters, but only unscheduled
                league_id_filter = request.form.get("league_id", type=int)
                match_type_str = request.form.get("match_type", "all")
                start_date = request.form.get("start_date")
                end_date = request.form.get("end_date")
                search_query = request.form.get("search", "").strip()

                # Get filtered matches - for deletion, we only want unscheduled matches for safety
                league = db.get_league(league_id_filter) if league_id_filter else None

                # For selected scope, we only delete unscheduled matches for safety
                # So we use UNSCHEDULED regardless of the original match_type filter
                all_matches = db.list_matches(
                    league=league, match_type=MatchType.UNSCHEDULED
                )
                matches_to_delete = filter_matches(
                    all_matches, start_date, end_date, search_query
                )

            else:
                return jsonify({"error": "Invalid scope or missing parameters"}), 400

            if not matches_to_delete:
                return jsonify(
                    {
                        "success": True,
                        "message": "No unscheduled matches found to delete",
                        "deleted_count": 0,
                        "total_count": 0,
                    }
                )

            print(f"Found {len(matches_to_delete)} unscheduled matches to delete")

            # Delete each match
            deleted_count = 0
            errors = []

            for match in matches_to_delete:
                try:
                    # Double-check it's unscheduled for safety (though we got them via UNSCHEDULED query)
                    if match.is_scheduled():
                        errors.append(
                            f"Match {match.id} is scheduled - skipped for safety"
                        )
                        continue

                    # Delete the match
                    db.delete_match(match.id)
                    deleted_count += 1
                    print(f"Successfully deleted match {match.id}")

                except Exception as e:
                    errors.append(f"Error deleting match {match.id}: {str(e)}")
                    print(f"Error deleting match {match.id}: {str(e)}")

            # Prepare response
            message = f"Deleted {deleted_count} of {len(matches_to_delete)} unscheduled matches"
            if errors:
                message += f". {len(errors)} matches could not be deleted."

            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "deleted_count": deleted_count,
                    "total_count": len(matches_to_delete),
                    "errors": errors[:5],  # Limit error details
                }
            )

        except Exception as e:
            print(f"Bulk delete error: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": f"Bulk delete failed: {str(e)}"}), 500

    # ==================== AJAX ENDPOINTS ====================
    
    @app.route("/api/calendar-data")
    def calendar_data():
        """AJAX endpoint to get calendar data for a specific month/year"""
        db = get_db()
        if not db:
            return jsonify({"error": "Database not available"}), 500
        
        try:
            # Get month/year parameters
            month = request.args.get("month", type=int)
            year = request.args.get("year", type=int)
            
            if not month or not year:
                return jsonify({"error": "Month and year parameters required"}), 400
            
            # Get all current filter parameters to maintain consistency
            league_id = request.args.get("league_id", type=int)
            facility_id = request.args.get("facility_id", type=int)
            team_id = request.args.get("team_id", type=int)
            match_type_str = request.args.get("match_type", "all")
            start_date = request.args.get("start_date", "").strip()
            end_date = request.args.get("end_date", "").strip()
            search_query = request.args.get("search_query", "").strip()
            
            # Get filter objects
            league = db.get_league(league_id) if league_id else None
            facility = db.get_facility(facility_id) if facility_id else None
            team = db.get_team(team_id) if team_id else None
            
            # Convert match_type string to MatchType enum
            try:
                match_type = MatchType.from_string(match_type_str)
            except ValueError:
                match_type = MatchType.ALL
            
            # Get matches with filters
            matches_list = db.list_matches(
                facility=facility,
                league=league,
                team=team,
                match_type=match_type,
            )
            
            # Apply additional filters
            filtered_matches = filter_matches(
                matches_list, start_date, end_date, search_query
            )
            
            # Create calendar context
            calendar_context = create_calendar_context(db, month, year)
            
            # Filter calendar matches based on current filters
            for week in calendar_context['calendar_weeks']:
                for day in week.days:
                    # Filter day matches based on current filters
                    day.matches = [m for m in day.matches if m in filtered_matches]
            
            # Convert calendar data to JSON-serializable format
            calendar_json = {
                'calendar_weeks': [],
                'current_month': calendar_context['current_month'],
                'current_year': calendar_context['current_year'],
                'month_name': calendar_context['month_name'],
                'prev_month': calendar_context['prev_month'],
                'prev_year': calendar_context['prev_year'],
                'next_month': calendar_context['next_month'],
                'next_year': calendar_context['next_year']
            }
            
            for week in calendar_context['calendar_weeks']:
                week_data = {'days': []}
                for day in week.days:
                    matches_data = []
                    for match in day.matches:
                        match_data = {
                            'id': match.id,
                            'home_team': match.home_team.name if match.home_team else 'TBD',
                            'visitor_team': match.visitor_team.name if match.visitor_team else 'TBD',
                            'facility': match.facility.name if match.facility else None,
                            'time': match.scheduled_times[0] if match.scheduled_times else None
                        }
                        matches_data.append(match_data)
                    
                    day_data = {
                        'day': day.day,
                        'is_today': day.is_today,
                        'is_other_month': day.is_other_month,
                        'matches': matches_data
                    }
                    week_data['days'].append(day_data)
                calendar_json['calendar_weeks'].append(week_data)
            
            return jsonify(calendar_json)
            
        except Exception as e:
            print(f"Error in calendar_data endpoint: {str(e)}")
            return jsonify({"error": f"Failed to load calendar data: {str(e)}"}), 500

    # ==================== JINJA2 FILTERS ====================

    def format_weekday(date_str):
        """Format date string to weekday abbreviation"""
        if not date_str or date_str == "TBD":
            return "TBD"

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_obj.strftime("%a")  # Returns Mon, Tue, Wed, etc.
        except (ValueError, TypeError):
            return "TBD"

    def group_matches_by_date(matches):
        """Group matches by date, with unscheduled matches last"""
        from itertools import groupby

        # Sort matches: scheduled dates first (by date), then unscheduled
        def sort_key(match):
            if match.date is None:
                return (1, "")  # Put None dates last

            # match.date is already a string in YYYY-MM-DD format
            return (0, match.date)

        sorted_matches = sorted(matches, key=sort_key)

        # Group by date, but convert string dates to datetime objects
        grouped = []
        for date, group in groupby(sorted_matches, key=lambda m: m.date):
            # Convert string dates to datetime objects for proper formatting
            if date and isinstance(date, str):
                try:
                    # Parse string date to datetime object
                    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                    grouped.append((date_obj, list(group)))
                except ValueError:
                    # If parsing fails, keep as string
                    grouped.append((date, list(group)))
            else:
                # Keep datetime objects or None as-is
                grouped.append((date, list(group)))

        return grouped

    def format_times_compact(times_list):
        """Format times in a more compact way"""
        if not times_list:
            return "No times"

        if len(times_list) == 1:
            return times_list[0]

        # For multiple times, show range if consecutive or list if not
        if len(times_list) == 2:
            return f"{times_list[0]}-{times_list[1]}"

        # For 3+ times, show first and last with count
        return f"{times_list[0]}+{len(times_list)-1} more"

    def unique_filter(items):
        """Return unique items from a list while preserving order"""
        if not items:
            return []

        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def count_lines_at_time(scheduled_times, target_time):
        """Count how many lines are scheduled at a specific time"""
        if not scheduled_times or not target_time:
            return 0
        return scheduled_times.count(target_time)

    def format_date(date_value, format_string='%Y-%m-%d'):
        """Format a date string or datetime object using strftime"""
        if not date_value:
            return "TBD"
        
        if isinstance(date_value, str):
            try:
                # Parse string date to datetime object
                date_obj = datetime.strptime(date_value, "%Y-%m-%d")
                return date_obj.strftime(format_string)
            except ValueError:
                return date_value  # Return as-is if parsing fails
        elif hasattr(date_value, 'strftime'):
            # Already a datetime/date object
            return date_value.strftime(format_string)
        else:
            return str(date_value)

    # Register the filter
    app.jinja_env.filters["compact_times"] = format_times_compact
    app.jinja_env.filters["unique"] = unique_filter
    app.jinja_env.filters["count_lines_at_time"] = count_lines_at_time
    app.jinja_env.filters["format_date"] = format_date

    # Register filters with the Flask app
    app.jinja_env.filters["format_weekday"] = format_weekday
    app.jinja_env.filters["groupby_date"] = group_matches_by_date


# ==================== HELPER FUNCTIONS ====================


def filter_matches(matches_list, start_date, end_date, search_query):
    """Filter matches based on date range and search query"""
    filtered_matches = matches_list

    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            # FIXED: Check that parse_match_date returns a valid date before comparison
            filtered_matches = [
                m
                for m in filtered_matches
                if m.date
                and parse_match_date(m.date) is not None
                and parse_match_date(m.date) >= start_date_obj
            ]
        except ValueError:
            pass  # Invalid date format, skip filter

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            # FIXED: Check that parse_match_date returns a valid date before comparison
            filtered_matches = [
                m
                for m in filtered_matches
                if m.date
                and parse_match_date(m.date) is not None
                and parse_match_date(m.date) <= end_date_obj
            ]
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
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            try:
                return datetime.strptime(date_value, "%m/%d/%Y").date()
            except ValueError:
                return None
    return None


def search_matches(matches_list, search_query):
    """Enhanced search functionality for matches with field-specific search"""
    if not search_query:
        return matches_list

    # Parse search query into field-specific and general terms
    search_terms = [
        term.lower().strip() for term in search_query.split() if term.strip()
    ]
    field_specific_terms = []
    general_terms = []

    for term in search_terms:
        if ":" in term:
            field_specific_terms.append(term.split(":", 1))
        else:
            general_terms.append(term)

    filtered_matches = []

    for match in matches_list:
        matches_query = True

        # Check field-specific terms
        for field, value in field_specific_terms:
            field_match = False

            if field in ["team", "teams"]:
                if (match.home_team and value in match.home_team.name.lower()) or (
                    match.visitor_team and value in match.visitor_team.name.lower()
                ):
                    field_match = True
            elif field in ["facility", "venue"]:
                if match.facility and value in match.facility.name.lower():
                    field_match = True
            elif field in ["league"]:
                if match.league and value in match.league.name.lower():
                    field_match = True
            elif field in ["date"]:
                if match.date and value in str(match.date).lower():
                    field_match = True
            elif field in ["status"]:
                if value in match.get_status().lower():
                    field_match = True
            elif field in ["captain"]:
                # Search in both team captains
                home_captain_match = (
                    match.home_team
                    and match.home_team.captain
                    and value in match.home_team.captain.lower()
                )
                visitor_captain_match = (
                    match.visitor_team
                    and match.visitor_team.captain
                    and value in match.visitor_team.captain.lower()
                )
                if home_captain_match or visitor_captain_match:
                    field_match = True
            elif field in ["division", "div"]:
                if (
                    match.league
                    and match.league.division
                    and value in match.league.division.lower()
                ):
                    field_match = True
            elif field in ["year"]:
                if (
                    match.league
                    and match.league.year
                    and value in str(match.league.year)
                ):
                    field_match = True

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

            combined_text = " ".join(searchable_text)

            for term in general_terms:
                if term not in combined_text:
                    matches_query = False
                    break

        if matches_query:
            filtered_matches.append(match)

    return filtered_matches


def _extract_common_scheduling_issues(errors):
    """Helper function to extract and categorize common scheduling issues"""
    if not errors:
        return []

    issue_counts = {}
    for error in errors:
        error_str = str(error).lower()

        # Categorize common issues
        if "no available" in error_str or "no slots" in error_str:
            issue_counts["No available time slots"] = (
                issue_counts.get("No available time slots", 0) + 1
            )
        elif "facility" in error_str and (
            "not found" in error_str or "unavailable" in error_str
        ):
            issue_counts["Facility unavailable"] = (
                issue_counts.get("Facility unavailable", 0) + 1
            )
        elif "conflict" in error_str or "overlap" in error_str:
            issue_counts["Scheduling conflict"] = (
                issue_counts.get("Scheduling conflict", 0) + 1
            )
        elif "team" in error_str and "unavailable" in error_str:
            issue_counts["Team unavailable"] = (
                issue_counts.get("Team unavailable", 0) + 1
            )
        else:
            issue_counts["Other scheduling issues"] = (
                issue_counts.get("Other scheduling issues", 0) + 1
            )

    # Return sorted list of issues by frequency
    return sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)


# Export the register function for use in main app
__all__ = ["register_routes"]
