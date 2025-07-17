"""
Flask Route Handler for Manual Match Scheduling
Fixed version with proper routes, data handling, and error handling
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from typing import Optional
import traceback
import math
from datetime import datetime, timedelta

from streamlit import success

from usta import League, Match, Facility, FacilityAvailabilityInfo, TimeSlotAvailability
from web_database import get_db, close_db
from scheduling_options import SchedulingOptions

# Ensure we have the correct imports

from typing import List, Dict, Any, Tuple

from sql_match_manager import SQLMatchManager


# Create blueprint for scheduling routes
schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/matches/<int:match_id>/schedule")
def schedule_match_form(match_id: int):
    """
    Display the manual scheduling form for a specific match
    Updated to use db.get_facility_availability properly
    """
    from web_database import get_db
    from datetime import datetime

    try:
        # Get database interface
        db = get_db()
        if db is None:
            flash("No database connection available", "danger")
            return redirect(url_for("matches"))

        # Get match object
        match = db.get_match(match_id)
        if not match:
            flash(f"Match with ID {match_id} not found", "danger")
            return redirect(url_for("matches"))

        league = match.league

        # Check if match is already scheduled
        if match.is_scheduled():
            facility_name = (
                match.facility.name if match.facility else "Unknown Facility"
            )
            flash(
                f"Match is already scheduled for {match.date} at {facility_name}",
                "info",
            )
            return redirect(url_for("view_match", match_id=match_id))


        # Validate that match has a facility (prefer match facility, fall back to home team facility)
        facility = match.get_facility()
        if not facility and match.home_team:
            facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None
        
        if not facility:
            flash("No facility available for this match. Please assign a facility to the home team.", "warning")
            return redirect(url_for("matches"))

        # Use the new SchedulingOptions class to get comprehensive scheduling data
        try:
            from scheduling_manager import SchedulingManager
            scheduling_manager = SchedulingManager(db)
            scheduling_options = scheduling_manager.get_scheduling_options(
                match=match, max_dates=20
            )
            
            # Check if we have any scheduling options
            if not scheduling_options.has_any_options():
                available_dates = []
                print("No scheduling options found for this match")
            else:
                # Use the built-in to_dict method to get template-compatible data
                scheduling_data = scheduling_options.to_dict()
                available_dates = scheduling_data.get('available_dates', [])
                
                # Add existing matches information to each date option
                for date_option in available_dates:
                    try:
                        existing_matches = get_existing_matches_on_date(db, facility, date_option['date'])
                        date_option['existing_matches'] = existing_matches
                    except Exception as e:
                        print(f"Error getting existing matches for {date_option['date']}: {e}")
                        date_option['existing_matches'] = []
                
                print(f"Found {len(available_dates)} scheduling options using SchedulingOptions class")
            
        except Exception as e:
            print(f"Error getting scheduling options: {e}")
            available_dates = []

        # Prepare match_info for template
        match_info = {
            "id": match.id,
            "home_team": match.home_team.name if match.home_team else "Unknown",
            "visitor_team": match.visitor_team.name if match.visitor_team else "Unknown", 
            "round": match.round,
            "num_rounds": match.num_rounds,
            "league": match.league.name if match.league else "Unknown League",
            "lines_needed": match.league.num_lines_per_match if match.league else 3
        }
        
        # Prepare facility_info for template (use the facility we determined earlier)
        facility_info = None
        if facility:
            facility_info = {
                "id": facility.id,
                "name": facility.name,
                "location": facility.location
            }

        # Render the scheduling form with available dates
        return render_template(
            "schedule_match.html",
            success=True,
            match=match,
            match_info=match_info,
            league=league,
            available_dates=available_dates,
            facility=facility,
            facility_info=facility_info,
            num_lines_per_match=league.num_lines_per_match,
            allow_split_lines=league.allow_split_lines,
        )
    except Exception as e:
        traceback.print_exc()
        flash(f"Error loading scheduling form: {str(e)}", "danger")
        return redirect(url_for("matches"))


# ====== Helper Functions for Scheduling Logic ======


def check_team_conflicts(db, match, date):
    """Simple team conflict checking using SchedulingManager"""
    from scheduling_manager import SchedulingManager
    scheduling_manager = SchedulingManager(db)
    
    # Check for team conflicts on the specific date
    team_conflict_dates = scheduling_manager.filter_team_conflicts(match, [date])
    if not team_conflict_dates:
        return f"Team conflict detected on {date}"
    
    return None


def get_existing_matches_on_date(db, facility, date):
    """Get existing matches scheduled at the facility on the given date"""
    try:
        # Get all matches on this date at this facility
        existing_matches = db.list_matches(facility=facility, date_str=date)

        # Convert to format suitable for template display
        match_info = []
        for match in existing_matches:
            if match.is_scheduled():
                match_info.append(
                    {
                        "id": match.id,
                        "home_team": match.home_team.name,
                        "visitor_team": match.visitor_team.name,
                        "league": match.league.name if match.league else "Unknown",
                        "scheduled_times": match.scheduled_times,
                        "earliest_time": match.get_earliest_time(),
                        "latest_time": match.get_latest_time(),
                        "num_lines": len(match.scheduled_times),
                    }
                )

        return match_info

    except Exception as e:
        print(f"Error getting existing matches on {date}: {e}")
        return []


def get_priority_label(priority: int) -> str:
    """
    Convert numeric priority to human-readable label

    Args:
        priority: Integer priority (lower number = higher priority)

    Returns:
        Human-readable priority label
    """
    if priority == 1:
        return "Ideal (Teams require, League prefers, In round)"
    elif priority == 2:
        return "Good (Teams require, League allows, In round)"
    elif priority == 3:
        return "Preferred (League prefers, In round)"
    elif priority == 4:
        return "Acceptable (League backup, In round)"
    elif priority <= 14:  # Out of round priorities (1-4 + 10)
        if priority == 11:
            return "Ideal (Teams require, League prefers, Out of round)"
        elif priority == 12:
            return "Good (Teams require, League allows, Out of round)"
        elif priority == 13:
            return "Preferred (League prefers, Out of round)"
        elif priority == 14:
            return "Acceptable (League backup, Out of round)"
        else:
            return "Available (Out of round)"
    else:
        return "Available"


# ======= Enhanced API Endpoint for Match Scheduling =======


# API endpoint to handle match scheduling with enhanced split times support
@schedule_bp.route("/api/schedule/match", methods=["POST"])
def api_schedule_match():
    """Simplified API endpoint using enhanced database validation"""
    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        match_id = data.get("match_id")
        facility_id = data.get("facility_id")
        date = data.get("date")
        times = data.get("times", [])
        scheduling_mode = data.get(
            "scheduling_mode", "same_time"
        )  # Default to 'same_time' if not provided
        if scheduling_mode not in ["same_time", "split_times", "custom"]:
            return jsonify({"success": False, "error": "Invalid scheduling mode"})

        # Basic validation
        if not all([match_id, date, times]):
            return jsonify({"success": False, "error": "Missing required fields"})

        # Get objects
        match = db.get_match(match_id)
        if not match:
            return jsonify({"success": False, "error": "Match not found"})

        facility = None
        if facility_id:
            try:
                facility_id = int(facility_id)
                if facility_id > 0:
                    facility = db.get_facility(facility_id)
            except (ValueError, TypeError):
                # Invalid facility_id, will fall back to home team facility
                pass
        if not facility and match.home_team:
            facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None
        if not facility:
            return jsonify({"success": False, "error": "No facility available"})

        # Check team conflicts (existing logic)
        team_conflict_error = check_team_conflicts(db, match, date)
        if team_conflict_error:
            return jsonify({"success": False, "error": team_conflict_error})

        # Create MatchScheduling object and assign it to the match
        from usta_match import MatchScheduling
        
        # Prepare the scheduled times based on the mode
        lines_needed = match.league.num_lines_per_match if match.league else 3
        
        if scheduling_mode == "same_time":
            if not times:
                return jsonify({"success": False, "error": "No times provided"})
            # For same_time mode, all lines use the same time
            scheduled_times = [times[0]] * lines_needed
            
        elif scheduling_mode == "split_times":
            if len(times) < 2:
                return jsonify({"success": False, "error": "Split times mode requires at least 2 time slots"})
            # For split_times mode, distribute lines across the provided times
            # Typically split into two groups, but handle multiple times if provided
            scheduled_times = []
            lines_per_time = lines_needed // len(times)
            extra_lines = lines_needed % len(times)
            
            for i, time in enumerate(times):
                # Add base lines for this time slot
                lines_for_this_time = lines_per_time
                # Distribute any extra lines to the first time slots
                if i < extra_lines:
                    lines_for_this_time += 1
                scheduled_times.extend([time] * lines_for_this_time)
                
        elif scheduling_mode == "custom":
            # For custom mode, we need exactly lines_needed time values
            if len(times) != lines_needed:
                return jsonify({
                    "success": False, 
                    "error": f"Custom mode requires exactly {lines_needed} time slots (one per line), got {len(times)}"
                })
            scheduled_times = times
            
        else:
            return jsonify({"success": False, "error": f"Unknown scheduling mode: {scheduling_mode}"})
        
        # Create MatchScheduling object and assign it
        match_scheduling = MatchScheduling(
            facility=facility,
            date=date,
            scheduled_times=scheduled_times,
            qscore=0  # Default quality score, could be calculated if needed
        )
        match.assign_scheduling(match_scheduling)

        # Save to database using SchedulingManager
        from scheduling_manager import SchedulingManager
        scheduling_manager = SchedulingManager(db)
        success = scheduling_manager.schedule_match(match)
        
        if success:
            result = {
                "success": True,
                "message": f"Match scheduled for {date} at {facility.name}",
                "match_id": match.id,
                "date": date,
                "facility": facility.name,
                "times": times
            }
        else:
            result = {"success": False, "error": "Failed to save match scheduling to database"}

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"})


@schedule_bp.route("/api/schedule/facility-availability/<int:facility_id>/<date>")
def api_facility_availability(facility_id: int, date: str):
    """
    API endpoint to get detailed facility availability for a specific date
    """
    from web_database import get_db

    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        facility = db.facility_manager.get_facility(facility_id)
        if not facility:
            return jsonify({"success": False, "error": "Facility not found"})

        # Get facility availability using db.get_facility_availability
        try:
            facility_availability_list = db.facility_manager.get_facility_availability(
                facility=facility, dates=[date], max_days=1
            )

            if facility_availability_list and len(facility_availability_list) > 0:
                facility_info = facility_availability_list[0]

                if facility_info.available:
                    # Extract available and busy times
                    available_times = [
                        slot.time
                        for slot in facility_info.time_slots
                        if slot.has_availability()
                    ]
                    busy_times = [
                        slot.time
                        for slot in facility_info.time_slots
                        if slot.is_fully_booked()
                    ]

                    availability = {
                        "available_times": available_times,
                        "busy_times": busy_times,
                        "time_slots": [
                            slot.to_dict() for slot in facility_info.time_slots
                        ],
                        "overall_utilization": facility_info.overall_utilization_percentage,
                        "total_court_slots": facility_info.total_court_slots,
                        "available_court_slots": facility_info.available_court_slots,
                        "message": f"Found {len(available_times)} available time slots",
                    }
                else:
                    availability = {
                        "available_times": [],
                        "busy_times": [],
                        "message": facility_info.reason
                        or "Facility not available on this date",
                    }
            else:
                availability = {
                    "available_times": [],
                    "busy_times": [],
                    "message": "No availability information found for this date",
                }

        except Exception as e:
            availability = {
                "available_times": [],
                "busy_times": [],
                "message": f"Error checking availability: {str(e)}",
            }

        return jsonify({"success": True, "availability": availability})

    except Exception as e:
        return jsonify(
            {
                "success": False,
                "error": f"Error getting facility availability: {str(e)}",
            }
        )


@schedule_bp.route("/matches/<int:match_id>/schedule/refresh-options")
def refresh_scheduling_options(match_id: int):
    """
    Refresh scheduling options with different parameters
    """
    from web_database import get_db

    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        # Get match object
        match = db.get_match(match_id)
        if not match:
            return jsonify({"success": False, "error": "Match not found"})

        # Get parameters from request
        facility_id = request.args.get("facility_id", type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        max_dates = int(request.args.get("max_dates", 20))

        # Get facility
        facility = None
        if facility_id:
            try:
                facility_id = int(facility_id)
                if facility_id > 0:
                    facility = db.get_facility(facility_id)
            except (ValueError, TypeError):
                # Invalid facility_id, will fall back to home team facility
                pass

        if not facility and match.home_team:
            facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None

        if not facility:
            return jsonify(
                {"success": False, "error": "No facility available for this match"}
            )

        # Get fresh scheduling options using SchedulingManager
        from scheduling_manager import SchedulingManager
        scheduling_manager = SchedulingManager(db)
        
        scheduling_options = scheduling_manager.get_scheduling_options(
            match=match,
            max_dates=max_dates
        )
        
        # Convert to the expected JSON format
        if scheduling_options.has_any_options():
            scheduling_data = scheduling_options.to_dict()
            result = {
                "success": True,
                "available_dates": scheduling_data.get('available_dates', []),
                "search_params": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "max_dates": max_dates,
                }
            }
        else:
            result = {
                "success": False,
                "available_dates": [],
                "error": "No scheduling options found for this match"
            }

        return jsonify(result)

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Error refreshing options: {str(e)}"}
        )


@schedule_bp.route("/api/schedule/match/preview", methods=["POST"])
def api_preview_schedule_match():
    """Simplified preview endpoint"""
    try:
        db = get_db()
        if db is None:
            return jsonify(
                {"success": False, "error": "No database connection available"}
            )

        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        match_id = data.get("match_id")
        facility_id = data.get("facility_id")
        date = data.get("date")
        times = data.get("times", [])
        scheduling_mode = data.get("scheduling_mode", "custom")

        # Basic validation
        if not all([match_id, date, times]):
            return jsonify({"success": False, "error": "Missing required fields"})

        # Get objects
        match = db.get_match(match_id)
        if not match:
            return jsonify({"success": False, "error": "Match not found"})

        facility = None
        if facility_id:
            try:
                facility_id = int(facility_id)
                if facility_id > 0:
                    facility = db.get_facility(facility_id)
            except (ValueError, TypeError):
                # Invalid facility_id, will fall back to home team facility
                pass
        
        if not facility and match.home_team:
            facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None
        
        if not facility:
            return jsonify({"success": False, "error": "No facility available"})

        # Use the SchedulingManager preview method
        from scheduling_manager import SchedulingManager
        scheduling_manager = SchedulingManager(db)
        result = scheduling_manager.preview_match_scheduling(
            match=match, date=date, times=times, scheduling_mode=scheduling_mode, facility=facility
        )

        # Return the preview result with success flag
        return jsonify(
            {
                "success": True,
                "preview": result,
                "can_schedule": result.get("schedulable", False),
            }
        )

    except Exception as e:
        return jsonify(
            {"success": False, "error": f"Error previewing schedule: {str(e)}"}
        )


# Add to the route registration function
def add_scheduling_routes_to_app(app):
    """
    Register all scheduling routes with the Flask app
    Enhanced with split times support
    """
    # Register the blueprint
    app.register_blueprint(schedule_bp)

    # Add any additional configuration for split times
    app.config.setdefault("TENNIS_SPLIT_TIMES_ENABLED", True)
    app.config.setdefault("TENNIS_SPLIT_TIMES_MIN_GAP_HOURS", 1)
    app.config.setdefault(
        "TENNIS_SPLIT_TIMES_DEFAULT_DISTRIBUTION", "balanced"
    )  # or 'majority_first'


# ======== Scheduling Options Retrieval ========


# Legacy functions removed - now using SchedulingManager.get_scheduling_options exclusively


def format_date_for_display(date_str):
    """Format date string for display in template"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%B %d, %Y")
    except ValueError:
        return date_str


# Alternative manual scheduling functions for direct use


def get_match_scheduling_data(match_id: int, facility_id: Optional[int] = None) -> dict:
    """
    Get scheduling data for a match (for use in other contexts)

    Args:
        match_id: Match ID to get scheduling options for
        facility_id: Optional facility ID (defaults to home team's facility)

    Returns:
        Dictionary with scheduling data
    """
    from web_database import get_db

    try:
        db = get_db()
        if db is None:
            return {"success": False, "error": "No database connection available"}
        match = db.get_match(match_id)
        if not match:
            return {"success": False, "error": "Match not found"}

        facility = None
        if facility_id:
            facility = db.get_facility(facility_id)

        if not facility and match.home_team:
            facility = match.home_team.get_primary_facility() if match.home_team.preferred_facilities else None

        if not facility:
            return {"success": False, "error": "No facility available"}

        # Use SchedulingManager for scheduling options
        from scheduling_manager import SchedulingManager
        scheduling_manager = SchedulingManager(db)
        
        scheduling_options = scheduling_manager.get_scheduling_options(match=match)
        
        # Convert to expected dictionary format
        if scheduling_options.has_any_options():
            scheduling_data = scheduling_options.to_dict()
            return {
                "success": True,
                "available_dates": scheduling_data.get('available_dates', []),
            }
        else:
            return {
                "success": False, 
                "error": "No scheduling options found for this match",
                "available_dates": []
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# Example usage in a Flask app setup
"""
# In your main Flask app file:

from web_schedule_match import add_scheduling_routes_to_app

app = Flask(__name__)

# Add the scheduling routes to your app
add_scheduling_routes_to_app(app)

# Now the following routes will be available:
# GET  /matches/<match_id>/schedule  - Show scheduling form
# POST /api/schedule/match         - Schedule the match
# GET  /api/schedule/facility-availability/<facility_id>/<date> - Check availability
# GET  /matches/<match_id>/schedule/refresh-options - Refresh scheduling options
"""
