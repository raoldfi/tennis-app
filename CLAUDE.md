# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the Application

**Web Application:**
```bash
# Simple startup (configure database through web interface)
python web_app.py

# Pre-configured startup with database
python start_tennis_app.py --backend sqlite --db-path tennis.db

# Debug mode
python start_tennis_app.py --backend sqlite --db-path tennis.db --debug
```

**CLI Operations:**
```bash
# CLI operations use dry-run by default - add --execute to actually perform changes
python simple_cli.py --db-path tennis.db <command>

# Common commands
python simple_cli.py --db-path tennis.db list leagues
python simple_cli.py --db-path tennis.db load facilities.yaml --execute
python simple_cli.py --db-path tennis.db generate-matches --league-id 1 --execute
python simple_cli.py --db-path tennis.db auto-schedule --execute
python simple_cli.py --db-path tennis.db test --comprehensive
```

### Development Tools

**Type Checking:**
```bash
mypy .
```

**Testing:**
```bash
# Built-in testing via CLI
python simple_cli.py --db-path tennis.db test --comprehensive
```

## Architecture

### Core Design Pattern
This is a **tennis league scheduling application** using an **interface-based architecture** with pluggable database backends:

- **TennisDBInterface** - Abstract interface defining all database operations
- **SQLiteTennisDB** - SQLite implementation with specialized managers
- **TennisDBFactory** - Factory for creating database instances

### Key Components

**USTA Data Models** (`usta/` package):
- `League` - USTA league (year, section, region, age group, division)
- `Team` - Teams belonging to leagues with home facilities
- `Facility` - Tennis facilities with complex scheduling availability
- `Match` - Individual matches with scheduling state management

**Database Managers** (handle specific entity operations):
- `SQLTeamManager` - Team CRUD operations
- `SQLLeagueManager` - League management
- `SQLFacilityManager` - Facility and availability management
- `SQLMatchManager` - Match creation and scheduling
- `SchedulingManager` - Generic auto-scheduling algorithms using TennisDBInterface

**Interfaces**:
- **Web Interface** - Flask app with Bootstrap templates
- **CLI Interface** - Comprehensive command-line tool with dry-run support

### Data Flow
1. **Web**: Flask routes → Database managers → SQLite
2. **CLI**: Command handlers → Database managers → SQLite
3. **Import**: YAML validation → Bulk operations → Database

### Match Scheduling
The application includes sophisticated scheduling logic:
- **Facility availability** - Complex weekly schedules with court counts and blackout dates
- **Conflict detection** - Prevents double-booking teams or facilities
- **Auto-scheduling** - Algorithms to automatically place matches within constraints
- **Dry-run mode** - Preview changes before execution

### Database Schema
- **leagues** - Tournament leagues with USTA classifications
- **facilities** - Tennis venues with scheduling availability
- **teams** - Team rosters with home facilities
- **matches** - Individual matches with scheduling state (Unscheduled → Scheduled → Completed)

## Development Notes

### Type Safety
- Strict mypy configuration in `mypy.ini`
- All functions should have type hints
- Use `from typing import` for complex types

### CLI Safety
- All mutating CLI operations default to dry-run mode
- Always add `--execute` flag for actual changes
- Use `test` command for validation

### Data Import/Export
- Use YAML format for data import/export
- Test data available in `testing/` directory
- Import validation prevents invalid data

### Web Development
- Templates use Bootstrap for styling
- Database connection managed via `web_database.py`
- All routes should handle database connection errors gracefully

## Dependencies
- **Flask** - Web framework
- **PyYAML** - YAML file processing
- **SQLite** - Database (no external server required)
- **Python 3.8+** - Required for type hints and features used