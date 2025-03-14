# CLAUDE.md for Lineup Baseball Manager

## Build & Run Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run lineup.py
```

## Database Setup
```bash
# Set DATABASE_URL in .env file:
# DATABASE_URL=postgresql://username:password@localhost/lineup
```

## Code Style Guidelines
- **Imports**: Group standard library, third-party, and local imports
- **Formatting**: Use 4 spaces for indentation
- **Naming**: snake_case for variables/functions, CamelCase for classes
- **Types**: Use type hints where appropriate
- **Error handling**: Use try/except blocks with specific exceptions
- **Constants**: Define constants at the top of files in UPPERCASE

## Key application constants
```python
POSITIONS = ["Pitcher", "Catcher", "1B", "2B", "3B", "SS", "LF", "RF", "LC", "RC", "Bench"]
INFIELD = ["Pitcher", "1B", "2B", "3B", "SS"]
OUTFIELD = ["Catcher", "LF", "RF", "LC", "RC"]
BENCH = ["Bench"]
```