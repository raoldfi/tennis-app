# Tennis Database Export Guide

This guide explains how to export data from the tennis scheduling database to YAML and Excel formats.

## Overview

The export functionality allows you to:
- Export all database records or specific components (leagues, facilities, teams, matches)
- Choose between YAML (human-readable) and Excel (spreadsheet) formats
- Filter exports by league
- Auto-detect format from file extension

## Command Line Interface

### Basic Usage

```bash
python simple_cli.py --db-path tennis.db export <output_file> [options]
```

### Common Export Scenarios

#### 1. Export Everything

```bash
# Export to YAML (auto-detected from extension)
python simple_cli.py --db-path tennis.db export database_backup.yaml

# Export to Excel
python simple_cli.py --db-path tennis.db export database_backup.xlsx
```

#### 2. Export Specific Components

```bash
# Export only leagues
python simple_cli.py --db-path tennis.db export leagues.yaml --components leagues

# Export leagues and teams
python simple_cli.py --db-path tennis.db export leagues_teams.xlsx --components leagues teams

# Export all components explicitly
python simple_cli.py --db-path tennis.db export full_export.yaml --components all
```

#### 3. Export by League

```bash
# Export all data for league ID 1
python simple_cli.py --db-path tennis.db export league_1.yaml --components all --league-id 1

# Export only matches for league ID 1
python simple_cli.py --db-path tennis.db export league_1_matches.xlsx --components matches --league-id 1

# Export teams and matches for league ID 2
python simple_cli.py --db-path tennis.db export league_2_data.yaml --components teams matches --league-id 2
```

#### 4. YAML with Metadata

```bash
# Include export timestamp and metadata in YAML export
python simple_cli.py --db-path tennis.db export export_with_metadata.yaml --include-metadata
```

## Python API

### Using TennisExporter Class

```python
from tennis_db_factory import TennisDBFactory, DatabaseBackend, TennisDBManager
from tennis_export import TennisExporter

# Connect to database
backend = DatabaseBackend('sqlite')
config = {'db_path': 'tennis.db'}
db_manager = TennisDBManager(backend, config)
db = db_manager.connect()

# Create exporter
exporter = TennisExporter(db)

# Export everything to YAML
stats = exporter.export_to_yaml(
    file_path='database_backup.yaml',
    components=['leagues', 'facilities', 'teams', 'matches'],
    include_metadata=True
)
print(f"Exported {stats['total']} records")

# Export to Excel with filtering
stats = exporter.export_to_excel(
    file_path='league_1.xlsx',
    components=['teams', 'matches'],
    league_id=1
)
print(f"Created {len(stats['sheets'])} Excel sheets")

# Auto-detect format
stats = exporter.export(
    file_path='export.yaml',  # .yaml = YAML format
    format='auto',
    components=['leagues', 'teams']
)
```

## Export Formats

### YAML Format

**Features:**
- Human-readable text format
- Preserves full data structure including schedules and availability
- Can be edited manually and re-imported
- Optional metadata section with export timestamp
- Compatible with version control systems

**Structure:**
```yaml
metadata:
  export_timestamp: '2025-01-23T10:30:00'
  format_version: '1.0'
  components: ['leagues', 'facilities', 'teams', 'matches']

leagues:
  - id: 1
    name: "Spring 2025 League"
    year: 2025
    # ... more fields

facilities:
  - id: 1
    name: "Tennis Center North"
    # ... more fields

teams:
  - id: 1
    name: "Team A"
    # ... more fields

matches:
  - id: 1
    league_id: 1
    # ... more fields
```

### Excel Format

**Features:**
- Spreadsheet format for easy viewing and analysis
- Separate sheets for each component (Leagues, Facilities, Teams, Matches)
- Auto-adjusted column widths
- Human-readable field names
- List fields converted to comma-separated strings

**Sheets:**
- **Leagues**: All league information with flattened fields
- **Facilities**: Basic facility info (without detailed schedules)
- **Teams**: Team data with league names and home facility names
- **Matches**: Match data with status, team names, and scheduling info

**Requirements:**
Excel export requires additional Python packages:
```bash
pip install pandas openpyxl
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `file_path` | Output file path (required) | - |
| `--format` | Export format: `yaml`, `excel`, or `auto` | `auto` |
| `--components` | Components to export: `leagues`, `facilities`, `teams`, `matches`, `all` | `all` |
| `--league-id` | Filter teams and matches by league ID | None |
| `--include-metadata` | Include metadata section (YAML only) | False |

## Examples by Use Case

### 1. Backup Entire Database

```bash
# YAML backup (can be re-imported)
python simple_cli.py --db-path tennis.db export backup_$(date +%Y%m%d).yaml --include-metadata

# Excel backup (for viewing/analysis)
python simple_cli.py --db-path tennis.db export backup_$(date +%Y%m%d).xlsx
```

### 2. Share League Schedule

```bash
# Export all data for a specific league to share with captains
python simple_cli.py --db-path tennis.db export 2025_spring_league.xlsx \
    --components teams matches --league-id 5
```

### 3. Archive Completed Season

```bash
# Export everything for archive
python simple_cli.py --db-path tennis.db export 2024_fall_archive.yaml \
    --include-metadata
```

### 4. Extract Reference Data

```bash
# Export just facilities for planning
python simple_cli.py --db-path tennis.db export facilities_list.xlsx \
    --components facilities

# Export leagues for reporting
python simple_cli.py --db-path tennis.db export leagues_2025.yaml \
    --components leagues
```

### 5. Migrate Data

```bash
# Export from source database
python simple_cli.py --db-path source.db export migration_data.yaml

# Import to destination database
python simple_cli.py --db-path destination.db load migration_data.yaml --execute
```

## Export Statistics

Both YAML and Excel exports return statistics:

```
✅ Export completed successfully!
   Format: YAML
   Leagues: 10
   Facilities: 25
   Teams: 80
   Matches: 400
   Total: 515 records
   Duration: 1.23 seconds
```

For Excel exports, you also get the sheet names:
```
   Excel sheets: Leagues, Facilities, Teams, Matches
```

## Troubleshooting

### Excel Export Fails

**Error:** `ImportError: Excel export requires pandas and openpyxl libraries`

**Solution:**
```bash
pip install pandas openpyxl
```

### Permission Denied

**Error:** `Permission denied: 'export.yaml'`

**Solution:** Ensure you have write permissions for the output directory or the file is not open in another program.

### Invalid Components

**Error:** `Invalid components: {'invalid'}`

**Solution:** Use only valid component names: `leagues`, `facilities`, `teams`, `matches`, or `all`

### League Not Found

If you specify `--league-id` but the league doesn't exist, teams and matches for that league will be empty (0 records).

## Tips

1. **Use YAML for backups and migrations** - YAML files can be re-imported with full fidelity
2. **Use Excel for viewing and analysis** - Excel is better for non-technical users and quick reviews
3. **Include metadata in YAML exports** - Helps track when and what was exported
4. **Filter by league for focused exports** - Reduces file size and focuses on relevant data
5. **Auto-detect format** - Let the tool determine format from file extension (`.yaml` or `.xlsx`)

## Integration with Import

Export and import work seamlessly together:

```bash
# Export from production database
python simple_cli.py --db-path production.db export backup.yaml --include-metadata

# Import to test database (dry-run first)
python simple_cli.py --db-path test.db load backup.yaml

# Actually import
python simple_cli.py --db-path test.db load backup.yaml --execute
```

## See Also

- [CLAUDE.md](CLAUDE.md) - Full application documentation
- [testing/matches_template.yaml](testing/matches_template.yaml) - Match import template
- [testing/league_template.yaml](testing/league_template.yaml) - League import template
- [testing/facility_template.yaml](testing/facility_template.yaml) - Facility import template
