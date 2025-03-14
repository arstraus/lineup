import streamlit as st

# Set page config must be the first Streamlit command
st.set_page_config(
    page_title="LineupBoss",
    page_icon="⚾",
    layout="wide"
)

import pandas as pd
import numpy as np
import io
import base64
import json
import requests
import time
import os
from dotenv import load_dotenv
import db_operations as db
import database

# Define positions (keep these as constants)
POSITIONS = ["Pitcher", "Catcher", "1B", "2B", "3B", "SS", "LF", "RF", "LC", "RC", "Bench"]
INFIELD = ["Pitcher", "1B", "2B", "3B", "SS"]
OUTFIELD = ["Catcher", "LF", "RF", "LC", "RC"]
BENCH = ["Bench"]

# Load environment variables
load_dotenv()

# Initialize session state for UI elements and temporary data
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Team Setup"
if 'team_id' not in st.session_state:
    st.session_state.team_id = None
if 'upload_roster_flag' not in st.session_state:
    st.session_state.upload_roster_flag = False
if 'claude_fielding_plan' not in st.session_state:
    st.session_state.claude_fielding_plan = None
if 'claude_fielding_stats' not in st.session_state:
    st.session_state.claude_fielding_stats = None
if 'claude_fielding_reasoning' not in st.session_state:
    st.session_state.claude_fielding_reasoning = None
if 'claude_validation_warning' not in st.session_state:
    st.session_state.claude_validation_warning = None
    
# User authentication state
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'is_authenticated' not in st.session_state:
    st.session_state.is_authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# Helper Functions
def get_csv_download_link(df, filename, link_text):
    """Generate a link to download the dataframe as a CSV file"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{link_text}</a>'
    return href

def create_empty_roster_template(num_players=14):
    """Create an empty roster template with specified number of players"""
    data = {
        "First Name": [""] * num_players,
        "Last Name": [""] * num_players,
        "Jersey Number": [""] * num_players
    }
    return pd.DataFrame(data)

def validate_roster(df):
    """Validate the uploaded roster file"""
    required_columns = ["First Name", "Last Name", "Jersey Number"]
    
    # Check if all required columns exist
    if not all(col in df.columns for col in required_columns):
        return False, "Roster must contain columns: First Name, Last Name, and Jersey Number"
    
    # Check if there are any missing values
    if df[required_columns].isna().any().any():
        return False, "Roster contains missing values"
    
    # Check if jersey numbers are unique
    if df["Jersey Number"].duplicated().any():
        return False, "Jersey numbers must be unique"
    
    return True, "Roster is valid"

def get_all_teams(include_details=False):
    """Get all teams from the database
    
    Args:
        include_details (bool): If True, returns additional team information
        
    Returns:
        list: List of teams with either (id, name) or detailed information
    """
    session = database.get_db_session()
    try:
        teams = session.query(database.Team).all()
        if include_details:
            return [{
                "id": team.id, 
                "name": team.name,
                "league": team.league,
                "head_coach": team.head_coach
            } for team in teams]
        return [(team.id, team.name) for team in teams]
    finally:
        session.close()

def delete_team(team_id):
    """Delete a team and all its associated data from the database"""
    session = database.get_db_session()
    try:
        # Find the team
        team = session.query(database.Team).filter(database.Team.id == team_id).one()
        
        # Store name for confirmation message
        team_name = team.name
        
        # The cascading delete set up in the database models should handle
        # deleting all the related data (players, games, etc.)
        session.delete(team)
        session.commit()
        
        return True, team_name
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def generate_game_plan_pdf(team_id, game_number):
    """Generate a PDF with the game plan"""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    import io
    
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    
    # Get game information
    game_schedule = db.get_schedule(team_id)
    filtered_games = game_schedule[game_schedule["Game #"] == game_number]
    
    # Validate game exists
    if filtered_games.empty:
        raise ValueError(f"Game {game_number} not found in schedule")
    
    game_info = filtered_games.iloc[0]
    
    # Get team info
    team_info = db.get_team_info(team_id)
    
    # Get roster with validation
    roster_df = db.get_roster(team_id)
    if roster_df.empty:
        raise ValueError("Team roster is empty")
    
    # Get batting order with validation
    batting_orders = db.get_batting_orders(team_id)
    batting_order = batting_orders.get(game_number, [])
    
    # Get fielding rotations with validation
    fielding_rotations = db.get_fielding_rotations(team_id)
    fielding_data = fielding_rotations.get(game_number, {})
    
    # Get player availability
    player_availability = db.get_player_availability(team_id)
    availability = {}
    if game_number in player_availability:
        availability = player_availability[game_number]["Available"]
    
    # Create the PDF document - using landscape for more horizontal space
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=0.5*inch, rightMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,  # Center
        spaceAfter=6
    )
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=6,
        spaceAfter=6
    )
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=9,
        leading=10
    )
    
    # Add game header
    elements.append(Paragraph(f"Game {game_number} Lineup", title_style))
    
    # Gather game details information
    team_name = team_info.get("team_name", "")
    league = team_info.get("league", "")
    head_coach = team_info.get("head_coach", "")
    asst_coaches = []
    if team_info.get("assistant_coach1"):
        asst_coaches.append(team_info["assistant_coach1"])
    if team_info.get("assistant_coach2"):
        asst_coaches.append(team_info["assistant_coach2"])
    
    opponent = game_info.get("Opponent", "Unknown")
    
    # Format date with validation
    try:
        date_str = game_info['Date'].strftime("%Y-%m-%d") if isinstance(game_info['Date'], pd.Timestamp) else str(game_info.get('Date', 'Not scheduled'))
    except (AttributeError, TypeError):
        date_str = "Not scheduled"
    
    # Format time with validation
    try:
        if "Time" in game_info and pd.notna(game_info["Time"]):
            time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else str(game_info["Time"])
            date_time = f"{date_str} at {time_str}"
        else:
            date_time = date_str
    except (AttributeError, TypeError):
        date_time = date_str
    
    # Get innings with default value
    innings = game_info.get("Innings", 6)
    
    # Create left-justified game details text
    details_style = ParagraphStyle(
        'Details',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=0.2*inch
    )
    
    # Format each line of details
    details_text = f"<b>Team:</b> {team_name}<br/>"
    if league:
        details_text += f"<b>League:</b> {league}<br/>"
    details_text += f"<b>Head Coach:</b> {head_coach}<br/>"
    if asst_coaches:
        details_text += f"<b>Assistant Coach(es):</b> {', '.join(asst_coaches)}<br/>"
    details_text += f"<b>Opponent:</b> {opponent}<br/>"
    details_text += f"<b>Date/Time:</b> {date_time}<br/>"
    details_text += f"<b>Innings:</b> {innings}"
    
    # Add the game details paragraph
    elements.append(Paragraph(details_text, details_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Create a mapping from jersey number to player info
    jersey_to_player = {}
    player_data = []
    
    for _, player in roster_df.iterrows():
        # Validate required columns exist
        if all(col in player for col in ["Jersey Number", "First Name", "Last Name"]):
            jersey = str(player["Jersey Number"])
            jersey_to_player[jersey] = player
            
            # Track batting order position
            try:
                batting_pos = batting_order.index(jersey) + 1 if jersey in batting_order else "-"
            except ValueError:
                batting_pos = "-"
            
            # Check availability
            is_available = availability.get(jersey, True)
            avail_text = "Yes" if is_available else "No"
            
            # Record player info for the main table
            player_data.append({
                "Jersey": jersey,
                "Name": f"{player.get('First Name', '')} {player.get('Last Name', '')}",
                "Batting": batting_pos,
                "Available": avail_text
            })
    
    # Sort player data by batting order, putting players not in the order at the end
    player_data.sort(key=lambda x: 999 if x["Batting"] == "-" else int(x["Batting"]))
    
    # Create the main table structure
    main_table_data = []
    
    # Create the header row
    header_row = ["Order", "Jersey #", "Player Name", "Available"]
    for i in range(1, innings + 1):
        header_row.append(f"Inning {i}")
    main_table_data.append(header_row)
    
    # Add each player's row
    for player in player_data:
        jersey = player["Jersey"]
        row = [
            player["Batting"],
            f"#{jersey}",
            player["Name"],
            player["Available"]
        ]
        
        # Add position for each inning
        for inning in range(1, innings + 1):
            inning_key = f"Inning {inning}"
            if inning_key in fielding_data and jersey in fielding_data[inning_key]:
                row.append(fielding_data[inning_key][jersey])
            else:
                row.append("-")
        
        main_table_data.append(row)
    
    # Create the main table with fixed width columns
    # Use a consistent column width for innings to prevent overlapping
    order_width = 0.5*inch    # Batting order
    jersey_width = 0.6*inch   # Jersey number
    name_width = 2.0*inch     # Player name
    avail_width = 0.7*inch    # Availability
    
    # Calculate inning width based on available space and number of innings
    page_width = 11.0*inch    # Landscape letter width
    used_width = order_width + jersey_width + name_width + avail_width
    margins = 1.0*inch        # Total left and right margins
    available_width = page_width - used_width - margins
    
    # Ensure a minimum width per inning column
    min_inning_width = 0.5*inch
    max_innings_that_fit = int(available_width / min_inning_width)
    
    # If we can't fit all innings at minimum width, we need to adjust
    if innings > max_innings_that_fit:
        inning_width = min_inning_width
    else:
        inning_width = available_width / innings
    
    # Create column widths array
    col_widths = [order_width, jersey_width, name_width, avail_width] + [inning_width] * innings
    
    # Create table with the calculated column widths
    main_table = Table(main_table_data, colWidths=col_widths, repeatRows=1)
    
    # Apply basic table styling without color coding
    table_style = [
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        
        # Content styling
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center order numbers
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),  # Center jersey numbers
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),  # Center availability
        ('ALIGN', (4, 0), (-1, -1), 'CENTER'),  # Center positions in innings
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # Thicker line below header
    ]
    
    main_table.setStyle(TableStyle(table_style))
    elements.append(main_table)
    
    # Add a small space before the legend
    elements.append(Spacer(1, 0.1*inch))
    
    # Create position legend
    legend_text = Paragraph("<b>Position Legend:</b> <i>Infield:</i> " + ", ".join(INFIELD) + 
                           " | <i>Outfield:</i> " + ", ".join(OUTFIELD) + 
                           " | <i>Other:</i> Bench, OUT", normal_style)
    elements.append(legend_text)
    
    # Add footer with small text
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("LineupBoss - Game Plan", 
                             ParagraphStyle('Footer', fontSize=7, textColor=colors.gray, alignment=1)))
    
    # Build the PDF
    try:
        doc.build(elements)
    except Exception as e:
        # Log the error but don't crash
        print(f"Error building PDF: {str(e)}")
        # Return empty buffer if building fails
        buffer = io.BytesIO()
        buffer.write(b"Error generating PDF")
        buffer.seek(0)
        return buffer
    
    # Get the PDF from the buffer
    buffer.seek(0)
    return buffer

# Function to prepare data for Claude API
def prepare_data_for_claude(team_id, selected_game):
    """Prepare all relevant data for Claude to generate a fielding rotation"""
    # Get player data
    roster_df = db.get_roster(team_id)
    
    # Get game info
    schedule_df = db.get_schedule(team_id)
    game_info = schedule_df[schedule_df["Game #"] == selected_game].iloc[0]
    innings = int(game_info["Innings"])
    
    # Get player availability
    player_availability = db.get_player_availability(team_id)
    
    # Default availability if not set
    availability = {"Available": {}, "Can Play Catcher": {}}
    if selected_game in player_availability:
        availability = player_availability[selected_game]
    
    # Create player details for Claude
    player_details = []
    for _, player in roster_df.iterrows():
        jersey = str(player["Jersey Number"])
        player_details.append({
            "name": f"{player['First Name']} {player['Last Name']}",
            "jersey": jersey,
            "available": bool(availability["Available"].get(jersey, True)),
            "can_play_catcher": bool(availability["Can Play Catcher"].get(jersey, False))
        })
    
    # Get current fielding positions if they exist
    fielding_rotations = db.get_fielding_rotations(team_id)
    current_positions = {}
    if selected_game in fielding_rotations:
        current_positions = fielding_rotations[selected_game]
    
    # Create fairness data from previous games
    game_ids = [g for g in fielding_rotations.keys() if g != selected_game]
    previous_rotations = {}
    for game_id in game_ids:
        previous_rotations[str(game_id)] = fielding_rotations[game_id]
    
    # Count available players and catchers
    available_players = sum(1 for p in player_details if p["available"])
    available_catchers = sum(1 for p in player_details if p["available"] and p["can_play_catcher"])
    
    # Create more structured data with required positions explicitly stated
    required_positions = [pos for pos in POSITIONS if pos != "Bench"]
    
    # Prepare the data with additional structure and information
    data = {
        "players": player_details,
        "game_info": {
            "game_id": int(selected_game),
            "opponent": str(game_info["Opponent"]),
            "innings": innings
        },
        "current_positions": current_positions,
        "previous_rotations": previous_rotations,
        "positions": POSITIONS,
        "required_positions": required_positions,
        "stats": {
            "total_players": len(player_details),
            "available_players": available_players,
            "available_catchers": available_catchers
        },
        "position_categories": {
            "infield": INFIELD,
            "outfield": OUTFIELD,
            "bench": BENCH
        }
    }
    
    return data

# Function to call Claude API
def generate_fielding_rotation(data):
    """Call Claude API to generate a fielding rotation plan with improved prompt and validation"""
    # Get Anthropic API key from Streamlit secrets or environment
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY not found in Streamlit secrets or environment variables"}, 400
    
    # Get required positions from the data with validation
    required_positions = []
    if isinstance(data, dict) and "positions" in data:
        required_positions = [pos for pos in data["positions"] if pos != "Bench"]
    
    if not required_positions:
        return {"error": "No required positions found in data"}, 400
    
    # Create prompt for Claude with more detailed requirements
    prompt = f"""
    You are an expert baseball coach assistant that specializes in creating fair and balanced fielding rotations.

    Please analyze the following data and create a fielding rotation plan with these STRICT requirements:

    1. MOST CRITICAL: In EVERY inning, ALL of these positions MUST be filled EXACTLY ONCE: {', '.join(required_positions)}
    2. Unavailable players (marked "available": false) MUST be marked as "OUT" in ALL innings
    3. "Catcher" position can ONLY be assigned to players marked as "can_play_catcher": true
    4. ALL positions must be assigned EXACTLY ONE player - no position can be left unfilled
    5. NO duplicate position assignments within the same inning
    6. NO player should play the SAME position more than once across ALL innings of a game
    7. NO player should play infield or outfield in CONSECUTIVE innings (they must alternate or have bench time in between)
       - Infield positions are: Pitcher, 1B, 2B, 3B, SS
       - Outfield positions are: Catcher, LF, RF, LC, RC
    8. STRICTLY BALANCE playing time:
       - Every available player should have nearly equal infield time (within 1 inning difference)
       - Every available player should have nearly equal outfield time (within 1 inning difference)
       - Only use bench if necessary (when there are more players than field positions)
       - Bench time should be evenly distributed across players (within 1 inning difference)
    9. DOUBLE CHECK that ALL of these positions are assigned in EVERY inning: {', '.join(required_positions)}

    Here is the data:
    {json.dumps(data, indent=2)}

    CRITICAL VALIDATION STEPS BEFORE ANSWERING:
    1. For each inning, make a checklist of all required positions: {', '.join(required_positions)}
    2. Verify that EVERY position has EXACTLY ONE player assigned to it in EVERY inning
    3. Verify unavailable players are marked as "OUT"
    4. Verify only capable players are assigned to "Catcher"
    5. Verify NO player plays the same position multiple times across all innings
    6. Verify NO player plays infield or outfield in consecutive innings

    Respond ONLY with a JSON object containing the fielding rotation plan. The format should be:
    {{
      "fielding_plan": {{
        "Inning 1": {{"jersey1": "position1", "jersey2": "position2", ...}},
        "Inning 2": {{"jersey1": "position1", "jersey2": "position2", ...}},
        ...
      }},
      "statistics": {{
        "jersey1": {{"infield": X, "outfield": Y, "bench": Z, "total": N}},
        "jersey2": {{"infield": X, "outfield": Y, "bench": Z, "total": N}},
        ...
      }},
      "reasoning": "Detailed explanation of how you ensured all positions are filled and playing time is balanced"
    }}
    """
    
    # Call Anthropic API
    try:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json={
                "model": "claude-3-sonnet-20240229",
                "max_tokens": 4000,
                "temperature": 0.2,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "system": "You are a helpful assistant that specializes in creating fair and balanced baseball fielding rotations. Your most important responsibility is to ensure that every required position has exactly one player assigned in every inning. Never leave any position unfilled. Respond only with valid JSON that follows the exact format specified."
            }
        )
        
        # Validate response status
        if response.status_code != 200:
            return {"error": f"API request failed with status {response.status_code}: {response.text}"}, response.status_code
            
        # Parse response with validation
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response from Claude API"}, 400
            
        # Validate response structure
        if not isinstance(response_data, dict) or "content" not in response_data:
            return {"error": "Unexpected response structure from Claude API"}, 400
            
        # Get content with validation
        content = response_data.get("content", [])
        if not isinstance(content, list) or len(content) == 0:
            return {"error": "Empty content in Claude API response"}, 400
            
        # Get text with validation
        first_content = content[0]
        if not isinstance(first_content, dict) or "text" not in first_content:
            return {"error": "Invalid content structure in Claude API response"}, 400
            
        ai_response = first_content.get("text", "")
        if not ai_response:
            return {"error": "Empty text in Claude API response"}, 400
                
        # Extract JSON from the response (in case there's extra text)
        try:
            import re
            json_match = re.search(r'({.*})', ai_response, re.DOTALL)
            if not json_match:
                return {"error": "Could not extract JSON from Claude's response"}, 400
                
            json_str = json_match.group(1)
            result = json.loads(json_str)
        except (json.JSONDecodeError, re.error) as e:
            return {"error": f"Failed to parse JSON from Claude's response: {str(e)}"}, 400
                
        # Validate result structure
        if not isinstance(result, dict):
            return {"error": "Invalid JSON structure in Claude's response"}, 400
            
        # Get fielding plan with validation
        fielding_plan = result.get("fielding_plan", {})
        if not isinstance(fielding_plan, dict):
            return {"error": "Invalid fielding plan structure"}, 400
            
        # Verify all required positions are filled in each inning and validate the new constraints
        valid_plan = True
        validation_errors = {}
        
        # Track positions played by each player across all innings
        player_positions = {}
        # Track infield/outfield by player and inning for consecutive check
        player_field_types = {}
        
        # Define position types
        infield_positions = ["Pitcher", "1B", "2B", "3B", "SS"]
        outfield_positions = ["Catcher", "LF", "RF", "LC", "RC"]
        
        for inning, positions in fielding_plan.items():
            if not isinstance(positions, dict):
                valid_plan = False
                if inning not in validation_errors:
                    validation_errors[inning] = []
                validation_errors[inning].append("Invalid position data (not a dictionary)")
                continue
                
            positions_in_inning = list(positions.values())
            # Remove OUT and Bench as they're not field positions
            field_positions = [pos for pos in positions_in_inning if pos not in ["OUT", "Bench"]]
            
            # Check for missing required positions
            for req_pos in required_positions:
                if req_pos not in field_positions:
                    valid_plan = False
                    if inning not in validation_errors:
                        validation_errors[inning] = []
                    validation_errors[inning].append(req_pos)
            
            # Check for duplicate positions (excluding OUT and Bench)
            position_counts = {}
            for pos in field_positions:
                position_counts[pos] = position_counts.get(pos, 0) + 1
            
            for pos, count in position_counts.items():
                if count > 1:
                    valid_plan = False
                    if inning not in validation_errors:
                        validation_errors[inning] = []
                    validation_errors[inning].append(f"{pos} (duplicate)")
            
            # Track positions by player (for same position across innings check)
            current_inning_num = int(inning.split(" ")[1]) if " " in inning else 0
            
            for player, position in positions.items():
                # Skip OUT positions
                if position == "OUT":
                    continue
                    
                # Initialize player tracking if needed
                if player not in player_positions:
                    player_positions[player] = []
                if player not in player_field_types:
                    player_field_types[player] = {}
                
                # Track this position for the player
                player_positions[player].append(position)
                
                # Determine position type (infield or outfield) and track it
                if position in infield_positions:
                    field_type = "infield"
                elif position in outfield_positions:
                    field_type = "outfield"
                else:
                    field_type = "bench"  # Bench or other
                
                player_field_types[player][current_inning_num] = field_type
        
        # Check for players playing the same position multiple times
        for player, positions in player_positions.items():
            if len(positions) != len(set(positions)) and "Bench" not in positions:
                position_counts = {}
                for pos in positions:
                    if pos != "Bench":  # We allow multiple bench assignments
                        position_counts[pos] = position_counts.get(pos, 0) + 1
                
                duplicates = [pos for pos, count in position_counts.items() if count > 1]
                if duplicates:
                    valid_plan = False
                    if "game-wide" not in validation_errors:
                        validation_errors["game-wide"] = []
                    validation_errors["game-wide"].append(f"Player {player} plays {duplicates[0]} multiple times")
        
        # Check for consecutive infield/outfield innings
        for player, innings in player_field_types.items():
            # Sort innings in numerical order
            sorted_innings = sorted(innings.keys())
            
            for i in range(1, len(sorted_innings)):
                current_inning = sorted_innings[i]
                prev_inning = sorted_innings[i-1]
                
                if current_inning == prev_inning + 1:  # Consecutive innings
                    current_type = innings[current_inning]
                    prev_type = innings[prev_inning]
                    
                    if (current_type == "infield" and prev_type == "infield") or \
                       (current_type == "outfield" and prev_type == "outfield"):
                        valid_plan = False
                        if "game-wide" not in validation_errors:
                            validation_errors["game-wide"] = []
                        validation_errors["game-wide"].append(
                            f"Player {player} plays {current_type} in consecutive innings {prev_inning} and {current_inning}"
                        )
        
        if not valid_plan:
            # Even when validation fails, return the best plan with warnings
            error_msg = "Validation failed: "
            for location, errors in validation_errors.items():
                if location == "game-wide":
                    error_msg += f"Game-wide issues: {', '.join(errors)}; "
                else:
                    error_msg += f"{location}: missing or duplicate {', '.join(errors)}; "
            
            # Add the warning to the result but still return the plan
            result["validation_warning"] = error_msg.strip()
            return result, 200
        
        return result, 200
        
    except requests.RequestException as e:
        return {"error": f"Network error calling Anthropic API: {str(e)}"}, 500
    except Exception as e:
        return {"error": f"Error calling Anthropic API: {str(e)}"}, 500

# Function to add to the Fielding Rotation tab
def add_claude_rotation_generator(team_id, selected_game):
    """Add the Claude rotation generator UI to the Fielding Rotation tab"""
    st.markdown("---")
    st.subheader("AI-Powered Fielding Rotation Generator")
    
    # Create columns for generation and application
    gen_col, apply_col = st.columns([3, 1])
    
    with gen_col:
        st.write("Use Claude AI to generate a balanced fielding rotation plan.")
        
        # Get required positions for validation
        required_positions = set(["Pitcher", "Catcher", "1B", "2B", "3B", "SS", "LF", "RF", "LC", "RC"])
        
        # Add a button to trigger the generation
        if st.button("Generate Field Positions", key="generate_fielding_ai"):
            # Show a spinner while processing
            with st.spinner("Generating balanced fielding rotation..."):
                # Prepare data for Claude
                data = prepare_data_for_claude(team_id, selected_game)
                
                if data is None:
                    st.error("Could not prepare data. Make sure you have a roster and player availability set up.")
                    return
                
                # Add retry logic
                max_retries = 3
                result = None
                for attempt in range(max_retries):
                    # Call Claude API
                    result, status_code = generate_fielding_rotation(data)
                    
                    if status_code == 200:
                        break
                    elif attempt < max_retries - 1:
                        st.info(f"Attempt {attempt+1} failed. Retrying...")
                    else:
                        st.error(f"Error after {max_retries} attempts: {result.get('error', 'Unknown error')}")
                        if "API key" in result.get('error', ''):
                            st.info("Please set the ANTHROPIC_API_KEY environment variable.")
                        return
                
                # Get the fielding plan from the result with validation
                if not result or not isinstance(result, dict):
                    st.error("Invalid response from Claude API.")
                    return
                    
                fielding_plan = result.get("fielding_plan", {})
                statistics = result.get("statistics", {})
                reasoning = result.get("reasoning", "No reasoning provided")
                validation_warning = result.get("validation_warning", "")
                
                # Validate the fielding plan
                if not fielding_plan:
                    st.error("Generated fielding plan is empty.")
                    return
                
                # Validate that all required positions are filled in each inning
                valid_plan = True
                missing_positions_summary = []
                
                for inning, positions in fielding_plan.items():
                    if not positions or not isinstance(positions, dict):
                        valid_plan = False
                        missing_positions_summary.append(f"{inning}: invalid position data")
                        continue
                        
                    filled_positions = set(positions.values())
                    # Remove OUT and Bench as they're not field positions
                    filled_positions = {pos for pos in filled_positions if pos not in ["OUT", "Bench"]}
                    
                    missing = required_positions - filled_positions
                    if missing:
                        valid_plan = False
                        missing_positions_summary.append(f"{inning}: missing {', '.join(missing)}")
                    
                    # Check for duplicates
                    position_counts = {}
                    for pos in filled_positions:
                        position_counts[pos] = position_counts.get(pos, 0) + 1
                    
                    duplicates = [pos for pos, count in position_counts.items() if count > 1]
                    if duplicates:
                        valid_plan = False
                        missing_positions_summary.append(f"{inning}: duplicate {', '.join(duplicates)}")
                
                # Store the generated plan in session state
                st.session_state.claude_fielding_plan = fielding_plan
                st.session_state.claude_fielding_stats = statistics or {}
                st.session_state.claude_fielding_reasoning = reasoning
                st.session_state.claude_validation_warning = validation_warning
                
                # Show success or warning based on validation
                if validation_warning:
                    st.warning(f"Plan generated with some issues: {validation_warning}")
                    st.info("Review the plan below. You can still apply it, but it may not be optimal.")
                elif not valid_plan:
                    st.warning("Plan has potential issues:")
                    for summary in missing_positions_summary:
                        st.warning(summary)
                    st.info("Review the plan below. You can still apply it, but it may not be optimal.")
                else:
                    st.success("Fielding plan generated successfully!")
    
    # Button to apply the generated plan
    with apply_col:
        st.write(" ")  # Spacer
        st.write(" ")  # Spacer
        if st.button("Apply Plan", key="apply_fielding_plan"):
            # Apply the plan to the database
            if 'claude_fielding_plan' not in st.session_state or not st.session_state.claude_fielding_plan:
                st.error("No plan has been generated yet. Please generate a plan first.")
                return
                
            fielding_plan = st.session_state.claude_fielding_plan
            
            try:
                # Update each inning in the database
                for inning_key, positions in fielding_plan.items():
                    if not inning_key or not isinstance(inning_key, str) or not " " in inning_key:
                        continue  # Skip invalid keys
                        
                    # Extract inning number from the key with validation (format: "Inning X")
                    try:
                        inning_num = int(inning_key.split(" ")[1])
                    except (IndexError, ValueError):
                        continue  # Skip invalid inning format
                    
                    # Update the fielding rotation in the database
                    db.update_fielding_rotation(team_id, selected_game, inning_num, positions)
                
                st.success("Fielding plan applied successfully!")
                
                # Use standard rerun to refresh the UI
                st.rerun()
            except Exception as e:
                st.error(f"Error applying plan: {str(e)}")
    
    # Display the generated plan if it exists
    if 'claude_fielding_plan' in st.session_state and st.session_state.claude_fielding_plan:
        # Create a dataframe to display the plan
        st.subheader("Generated Fielding Plan")
        
        # Show reasoning with validation
        if 'claude_fielding_reasoning' in st.session_state and st.session_state.claude_fielding_reasoning:
            reasoning_text = str(st.session_state.claude_fielding_reasoning)
            st.write(f"**AI Reasoning:** {reasoning_text}")
            
        # Show validation warnings if any
        if 'claude_validation_warning' in st.session_state and st.session_state.claude_validation_warning:
            validation_warning = str(st.session_state.claude_validation_warning)
            st.warning(f"**Note:** This plan has some validation issues: {validation_warning}")
        
        # Create a table to display the plan
        plan_data = []
        
        # Get player info with validation
        roster_df = db.get_roster(team_id)
        if not roster_df.empty and all(col in roster_df.columns for col in ["First Name", "Last Name", "Jersey Number"]):
            roster_df["Player"] = roster_df["First Name"] + " " + roster_df["Last Name"] + " (#" + roster_df["Jersey Number"].astype(str) + ")"
            
            # Create player lookup dict
            player_lookup = {str(row["Jersey Number"]): row["Player"] for _, row in roster_df.iterrows()}
            
            # Get all innings with validation
            if st.session_state.claude_fielding_plan and isinstance(st.session_state.claude_fielding_plan, dict):
                innings = sorted(st.session_state.claude_fielding_plan.keys())
                
                # Create a structure for display
                for jersey in sorted(player_lookup.keys()):
                    row = {"Jersey": jersey, "Player": player_lookup.get(jersey, f"Unknown ({jersey})")}
                    
                    # Add positions for each inning with validation
                    for inning in innings:
                        # Validate inning key exists
                        if inning in st.session_state.claude_fielding_plan:
                            inning_positions = st.session_state.claude_fielding_plan[inning]
                            # Validate inning positions is a dictionary
                            if isinstance(inning_positions, dict):
                                row[inning] = inning_positions.get(jersey, "N/A")
                            else:
                                row[inning] = "N/A"  # Default if invalid
                        else:
                            row[inning] = "N/A"  # Default if not found
                    
                    # Add statistics if available with validation
                    if 'claude_fielding_stats' in st.session_state and isinstance(st.session_state.claude_fielding_stats, dict):
                        stats = st.session_state.claude_fielding_stats.get(jersey, {})
                        if isinstance(stats, dict):
                            row["Infield"] = stats.get("infield", 0)
                            row["Outfield"] = stats.get("outfield", 0)
                            row["Bench"] = stats.get("bench", 0)
                            row["Total"] = stats.get("total", 0)
                        else:
                            # Default values if stats isn't a dictionary
                            row["Infield"] = 0
                            row["Outfield"] = 0
                            row["Bench"] = 0
                            row["Total"] = 0
                    
                    plan_data.append(row)
                
                # Create dataframe
                plan_df = pd.DataFrame(plan_data)
                
                # Display the plan
                st.dataframe(plan_df, use_container_width=True)
            else:
                st.warning("Field plan data is invalid. Try generating a new plan.")
        else:
            st.warning("Roster data is missing or incomplete.")

# Add statistics view for the generated plan
def add_plan_statistics():
    """Add statistics visualization for the generated plan"""
    if 'claude_fielding_stats' in st.session_state and st.session_state.claude_fielding_stats:
        st.subheader("Position Distribution in Generated Plan")
        
        # Get player info
        roster_df = db.get_roster(st.session_state.team_id)
        
        # Create stats dataframe
        stats_data = []
        for jersey, stats in st.session_state.claude_fielding_stats.items():
            # Find player name
            player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
            player_name = f"Unknown ({jersey})"
            if not player_rows.empty:
                player_name = f"{player_rows.iloc[0]['First Name']} {player_rows.iloc[0]['Last Name']} (#{jersey})"
            
            # Calculate percentages
            total = stats.get("total", 0)
            if total > 0:
                infield_pct = round((stats.get("infield", 0) / total * 100), 1)
                outfield_pct = round((stats.get("outfield", 0) / total * 100), 1)
                bench_pct = round((stats.get("bench", 0) / total * 100), 1)
            else:
                infield_pct = outfield_pct = bench_pct = 0.0
            
            stats_data.append({
                "Player": player_name,
                "Infield": stats.get("infield", 0),
                "Outfield": stats.get("outfield", 0),
                "Bench": stats.get("bench", 0),
                "Total": total,
                "Infield %": infield_pct,
                "Outfield %": outfield_pct,
                "Bench %": bench_pct
            })
        
        # Only proceed if we have stats data
        if stats_data:
            # Create dataframe
            stats_df = pd.DataFrame(stats_data)
            
            # Display the statistics
            st.dataframe(stats_df, use_container_width=True)
            
            # Add visualization
            st.subheader("Position Type Distribution")
            chart_data = stats_df[["Player", "Infield %", "Outfield %", "Bench %"]].set_index("Player")
            st.bar_chart(chart_data)
            
            # Rest of the existing analysis code...
        else:
            st.warning("No player statistics available.")
    else:
        st.warning("No fielding statistics have been generated yet.")

# Authentication functions
def show_login_form():
    """Display login form"""
    st.title("⚾ LineupBoss")
    st.subheader("Login")
    
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Login")
        with col2:
            register_button = st.form_submit_button("Need to Register?")
    
    if submit:
        if not email or not password:
            st.error("Please enter both email and password")
        else:
            user_id = database.verify_user(email, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.is_authenticated = True
                st.session_state.user_email = email
                st.rerun()
            else:
                st.error("Invalid email or password")
                
    if register_button:
        st.session_state.active_tab = "Register"
        st.rerun()

def show_registration_form():
    """Display registration form"""
    st.title("⚾ LineupBoss")
    st.subheader("Create Account")
    
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Register")
        with col2:
            login_button = st.form_submit_button("Back to Login")
    
    if submit:
        if not email or not password:
            st.error("Please enter both email and password")
        elif password != confirm_password:
            st.error("Passwords do not match")
        else:
            user_id, message = database.create_user(email, password)
            if user_id:
                st.success("Registration successful! Please log in.")
                st.session_state.active_tab = "Login"
                st.rerun()
            else:
                st.error(f"Registration failed: {message}")
                
    if login_button:
        st.session_state.active_tab = "Login"
        st.rerun()

# Main app layout
def main():
    # Database configuration check
    try:
        # Try to get a database session to verify connection works
        session = database.get_db_session()
        session.close()
    except Exception as e:
        # Show a user-friendly error message for database configuration issues
        st.error("⚠️ Database Configuration Error")
        st.markdown("""
        ### Unable to connect to the database
        
        This application requires a properly configured PostgreSQL database to function.
        
        **If you're running on Streamlit Cloud:**
        - Make sure you've added the `DATABASE_URL` to your app secrets
        - The URL format should be: `postgresql://username:password@hostname/database`
        
        **If you're running locally:**
        - Create a `.env` file in the project directory with your database connection string:
          ```
          DATABASE_URL=postgresql://username:password@hostname/database
          ```
        - Make sure you have the python-dotenv package installed: `pip install python-dotenv`
        - Double-check that your .env file is in the correct location and properly formatted
        
        **Error details:** 
        """)
        st.code(str(e))
        
        # Add local development instructions for quick setup
        st.subheader("Quick Setup for Local Development")
        st.markdown("""
        1. Create a file named `.env` in this directory (/Users/astraus/dev/lineup/)
        2. Add the following line to the file:
           ```
           DATABASE_URL=postgresql://username:password@localhost/lineup
           ```
        3. Replace username, password with your PostgreSQL credentials
        4. Create a database named 'lineup' in PostgreSQL
        5. Restart this application
        """)
        return  # Exit the main function to prevent further errors
    
    # Check if user is authenticated
    if not st.session_state.is_authenticated:
        # Show login/registration forms
        if st.session_state.active_tab == "Register":
            show_registration_form()
        else:
            show_login_form()
        return  # Exit the main function
        
    # Add a sidebar with tabs
    st.sidebar.title("⚾ LineupBoss")
    
    # Show user information and logout button
    if st.session_state.user_email:
        st.sidebar.markdown(f"**Logged in as:** {st.session_state.user_email}")
        if st.sidebar.button("Logout"):
            st.session_state.user_id = None
            st.session_state.is_authenticated = False
            st.session_state.user_email = None
            st.session_state.team_id = None
            st.rerun()
    
    # Function to get all teams from the database (use the version defined at the top level)
    get_all_teams_local = get_all_teams
    
    # Team selector (we can now support multiple teams)
    if st.session_state.team_id is None:
        # Get teams for the current user
        team_options = database.get_teams_for_user(st.session_state.user_id)
        
        st.sidebar.markdown("### Team Selection")
        
        # Display existing teams in a selectbox if there are any
        if team_options:
            st.sidebar.markdown("#### Select an existing team:")
            selected_team_tuple = st.sidebar.selectbox(
                "Choose a team to work with:",
                options=team_options,
                format_func=lambda x: x[1]  # Display team name
            )
            
            if st.sidebar.button("Load Selected Team"):
                st.session_state.team_id = selected_team_tuple[0]  # Set team ID
                st.rerun()
        else:
            st.sidebar.markdown("No existing teams found.")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Team Management")
        
        # Move to Data Management tab to create a new team
        st.sidebar.info("To create a new team, use the Data Management tab.")
        if st.sidebar.button("Go to Data Management"):
            st.session_state.active_tab = "Data Management"
            st.rerun()
        
        # Quick onboarding for new users
        st.sidebar.markdown("---")
        st.sidebar.markdown("#### Quick Start (for testing)")
        if st.sidebar.button("Create Example Team"):
            # Create example team
            team_info = {
                "team_name": "Example Tigers",
                "league": "Little League",
                "head_coach": "Coach Smith",
                "assistant_coach1": "Coach Johnson",
                "assistant_coach2": "Coach Wilson"
            }
            team_id = database.create_team_with_user(team_info, st.session_state.user_id)
            
            # Create example roster
            roster_data = {
                "First Name": ["John", "Michael", "David", "James", "Robert", "William", "Thomas", "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Andrew", "Christopher"],
                "Last Name": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor", "Thomas"],
                "Jersey Number": [str(num) for num in range(1, 15)]
            }
            roster_df = pd.DataFrame(roster_data)
            db.update_roster(team_id, roster_df)
            
            # Create example schedule
            schedule_data = []
            for i in range(1, 11):
                schedule_data.append({
                    "Game #": i,
                    "Date": pd.Timestamp(f"2023-06-{i+10}"),
                    "Time": pd.Timestamp(f"2023-06-{i+10} 18:00:00").time() if i % 2 == 0 else pd.Timestamp(f"2023-06-{i+10} 10:00:00").time(),
                    "Opponent": f"Team {i}",
                    "Innings": 6
                })
            schedule_df = pd.DataFrame(schedule_data)
            db.update_schedule(team_id, schedule_df)
            
            # Set team ID in session state
            st.session_state.team_id = team_id
            st.rerun()
            
        return
    
    # Define all tab names with Instructions as Tab 0
    tabs = [
        "Instructions",
        "Team Setup",
        "Game Schedule", 
        "Player Setup",
        "Batting Order", 
        "Fielding Rotation", 
        "Batting Fairness", 
        "Fielding Fairness",
        "Game Summary",
        "Data Management"
    ]

    # Create radio buttons in the sidebar for navigation
    selected_tab = st.sidebar.radio("Navigation", tabs, index=tabs.index(st.session_state.active_tab) if st.session_state.active_tab in tabs else 0)

    # Update the session state to track the active tab
    st.session_state.active_tab = selected_tab

    # Main area title that shows the current tab
    if selected_tab != "Instructions":
        st.title(f"⚾ {selected_tab}")

    # Tab 0: Instructions
    if selected_tab == "Instructions":
        st.markdown("# Welcome to LineupBoss")
        
        st.markdown("""
        This application helps baseball coaches manage team rosters, create fair batting orders and fielding rotations, 
        and generate game plans. Follow the steps below to get started.
        """)

        # Overview diagram using a Streamlit flowchart-like layout
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("### Step 1: Setup")
            st.markdown("""
            - Team Setup
            - Game Schedule 
            - Player Setup
            """)
        with col2:
            st.markdown("### Step 2: Plan")
            st.markdown("""
            - Batting Order
            - Fielding Rotation
            """)
        with col3:
            st.markdown("### Step 3: Analyze")
            st.markdown("""
            - Batting Fairness
            - Fielding Fairness
            """)
        with col4:
            st.markdown("### Step 4: Share")
            st.markdown("""
            - Game Summary
            - Data Management
            """)

        st.markdown("---")

        # Quick Start
        st.markdown("## 🚀 Quick Start Guide")
        st.markdown("""
        1. **Team Setup**: Enter team information and upload/create your roster
        2. **Game Schedule**: Create your season schedule
        3. **Player Setup**: Mark player availability for each game
        4. **Batting Order**: Set your batting lineup for each game
        5. **Fielding Rotation**: Assign positions for each inning
        6. **Generate Game Plan**: View and export your game plans
        """)

        st.markdown("---")

        # Detailed tab instructions
        with st.expander("📋 Detailed Tab Instructions", expanded=True):
            st.markdown("""
            ### Team Setup Tab
            - Input team and coach information
            - Create or upload a roster with player names and jersey numbers
            - Add or remove players from your roster

            ### Game Schedule Tab
            - Create a season schedule with dates, opponents, and number of innings
            - Edit game details as needed throughout the season

            ### Player Setup Tab
            - Mark which players are available for each game
            - Indicate which players can play specialized positions (e.g., catcher)
            - This affects batting orders and fielding rotations

            ### Batting Order Tab
            - Assign batting positions for each player across all games
            - Automatically handle unavailable players
            - Check for issues with your batting order

            ### Fielding Rotation Tab
            - Assign fielding positions for each player for each inning
            - Auto-assign unavailable players to bench
            - Check for position coverage and errors

            ### Batting Fairness Tab
            - Analyze how equitably batting positions are distributed
            - View visual representations of batting position fairness
            - Identify players who need different batting opportunities

            ### Fielding Fairness Tab
            - Track time spent in infield, outfield, and bench positions
            - Analyze equity in fielding assignments
            - Make data-driven decisions for future games

            ### Game Summary Tab
            - Generate comprehensive game plans
            - Export as PDF or text format
            - Share with coaches, players, and parents

            ### Data Management Tab
            - Export your team data for backup
            - Import previously saved data
            - Generate example data for testing
            """)

    # Tab 1: Team Setup
    elif selected_tab == "Team Setup":
        # Get team info from database
        team_info = db.get_team_info(st.session_state.team_id)
        
        # Track if we need to upload a roster in this session
        if 'upload_roster_flag' not in st.session_state:
            st.session_state.upload_roster_flag = False
        
        # Create columns for team info and roster management
        team_info_col, roster_col = st.columns([1, 2])
        
        with team_info_col:
            st.subheader("Team Information")
            
            # Team information form
            with st.form("team_info_form"):
                team_name = st.text_input("Team Name", value=team_info["team_name"])
                league = st.text_input("League", value=team_info["league"])
                head_coach = st.text_input("Head Coach", value=team_info["head_coach"])
                assistant_coach1 = st.text_input("Assistant Coach 1", value=team_info["assistant_coach1"])
                assistant_coach2 = st.text_input("Assistant Coach 2", value=team_info["assistant_coach2"])
                
                save_team_info = st.form_submit_button("Save Team Information")
                
                if save_team_info:
                    # Update the database with new values
                    updated_info = {
                        "team_name": team_name,
                        "league": league,
                        "head_coach": head_coach,
                        "assistant_coach1": assistant_coach1,
                        "assistant_coach2": assistant_coach2
                    }
                    db.update_team(st.session_state.team_id, updated_info)
                    st.success("Team information saved!")
        
        with roster_col:
            st.subheader("Team Roster Management")
            
            # Option to upload a roster
            upload_container = st.container()
            with upload_container:
                st.markdown("##### Upload Team Roster")
                
                # Callback for when file is uploaded
                def process_roster_upload():
                    if st.session_state.roster_file is not None:
                        try:
                            df = pd.read_csv(st.session_state.roster_file)
                            valid, message = validate_roster(df)
                            
                            if valid:
                                # Save roster to database
                                db.update_roster(st.session_state.team_id, df)
                                
                                st.session_state.upload_roster_flag = True
                                st.session_state.upload_success = True
                            else:
                                st.session_state.upload_error = message
                        except Exception as e:
                            st.session_state.upload_error = f"Error uploading file: {str(e)}"
                
                # File uploader with on_change callback
                roster_file = st.file_uploader(
                    "Upload your team roster CSV file", 
                    type=["csv"], 
                    key="roster_file",
                    on_change=process_roster_upload
                )
                
                # Show success or error message
                if 'upload_success' in st.session_state and st.session_state.upload_success:
                    st.success("Roster uploaded successfully!")
                    # Clear the flag after showing the message
                    st.session_state.upload_success = False
                    
                if 'upload_error' in st.session_state and st.session_state.upload_error:
                    st.error(st.session_state.upload_error)
                    # Clear the error after showing it
                    st.session_state.upload_error = ""
            
            # Option to download a template
            st.markdown("##### Download Roster Template")
            num_players = st.number_input("Number of players", min_value=1, max_value=30, value=14)
            template_df = create_empty_roster_template(num_players)
            st.markdown(get_csv_download_link(template_df, "roster_template.csv", "Download Roster Template"), unsafe_allow_html=True)
            
            # Get roster from database
            roster_df = db.get_roster(st.session_state.team_id)
            
            # Display current roster if it exists
            if not roster_df.empty:
                st.subheader("Current Team Roster")
                
                # Add a row index column that starts at 1
                display_df = roster_df.copy()
                display_df.index = range(1, len(display_df) + 1)
                
                # Make the displayed roster editable
                edited_roster = st.data_editor(
                    display_df, 
                    use_container_width=True,
                    key="roster_editor"
                )
                
                # Save button for roster edits
                if st.button("Save Roster Changes"):
                    # Update the roster in the database
                    try:
                        # Reset index if it was changed in the editor
                        edited_roster.reset_index(drop=True, inplace=True)
                        db.update_roster(st.session_state.team_id, edited_roster)
                        st.success("Roster changes saved!")
                    except Exception as e:
                        st.error(f"Error saving roster: {str(e)}")
                
                # Add roster statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Players", len(roster_df))
        
        # Roster management actions (shown only if roster exists)
        if roster_df is not None and not roster_df.empty:
            st.subheader("Roster Management")
            
            # Option to add a player
            with st.expander("Add New Player"):
                with st.form("add_player_form"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_first_name = st.text_input("First Name")
                    with col2:
                        new_last_name = st.text_input("Last Name")
                    with col3:
                        new_jersey = st.number_input("Jersey Number", min_value=0, max_value=99)
                    
                    submit_button = st.form_submit_button("Add Player")
                    
                    if submit_button:
                        # Check if all fields are filled
                        if not new_first_name or not new_last_name:
                            st.error("Please fill in all fields")
                        else:
                            # Check if jersey number already exists
                            if str(new_jersey) in roster_df["Jersey Number"].astype(str).values:
                                st.error(f"Jersey number {new_jersey} already exists")
                            else:
                                try:
                                    # Add new player to roster
                                    new_player = pd.DataFrame({
                                        "First Name": [new_first_name],
                                        "Last Name": [new_last_name],
                                        "Jersey Number": [str(new_jersey)]
                                    })
                                    
                                    # Add to roster in database
                                    updated_roster = pd.concat([roster_df, new_player], ignore_index=True)
                                    db.update_roster(st.session_state.team_id, updated_roster)
                                    
                                    st.success(f"Added {new_first_name} {new_last_name} (#{new_jersey}) to roster")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error adding player: {str(e)}")
            
            # Option to remove a player
            with st.expander("Remove Player"):
                # Create a list of players to select from
                roster_df["Player"] = roster_df["First Name"] + " " + roster_df["Last Name"] + " (#" + roster_df["Jersey Number"].astype(str) + ")"
                player_options = roster_df["Player"].tolist()
                
                selected_player = st.selectbox("Select player to remove", player_options)
                
                if st.button("Remove Selected Player"):
                    try:
                        # Find the player in the roster
                        player_idx = roster_df[roster_df["Player"] == selected_player].index[0]
                        
                        # Remove player from roster
                        updated_roster = roster_df.drop(player_idx).reset_index(drop=True)
                        db.update_roster(st.session_state.team_id, updated_roster)
                        
                        # Show success message
                        st.success(f"Removed {selected_player} from roster")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error removing player: {str(e)}")
        
        # Force a rerun when a new roster is uploaded to ensure it displays immediately
        if st.session_state.upload_roster_flag:
            st.session_state.upload_roster_flag = False
            st.rerun()

    # Tab 2: Game Schedule
    elif selected_tab == "Game Schedule":
        st.subheader("Create Game Schedule")
        
        # Get schedule from database
        schedule_df = db.get_schedule(st.session_state.team_id)
        
        # Initialize or display schedule
        if schedule_df.empty:
            num_games = st.number_input("Number of games", min_value=1, max_value=50, value=10)
            
            if st.button("Initialize Schedule"):
                # Create schedule with proper data types
                schedule_data = []
                for i in range(1, num_games + 1):
                    schedule_data.append({
                        "Game #": i,
                        "Date": None,
                        "Time": None,
                        "Opponent": "",
                        "Innings": 6
                    })
                new_schedule = pd.DataFrame(schedule_data)
                
                # Ensure Date column is datetime type
                new_schedule["Date"] = pd.to_datetime(new_schedule["Date"])
                
                # Save to database
                db.update_schedule(st.session_state.team_id, new_schedule)
                st.rerun()
        
        # Edit schedule if it exists
        if not schedule_df.empty:
            # Make sure the Date column is datetime type before editing
            if schedule_df["Date"].dtype != 'datetime64[ns]':
                schedule_df["Date"] = pd.to_datetime(schedule_df["Date"], errors='coerce')
            
            # Add Time column if it doesn't exist
            if "Time" not in schedule_df.columns:
                schedule_df["Time"] = None
            
            # Create a fresh DataFrame with exactly the columns we want
            columns = ["Game #", "Date", "Time", "Opponent", "Innings"]
            data = []
            
            # Copy the data row by row to ensure clean DataFrame creation
            for _, row in schedule_df.iterrows():
                data.append({
                    "Game #": row["Game #"],
                    "Date": row["Date"],
                    "Time": row["Time"] if "Time" in row and pd.notna(row["Time"]) else None,
                    "Opponent": row["Opponent"],
                    "Innings": row["Innings"]
                })
            
            # Create a fresh DataFrame
            display_schedule = pd.DataFrame(data, columns=columns)
                
            # Create the data editor with explicit columns and hiding index
            edited_schedule = st.data_editor(
                display_schedule,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "Game #": st.column_config.NumberColumn("Game #", help="Game number"),
                    "Date": st.column_config.DateColumn("Date", help="Game date", format="YYYY-MM-DD"),
                    "Time": st.column_config.TimeColumn("Time", help="Game time"),
                    "Opponent": st.column_config.TextColumn("Opponent", help="Opposing team"),
                    "Innings": st.column_config.NumberColumn("Innings", help="Number of innings", min_value=1, max_value=9),
                },
                hide_index=True,
                key="fresh_game_schedule_editor"
            )
            
            if st.button("Save Schedule"):
                # Save the edited schedule to database
                db.update_schedule(st.session_state.team_id, edited_schedule)
                st.success("Schedule saved!")
                
            # Add some helpful instructions
            with st.expander("Schedule Instructions"):
                st.markdown("""
                ### How to use the Game Schedule tab:
                
                1. **Set the number of games** and click "Initialize Schedule" if starting fresh
                2. **Enter game details** in the table:
                   - **Game #**: Automatically numbered, but can be changed if needed
                   - **Date**: Click to select the game date from a calendar
                   - **Time**: Set the game start time
                   - **Opponent**: Enter the name of the opposing team
                   - **Innings**: Set the number of innings scheduled (typically 6-9)
                3. **Click "Save Schedule"** after making changes
                4. **Add rows** using the + button at the bottom of the table if needed
                
                Your schedule will be available throughout the app for creating lineups and rotations.
                """)

    # Tab 3: Player Setup
    elif selected_tab == "Player Setup":
        # Get roster and schedule from database
        roster_df = db.get_roster(st.session_state.team_id)
        schedule_df = db.get_schedule(st.session_state.team_id)
        
        if roster_df.empty:
            st.warning("Please create a team roster first")
        elif schedule_df.empty:
            st.warning("Please create a game schedule first")
        else:
            # Select a game to set up players for
            game_options = schedule_df["Game #"].tolist()
            selected_game = st.selectbox("Select a game", game_options, key="setup_game_select")
            
            # Get the game information
            game_info = schedule_df[schedule_df["Game #"] == selected_game].iloc[0]
            
            st.subheader(f"Player Setup for Game {selected_game}")
            st.write(f"**Opponent:** {game_info['Opponent']}")
            st.write(f"**Date:** {game_info['Date']}")
            
            # Get player info
            roster_df["Player"] = roster_df["First Name"] + " " + roster_df["Last Name"] + " (#" + roster_df["Jersey Number"].astype(str) + ")"
            
            # Get player availability from database
            player_availability = db.get_player_availability(st.session_state.team_id)
            
            # Initialize player availability for this game if needed
            if selected_game not in player_availability:
                player_availability[selected_game] = {
                    "Available": {},
                    "Can Play Catcher": {}
                }
                # Initialize with all players available
                for _, player in roster_df.iterrows():
                    jersey = str(player["Jersey Number"])
                    player_availability[selected_game]["Available"][jersey] = True
                    player_availability[selected_game]["Can Play Catcher"][jersey] = False
            
            # Create a dataframe for the player setup grid
            setup_data = []
            for _, player in roster_df.iterrows():
                jersey = str(player["Jersey Number"])
                player_name = f"{player['First Name']} {player['Last Name']}"
                
                # Get availability and catcher info for this player
                available = player_availability[selected_game]["Available"].get(jersey, True)
                can_play_catcher = player_availability[selected_game]["Can Play Catcher"].get(jersey, False)
                
                setup_data.append({
                    "Player": player_name,
                    "Jersey #": jersey,
                    "Available": available,
                    "Can Play Catcher": can_play_catcher
                })
            
            setup_df = pd.DataFrame(setup_data)
            
            # Add index starting from 1 instead of 0
            setup_df.index = range(1, len(setup_df) + 1)
            
            # Display the editable grid
            edited_df = st.data_editor(
                setup_df,
                use_container_width=True,
                column_config={
                    "Player": st.column_config.TextColumn("Player", disabled=True),
                    "Jersey #": st.column_config.TextColumn("Jersey #", disabled=True),
                    "Available": st.column_config.CheckboxColumn("Available for Game", help="Check if player is available for this game"),
                    "Can Play Catcher": st.column_config.CheckboxColumn("Can Play Catcher", help="Check if player can play catcher position")
                },
                hide_index=False,
                key="player_setup_editor"
            )
            
            # Save button
            if st.button("Save Player Setup", key="save_player_setup"):
                # Extract the updated values from the edited dataframe
                availability_data = {
                    "Available": {},
                    "Can Play Catcher": {}
                }
                
                for _, row in edited_df.iterrows():
                    jersey = str(row["Jersey #"])
                    availability_data["Available"][jersey] = row["Available"]
                    availability_data["Can Play Catcher"][jersey] = row["Can Play Catcher"]
                
                # Update database
                db.update_player_availability(st.session_state.team_id, selected_game, availability_data)
                
                st.success("Player setup saved successfully!")
            
            # Add a summary of player availability
            available_count = sum(1 for _, row in edited_df.iterrows() if row["Available"])
            unavailable_count = len(edited_df) - available_count
            catchers_count = sum(1 for _, row in edited_df.iterrows() if row["Can Play Catcher"])
            
            st.subheader("Player Availability Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Available Players", available_count)
            with col2:
                st.metric("Unavailable Players", unavailable_count)
            with col3:
                st.metric("Catchers Available", catchers_count)
            
            # Provide guidance on batting order and fielding
            st.info("""
            **How to use Player Setup:**
            
            1. Check the "Available" box for all players who will be at this game
            2. Check the "Can Play Catcher" box for players who can play catcher position
            3. Click "Save Player Setup" to update
            
            This information will help with batting orders and fielding rotations. 
            Unavailable players will automatically be placed at the end of the batting order.
            """)

    # Tab 4: Batting Order
    elif selected_tab == "Batting Order":
        # Get roster and schedule from database
        roster_df = db.get_roster(st.session_state.team_id)
        schedule_df = db.get_schedule(st.session_state.team_id)
        
        if roster_df.empty:
            st.warning("Please upload a team roster first")
        elif schedule_df.empty:
            st.warning("Please create a game schedule first")
        else:
            # Get player info
            roster_df["Player"] = roster_df["First Name"] + " " + roster_df["Last Name"] + " (#" + roster_df["Jersey Number"].astype(str) + ")"
            
            st.subheader("Batting Orders for All Games")
            
            # Get all games from schedule
            games = schedule_df.copy()
            
            # Get batting orders from database
            batting_orders = db.get_batting_orders(st.session_state.team_id)
            
            # Initialize batting orders for all games if they don't exist
            for game_id in games["Game #"].tolist():
                if game_id not in batting_orders:
                    batting_orders[game_id] = [
                        str(jersey) for jersey in roster_df["Jersey Number"].tolist()
                    ]
            
            # Create a table layout with player names in the leftmost column
            # and games across the top
            col_headers = ["Player"]
            for _, game in games.iterrows():
                game_id = game["Game #"]
                game_label = f"Game {game_id} vs {game['Opponent']}"
                if pd.notna(game["Date"]):
                    # Format date if it exists
                    try:
                        date_str = game["Date"].strftime("%m/%d")
                        game_label += f" ({date_str}"
                        
                        # Add time if available
                        if "Time" in game and pd.notna(game["Time"]):
                            try:
                                time_str = game["Time"].strftime("%I:%M%p")
                                game_label += f" {time_str}"
                            except:
                                pass
                        
                        game_label += ")"
                    except:
                        pass
                col_headers.append(game_label)
            
            # Create an empty DataFrame for the batting order grid
            num_players = len(roster_df)
            batting_grid = pd.DataFrame(index=range(num_players), columns=col_headers)
            
            # Fill in player names
            batting_grid["Player"] = roster_df["Player"].tolist()
            
            # Get player availability from database
            player_availability = db.get_player_availability(st.session_state.team_id)
            
            # Fill in the current batting positions with OUT for unavailable players
            for _, game in games.iterrows():
                game_id = game["Game #"]
                game_col = f"Game {game_id} vs {game['Opponent']}"
                if pd.notna(game["Date"]):
                    try:
                        date_str = game["Date"].strftime("%m/%d")
                        game_col += f" ({date_str}"
                        
                        # Add time if available
                        if "Time" in game and pd.notna(game["Time"]):
                            try:
                                time_str = game["Time"].strftime("%I:%M%p")
                                game_col += f" {time_str}"
                            except:
                                pass
                        
                        game_col += ")"
                    except:
                        pass
                
                # Get availability information
                availability = {}  # Default all players as available
                if game_id in player_availability:
                    availability = player_availability[game_id]["Available"]
                
                # Get batting order for this game
                if game_id in batting_orders:
                    batting_order = batting_orders[game_id]
                    
                    # Fill in the batting positions or OUT for unavailable players
                    for i, player in roster_df.iterrows():
                        jersey = str(player["Jersey Number"])
                        
                        # Check if player is unavailable
                        is_available = availability.get(jersey, True)
                        
                        if not is_available:
                            # Player is unavailable - display OUT
                            batting_grid.loc[i, game_col] = "OUT"
                        else:
                            # Player is available - display batting position
                            try:
                                position = batting_order.index(jersey) + 1  # Batting position is 1-based
                                batting_grid.loc[i, game_col] = position
                            except ValueError:
                                # Player not found in batting order
                                batting_grid.loc[i, game_col] = ""
            
            # Set index to start at 1
            batting_grid.index = range(1, len(batting_grid) + 1)
            
            # Convert all columns (except Player) to string type to allow mixed content (numbers and "OUT")
            for col in batting_grid.columns:
                if col != "Player":
                    batting_grid[col] = batting_grid[col].astype(str)
                    batting_grid[col] = batting_grid[col].replace("nan", "")  # Replace NaN values with empty strings
            
            # Display the editable grid
            edited_grid = st.data_editor(
                batting_grid,
                use_container_width=True,
                column_config={
                    "Player": st.column_config.TextColumn("Player", disabled=True),
                    **{col: st.column_config.TextColumn(
                        col, 
                        width="medium",
                        help=f"Batting position for {col}"
                    ) for col in batting_grid.columns if col != "Player"}
                },
                hide_index=False,
            )
            
            # Display availability warnings for each game
            for _, game in games.iterrows():
                game_id = game["Game #"]
                if game_id in player_availability:
                    unavailable_count = sum(1 for _, available in player_availability[game_id]["Available"].items() if not available)
                    if unavailable_count > 0:
                        st.warning(f"Game {game_id}: {unavailable_count} player(s) marked as unavailable in Player Setup.")
            
            # Save button for all games
            if st.button("Save All Batting Orders", key="save_all_batting"):
                # Extract the updated orders from the edited grid
                for _, game in games.iterrows():
                    game_id = game["Game #"]
                    game_col = f"Game {game_id} vs {game['Opponent']}"
                    if pd.notna(game["Date"]):
                        try:
                            date_str = game["Date"].strftime("%m/%d")
                            game_col += f" ({date_str}"
                            
                            # Add time if available
                            if "Time" in game and pd.notna(game["Time"]):
                                try:
                                    time_str = game["Time"].strftime("%I:%M%p")
                                    game_col += f" {time_str}"
                                except:
                                    pass
                            
                            game_col += ")"
                        except:
                            pass
                    
                    if game_col in edited_grid.columns:
                        # Create a mapping of batting positions to jersey numbers
                        position_map = {}
                        
                        # Get availability info
                        availability = {}
                        if game_id in player_availability:
                            availability = player_availability[game_id]["Available"]
                        
                        # Collect the positions entered by the user
                        for i, row in edited_grid.iterrows():
                            pos_str = row[game_col]
                            i_adj = i - 1  # Adjust for 1-based index
                            
                            if i_adj < len(roster_df):
                                jersey = str(roster_df.iloc[i_adj]["Jersey Number"])
                                
                                # Skip if position is OUT or empty
                                if pos_str and pos_str != "OUT" and pos_str != "nan":
                                    try:
                                        # Convert position to integer
                                        position = int(pos_str)
                                        
                                        # Add to the mapping if valid
                                        if position > 0:
                                            position_map[position] = jersey
                                    except ValueError:
                                        # Not a valid number, skip it
                                        pass
                        
                        # Sort by position to create the batting order
                        sorted_positions = sorted(position_map.keys())
                        ordered_jerseys = [position_map[pos] for pos in sorted_positions]
                        
                        # Get all jersey numbers
                        all_jerseys = [str(j) for j in roster_df["Jersey Number"].astype(str).tolist()]
                        
                        # Add missing players who are available but not in the batting order
                        for jersey in all_jerseys:
                            # Add jersey if not already in the order and is available
                            if jersey not in ordered_jerseys:
                                is_available = availability.get(jersey, True)
                                if is_available:
                                    ordered_jerseys.append(jersey)
                        
                        # Add unavailable players at the end
                        for jersey in all_jerseys:
                            if jersey not in ordered_jerseys:
                                ordered_jerseys.append(jersey)
                        
                        # Update the batting order in the database
                        db.update_batting_order(st.session_state.team_id, game_id, ordered_jerseys)
                
                st.success("All batting orders saved!")
                
            # Add warnings about duplicate or missing positions
            st.info("Enter the batting order position (1-9+) for each player in each game. Leave blank for players not in the lineup. Unavailable players will show 'OUT'.")
            
            # Validation button
            if st.button("Validate Batting Orders"):
                all_valid = True
                for _, game in games.iterrows():
                    game_id = game["Game #"]
                    game_col = f"Game {game_id} vs {game['Opponent']}"
                    if pd.notna(game["Date"]):
                        try:
                            date_str = game["Date"].strftime("%m/%d")
                            game_col += f" ({date_str}"
                            
                            # Add time if available
                            if "Time" in game and pd.notna(game["Time"]):
                                try:
                                    time_str = game["Time"].strftime("%I:%M%p")
                                    game_col += f" {time_str}"
                                except:
                                    pass
                            
                            game_col += ")"
                        except:
                            pass
                    
                    if game_col in edited_grid.columns:
                        # Get the batting positions from the grid (exclude OUT values)
                        positions = []
                        for p in edited_grid[game_col].tolist():
                            if pd.notna(p) and p != "" and p != "OUT" and p != "nan":
                                try:
                                    positions.append(int(p))
                                except ValueError:
                                    # Skip non-numeric values
                                    pass
                        
                        # Check for duplicates
                        if len(positions) != len(set(positions)):
                            st.error(f"Game {game_id}: Duplicate batting positions found.")
                            all_valid = False
                        
                        # Check for gaps in the batting order
                        if positions:
                            min_pos = min(positions)
                            max_pos = max(positions)
                            expected_positions = list(range(int(min_pos), int(max_pos) + 1))
                            missing = [p for p in expected_positions if p not in positions]
                            if missing:
                                st.warning(f"Game {game_id}: Gaps in batting order - missing positions {missing}")
                                all_valid = False
                
                if all_valid:
                    st.success("All batting orders are valid!")
                    
            # Add a way to auto-arrange unavailable players
            st.subheader("Auto-arrange Batting Orders")
            game_options_auto = schedule_df["Game #"].tolist()
            auto_game = st.selectbox("Select a game to auto-arrange", game_options_auto, key="auto_arrange_game")
            
            if auto_game in player_availability:
                if st.button("Auto-arrange Batting Order", key="auto_arrange"):
                    # Get current batting order
                    current_order = batting_orders.get(auto_game, [])
                    
                    # Get availability info
                    availability = player_availability[auto_game]["Available"]
                    
                    # Separate available and unavailable players
                    available = []
                    unavailable = []
                    
                    for jersey in current_order:
                        is_available = availability.get(jersey, True)
                        if is_available:
                            available.append(jersey)
                        else:
                            unavailable.append(jersey)
                    
                    # Make sure all jerseys are accounted for
                    all_jerseys = [str(j) for j in roster_df["Jersey Number"].astype(str).tolist()]
                    for jersey in all_jerseys:
                        is_available = availability.get(jersey, True)
                        if is_available and jersey not in available:
                            available.append(jersey)
                        elif not is_available and jersey not in unavailable:
                            unavailable.append(jersey)
                    
                    # Form the new order with available players first, then unavailable
                    new_order = available + unavailable
                    
                    # Update the batting order in the database
                    db.update_batting_order(st.session_state.team_id, auto_game, new_order)
                    
                    st.success("Batting order auto-arranged with unavailable players at the end.")
                    st.rerun()
    
    # Tab 5: Fielding Rotation
    elif selected_tab == "Fielding Rotation":
        # Get roster and schedule from database
        roster_df = db.get_roster(st.session_state.team_id)
        schedule_df = db.get_schedule(st.session_state.team_id)
        
        if roster_df.empty:
            st.warning("Please upload a team roster first")
        elif schedule_df.empty:
            st.warning("Please create a game schedule first")
        else:
            # Select a game to create a fielding rotation for
            game_options = schedule_df["Game #"].tolist()
            selected_game = st.selectbox("Select a game", game_options, key="fielding_game_select")
            
            # Get the game information
            game_info = schedule_df[schedule_df["Game #"] == selected_game].iloc[0]
            innings = game_info["Innings"]
            
            # Format date and time
            game_date_time = f"{game_info['Date']}"
            if "Time" in game_info and pd.notna(game_info["Time"]):
                # Format the time
                time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else game_info["Time"]
                game_date_time += f" at {time_str}"

            st.write(f"Game {selected_game} vs {game_info['Opponent']} on {game_date_time} ({innings} innings)")
            
            # Get fielding rotations from database
            fielding_rotations = db.get_fielding_rotations(st.session_state.team_id)
            
            # Initialize fielding rotation for this game if needed
            if selected_game not in fielding_rotations:
                fielding_rotations[selected_game] = {}
                
            # Initialize positions for all innings if needed
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                if inning_key not in fielding_rotations[selected_game]:
                    # Initialize with default positions for each player
                    positions = {}
                    for i, player in roster_df.iterrows():
                        jersey = str(player["Jersey Number"])
                        if i < len(POSITIONS) - 1:  # All but bench
                            positions[jersey] = POSITIONS[i]
                        else:
                            positions[jersey] = "Bench"
                    
                    # Save the positions to the database
                    db.update_fielding_rotation(st.session_state.team_id, selected_game, inning, positions)
                    
                    # Update local copy
                    fielding_rotations[selected_game][inning_key] = positions
            
            # Get player info
            roster_df["Player"] = roster_df["First Name"] + " " + roster_df["Last Name"] + " (#" + roster_df["Jersey Number"].astype(str) + ")"
            
            # Get player availability from database
            player_availability = db.get_player_availability(st.session_state.team_id)
            
            # Get availability information
            availability = {}  # Default all players as available
            can_play_catcher = {}  # Default no players can play catcher
            
            if selected_game in player_availability:
                availability = player_availability[selected_game]["Available"]
                can_play_catcher = player_availability[selected_game]["Can Play Catcher"]
                
                # Add availability warning
                unavailable_count = sum(1 for available in availability.values() if not available)
                if unavailable_count > 0:
                    st.warning(f"{unavailable_count} player(s) marked as unavailable. They will show 'OUT' in all innings.")
                
                # Add catcher information
                catcher_count = sum(1 for can_catch in can_play_catcher.values() if can_catch)
                if catcher_count == 0:
                    st.error("No players marked as capable of playing catcher. Please update player setup.")
                else:
                    # Get the names of available catchers
                    catcher_names = []
                    for jersey, can_catch in can_play_catcher.items():
                        if can_catch:
                            player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
                            if not player_rows.empty:
                                catcher_names.append(player_rows.iloc[0]["Player"])
                    
                    st.info(f"Players who can play catcher: {', '.join(catcher_names)}")
            
            # Create a table for all innings at once
            st.subheader("Fielding Positions for All Innings")
            
            # Create a table layout with player names in the leftmost column and innings across the top
            col_headers = ["Player"]
            for i in range(1, innings + 1):
                col_headers.append(f"Inning {i}")
            
            # Create an empty DataFrame for the fielding grid
            fielding_grid = pd.DataFrame(index=range(len(roster_df)), columns=col_headers)
            fielding_grid["Player"] = roster_df["Player"].tolist()
            
            # Fill in the positions or OUT for unavailable players
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                inning_col = f"Inning {inning}"
                
                if inning_key in fielding_rotations[selected_game]:
                    positions = fielding_rotations[selected_game][inning_key]
                    
                    for i, player in roster_df.iterrows():
                        jersey = str(player["Jersey Number"])
                        
                        # Check availability
                        is_available = availability.get(jersey, True)
                        
                        if not is_available:
                            # Player is unavailable - display OUT
                            fielding_grid.loc[i, inning_col] = "OUT"
                        elif jersey in positions:
                            # Player is available - display position
                            fielding_grid.loc[i, inning_col] = positions[jersey]
                        else:
                            # Default to bench for any missing positions
                            fielding_grid.loc[i, inning_col] = "Bench"
            
            # Set index to start at 1
            fielding_grid.index = range(1, len(fielding_grid) + 1)
            
            # Create a list of options for the selectbox - regular positions plus OUT
            position_options = POSITIONS.copy()
            position_options.append("OUT")
            
            # Display the editable grid
            edited_grid = st.data_editor(
                fielding_grid,
                use_container_width=True,
                column_config={
                    "Player": st.column_config.TextColumn("Player", disabled=True),
                    **{f"Inning {i}": st.column_config.SelectboxColumn(
                        f"Inning {i}", 
                        options=position_options,
                        width="medium",
                        help=f"Position for inning {i}"
                    ) for i in range(1, innings + 1)}
                },
                hide_index=False,
            )
            
            # Save button for all innings
            if st.button("Save Fielding Positions", key="save_fielding"):
                # Extract the updated positions from the edited grid
                for inning in range(1, innings + 1):
                    inning_key = f"Inning {inning}"
                    inning_col = f"Inning {inning}"
                    
                    # Create a fresh dictionary for this inning
                    updated_positions = {}
                    
                    # Map positions to jersey numbers
                    for i, row in edited_grid.iterrows():
                        i_adj = i - 1  # Adjust for 1-based index
                        if i_adj < len(roster_df):
                            jersey = str(roster_df.iloc[i_adj]["Jersey Number"])
                            position = row[inning_col]
                            
                            # Store the position
                            updated_positions[jersey] = position
                    
                    # Save positions to the database
                    db.update_fielding_rotation(st.session_state.team_id, selected_game, inning, updated_positions)
                
                st.success("Fielding positions saved for all innings!")
                
            # Position validation
            st.subheader("Position Coverage Check")
            if st.button("Validate Positions", key="validate_positions"):
                errors = []
                warnings = []
                
                # Track positions played by each player across all innings
                player_positions = {}
                # Track infield/outfield by player and inning for consecutive check
                player_field_types = {}
                
                for inning in range(1, innings + 1):
                    inning_key = f"Inning {inning}"
                    inning_col = f"Inning {inning}"
                    
                    # Get positions for this inning
                    positions_dict = {}
                    for i, row in edited_grid.iterrows():
                        i_adj = i - 1  # Adjust for 1-based index
                        if i_adj < len(roster_df):
                            jersey = str(roster_df.iloc[i_adj]["Jersey Number"])
                            position = row[inning_col]
                            positions_dict[jersey] = position
                    
                    # Get list of positions (excluding bench and OUT)
                    positions = [pos for pos in positions_dict.values() if pos != "Bench" and pos != "OUT"]
                    
                    # Check for duplicate positions (except bench and OUT)
                    if len(positions) != len(set(positions)):
                        duplicates = [p for p in positions if positions.count(p) > 1]
                        errors.append(f"Inning {inning}: Duplicate position(s): {', '.join(set(duplicates))}")
                    
                    # Check that all required positions are filled
                    required_positions = [p for p in POSITIONS if p != "Bench"]
                    missing_positions = [p for p in required_positions if p not in positions]
                    if missing_positions:
                        errors.append(f"Inning {inning}: Missing position(s): {', '.join(missing_positions)}")
                    
                    # Check if unavailable players are assigned field positions
                    for jersey, position in positions_dict.items():
                        is_available = availability.get(jersey, True)
                        if not is_available and position != "OUT":
                            # Find player name
                            player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
                            if not player_rows.empty:
                                player_name = f"{player_rows.iloc[0]['First Name']} {player_rows.iloc[0]['Last Name']}"
                                warnings.append(f"Inning {inning}: Unavailable player {player_name} should be marked as OUT, not {position}")
                    
                    # Check if catcher position is assigned to a capable player
                    for jersey, position in positions_dict.items():
                        if position == "Catcher":
                            can_catch = can_play_catcher.get(jersey, False)
                            if not can_catch:
                                # Find player name
                                player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
                                if not player_rows.empty:
                                    player_name = f"{player_rows.iloc[0]['First Name']} {player_rows.iloc[0]['Last Name']}"
                                    warnings.append(f"Inning {inning}: Player {player_name} assigned to Catcher but not marked as capable")
                    
                    # Track positions by player for cross-inning validation
                    for jersey, position in positions_dict.items():
                        # Skip OUT positions
                        if position == "OUT":
                            continue
                            
                        # Initialize player tracking if needed
                        if jersey not in player_positions:
                            player_positions[jersey] = []
                        if jersey not in player_field_types:
                            player_field_types[jersey] = {}
                        
                        # Track this position for the player
                        player_positions[jersey].append(position)
                        
                        # Determine position type (infield or outfield) and track it
                        if position in INFIELD:
                            field_type = "infield"
                        elif position in OUTFIELD:
                            field_type = "outfield"
                        else:
                            field_type = "bench"  # Bench or other
                        
                        player_field_types[jersey][inning] = field_type
                
                # Check for players playing the same position multiple times
                for jersey, positions in player_positions.items():
                    # Find player name for better error messages
                    player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
                    player_name = f"Jersey #{jersey}"
                    if not player_rows.empty:
                        player_name = f"{player_rows.iloc[0]['First Name']} {player_rows.iloc[0]['Last Name']} (#{jersey})"
                    
                    if len(positions) != len(set(positions)) and "Bench" not in positions:
                        position_counts = {}
                        for pos in positions:
                            if pos != "Bench":  # We allow multiple bench assignments
                                position_counts[pos] = position_counts.get(pos, 0) + 1
                        
                        duplicates = [f"{pos} ({count} times)" for pos, count in position_counts.items() if count > 1]
                        if duplicates:
                            errors.append(f"Player {player_name} plays the same position multiple times: {', '.join(duplicates)}")
                
                # Check for consecutive infield/outfield innings
                for jersey, innings_dict in player_field_types.items():
                    # Find player name for better error messages
                    player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
                    player_name = f"Jersey #{jersey}"
                    if not player_rows.empty:
                        player_name = f"{player_rows.iloc[0]['First Name']} {player_rows.iloc[0]['Last Name']} (#{jersey})"
                    
                    # Sort innings in numerical order
                    sorted_innings = sorted(innings_dict.keys())
                    
                    for i in range(1, len(sorted_innings)):
                        current_inning = sorted_innings[i]
                        prev_inning = sorted_innings[i-1]
                        
                        if current_inning == prev_inning + 1:  # Consecutive innings
                            current_type = innings_dict[current_inning]
                            prev_type = innings_dict[prev_inning]
                            
                            if (current_type == "infield" and prev_type == "infield") or \
                               (current_type == "outfield" and prev_type == "outfield"):
                                errors.append(
                                    f"Player {player_name} plays {current_type} in consecutive innings {prev_inning} and {current_inning}"
                                )
                
                # Display errors and warnings
                if errors:
                    for error in errors:
                        st.error(error)
                elif warnings:
                    for warning in warnings:
                        st.warning(warning)
                    st.success("All positions are properly assigned but with some warnings.")
                else:
                    st.success("All positions are properly assigned for each inning!")
                    st.info("Note: It's normal to have multiple players on the bench.")
            
            # Add auto-assign feature for unavailable players
            if st.button("Auto-assign Unavailable Players", key="auto_assign_out"):
                updated = False
                for inning in range(1, innings + 1):
                    inning_key = f"Inning {inning}"
                    
                    if inning_key in fielding_rotations[selected_game]:
                        positions = fielding_rotations[selected_game][inning_key].copy()
                        
                        # Set unavailable players to OUT
                        for jersey in positions.keys():
                            is_available = availability.get(jersey, True)
                            if not is_available and positions[jersey] != "OUT":
                                positions[jersey] = "OUT"
                                updated = True
                        
                        # Update the database if changes were made
                        if updated:
                            db.update_fielding_rotation(st.session_state.team_id, selected_game, inning, positions)
                
                if updated:
                    st.success("Updated all unavailable players to OUT")
                    st.rerun()
                else:
                    st.info("All unavailable players are already marked as OUT")
            
            # Add individual game fairness analysis
            st.subheader("Game Fielding Fairness")
            
            # Calculate fairness for the selected game
            if selected_game in fielding_rotations:
                # Create a fairness dataframe for this game
                game_fairness = pd.DataFrame(
                    0, 
                    index=roster_df["Player"], 
                    columns=["Infield", "Outfield", "Bench", "OUT", "Total Innings"]
                )
                
                # Get game details
                game_info = schedule_df[schedule_df["Game #"] == selected_game].iloc[0]
                innings = game_info["Innings"]
                
                # Process each inning
                for inning in range(1, innings + 1):
                    inning_key = f"Inning {inning}"
                    
                    if inning_key in fielding_rotations[selected_game]:
                        positions = fielding_rotations[selected_game][inning_key]
                        
                        for jersey, position in positions.items():
                            # Find the player with this jersey number
                            player_rows = roster_df[roster_df["Jersey Number"].astype(str) == jersey]
                            if not player_rows.empty:
                                player = player_rows.iloc[0]["Player"]
                                
                                # Update total innings
                                game_fairness.loc[player, "Total Innings"] += 1
                                
                                # Update position counts
                                if position == "OUT":
                                    game_fairness.loc[player, "OUT"] += 1
                                elif position in INFIELD:
                                    game_fairness.loc[player, "Infield"] += 1
                                elif position in OUTFIELD:
                                    game_fairness.loc[player, "Outfield"] += 1
                                elif position in BENCH:
                                    game_fairness.loc[player, "Bench"] += 1
                
                # Calculate percentages
                for col in ["Infield", "Outfield", "Bench", "OUT"]:
                    game_fairness[f"{col} %"] = (game_fairness[col] / game_fairness["Total Innings"] * 100).round(1)
                
                # Filter out players with no innings
                game_fairness = game_fairness[game_fairness["Total Innings"] > 0]
                
                # Display the table
                st.dataframe(game_fairness[["Infield", "Outfield", "Bench", "OUT", "Total Innings", 
                                           "Infield %", "Outfield %", "Bench %", "OUT %"]])
            
            st.info("💡 To see position distribution and fairness across all games, visit the 'Fielding Fairness' tab.")
        
            # Instructions on manual rotation setup
            st.markdown("---")
            st.subheader("Manual Fielding Rotation Tips")
            st.info("""
            **Tips for creating balanced fielding rotations:**
            
            1. **Track playing time**: Ensure all players get similar field time over the season
            2. **Rotate positions**: Give players experience in different positions
            3. **Consider player skills**: Balance development with team success
            4. **Check player availability**: Unavailable players are shown as OUT
            5. **Validate positions**: Use the validation button to check for errors
            
            **Important Rotation Rules:**
            
            - No player should play the same position multiple times in one game
            - Players should not play infield or outfield in consecutive innings (must alternate or have bench time in between)
            - Infield positions: Pitcher, 1B, 2B, 3B, SS
            - Outfield positions: Catcher, LF, RF, LC, RC
            
            Create rotations by assigning positions to each player for each inning.
            """)
            
            # Add the Claude AI rotation generator
            add_claude_rotation_generator(st.session_state.team_id, selected_game)
            
            # Add statistics visualization for the plan
            if 'claude_fielding_plan' in st.session_state:
                add_plan_statistics()
    
    # Tab 6: Batting Fairness Analysis
    elif selected_tab == "Batting Fairness":
        # Get roster from database
        roster_df = db.get_roster(st.session_state.team_id)
        
        if roster_df.empty:
            st.warning("Please upload a team roster first")
        else:
            # Analyze batting fairness
            batting_fairness = db.analyze_batting_fairness(st.session_state.team_id)
            
            if batting_fairness is not None and not batting_fairness.empty:
                st.subheader("Batting Position Distribution")
                st.write("Number of times each player bats in each position across all games:")
                st.dataframe(batting_fairness)
                
                # Add visualization of the batting fairness
                st.subheader("Visualization")
                
                # Create bar chart for each player
                st.write("Average batting position for each player:")
                
                # Calculate average position
                avg_positions = pd.DataFrame({
                    'Player': batting_fairness.index,
                    'Avg Position': batting_fairness.multiply(batting_fairness.columns).sum(axis=1) / batting_fairness.sum(axis=1)
                }).sort_values('Avg Position')
                
                # Display as a bar chart using Streamlit
                st.bar_chart(avg_positions.set_index('Player'))
                
                # Add some explanations
                st.markdown("""
                ### Interpreting the Results
                
                The table above shows how many times each player has batted in each position across all games.
                Ideally, you want this distribution to be relatively even so all players get experience
                in different parts of the batting order.
                
                **Good batting order rotation practices:**
                
                - Players should experience both early and late positions in the order
                - No player should be consistently placed in the last positions
                - Consider skill levels but balance with fairness
                - Rotate consistently throughout the season
                
                Use this analysis to identify players who might need more opportunities in different
                batting positions in upcoming games.
                """)
            else:
                st.warning("No batting order data available yet. Create batting orders first.")

    # Tab 7: Fielding Fairness Analysis
    elif selected_tab == "Fielding Fairness":
        # Get roster from database
        roster_df = db.get_roster(st.session_state.team_id)
        
        if roster_df.empty:
            st.warning("Please upload a team roster first")
        else:
            # Analyze fielding fairness
            fielding_fairness = db.analyze_fielding_fairness(st.session_state.team_id)
            
            if fielding_fairness is not None and not fielding_fairness.empty:
                st.subheader("Fielding Position Distribution")
                st.write("Distribution of infield, outfield, and bench time for each player:")
                
                # Select columns to display
                display_cols = ["Infield", "Outfield", "Bench", "Total Innings", 
                              "Infield %", "Outfield %", "Bench %"]
                st.dataframe(fielding_fairness[display_cols])
                
                # Add visualization
                st.subheader("Position Type Distribution")
                
                # Prepare data for the chart
                chart_data = fielding_fairness[["Infield %", "Outfield %", "Bench %"]].copy()
                
                # Display as a bar chart
                st.bar_chart(chart_data)
                
                # Add detailed analysis
                st.subheader("Detailed Analysis")
                
                # Calculate statistics
                avg_bench = fielding_fairness["Bench %"].mean().round(1)
                max_bench = fielding_fairness["Bench %"].max().round(1)
                min_bench = fielding_fairness["Bench %"].min().round(1)
                bench_std = fielding_fairness["Bench %"].std().round(1)
                
                # Display the statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Avg Bench Time", f"{avg_bench}%")
                with col2:
                    st.metric("Max Bench Time", f"{max_bench}%")
                with col3:
                    st.metric("Min Bench Time", f"{min_bench}%")
                
                st.write(f"**Standard Deviation (Bench):** {bench_std}% - Lower values indicate more balanced bench time")
                
                # Add interpretation guidance
                st.markdown("""
                ### Interpreting the Results
                
                The fielding position distribution shows how much time each player spends in different parts
                of the field across all games and innings.
                
                **What to look for:**
                
                - Bench time should be fairly distributed among all players
                - Players should experience both infield and outfield positions when possible
                - Consider player skills and preferences while maintaining fairness
                - A lower standard deviation in bench time percentage indicates more balanced rotations
                
                Use this analysis to identify adjustments needed for upcoming games to balance playing time
                and field experience.
                """)
            else:
                st.warning("No fielding rotation data available yet. Create fielding rotations first.")

    # Tab 8: Game Summary
    elif selected_tab == "Game Summary":
        # Get roster and schedule from database
        roster_df = db.get_roster(st.session_state.team_id)
        schedule_df = db.get_schedule(st.session_state.team_id)
        
        if roster_df.empty:
            st.warning("Please upload a team roster first")
        elif schedule_df.empty:
            st.warning("Please create a game schedule first")
        else:
            # Get batting orders from database
            batting_orders = db.get_batting_orders(st.session_state.team_id)
            
            # Get fielding rotations from database
            fielding_rotations = db.get_fielding_rotations(st.session_state.team_id)
            
            if not batting_orders or not fielding_rotations:
                st.warning("Please create batting orders and fielding rotations first")
            else:
                # Select a game to summarize
                game_options = schedule_df["Game #"].tolist()
                selected_game = st.selectbox("Select a game to summarize", game_options, key="summary_game_select")
                
                # Get the game information (with validation)
                filtered_games = schedule_df[schedule_df["Game #"] == selected_game]
                if filtered_games.empty:
                    st.error(f"Game {selected_game} not found in schedule")
                    return
                
                game_info = filtered_games.iloc[0]
                innings = game_info.get("Innings", 6)  # Default to 6 innings if not specified
                
                st.subheader(f"Game {selected_game} Summary")
                
                # Display team information
                team_info = db.get_team_info(st.session_state.team_id)
                if team_info and team_info.get("team_name"):
                    team_col1, team_col2 = st.columns(2)
                    with team_col1:
                        st.write(f"**Team:** {team_info['team_name']}")
                        if team_info.get("league"):
                            st.write(f"**League:** {team_info['league']}")
                    
                    with team_col2:
                        if team_info.get("head_coach"):
                            coach_text = f"**Head Coach:** {team_info['head_coach']}"
                            st.write(coach_text)
                        
                        asst_coaches = []
                        if team_info.get("assistant_coach1"):
                            asst_coaches.append(team_info["assistant_coach1"])
                        if team_info.get("assistant_coach2"):
                            asst_coaches.append(team_info["assistant_coach2"])
                        
                        if asst_coaches:
                            st.write(f"**Assistant Coach(es):** {', '.join(asst_coaches)}")
                
                # Display game information with validation
                opponent = game_info.get("Opponent", "Unknown")
                st.write(f"**Opponent:** {opponent}")
                
                # Update this line to include time if available (with validation)
                if "Time" in game_info and pd.notna(game_info["Time"]):
                    # Format the time with validation
                    try:
                        time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else str(game_info["Time"])
                    except (AttributeError, TypeError):
                        time_str = "Unknown"
                    
                    # Format the date without time component
                    try:
                        date_str = game_info['Date'].strftime("%Y-%m-%d") if isinstance(game_info['Date'], pd.Timestamp) else str(game_info['Date'])
                    except (AttributeError, TypeError):
                        date_str = "Unknown"
                    
                    st.write(f"**Date/Time:** {date_str} at {time_str}")
                elif "Date" in game_info and pd.notna(game_info["Date"]):
                    try:
                        date_str = game_info['Date'].strftime("%Y-%m-%d") if isinstance(game_info['Date'], pd.Timestamp) else str(game_info['Date'])
                        st.write(f"**Date:** {date_str}")
                    except (AttributeError, TypeError):
                        st.write("**Date:** Unknown")
                else:
                    st.write("**Date:** Not scheduled")
                    
                st.write(f"**Innings:** {innings}")
                
                # Check if we have data for this game
                if selected_game in batting_orders and selected_game in fielding_rotations:
                    # Get roster data
                    roster_df["Player Name"] = roster_df["First Name"] + " " + roster_df["Last Name"]
                    
                    # Get batting order as jersey numbers
                    batting_order = batting_orders[selected_game]
                    
                    # Get fielding data
                    fielding_data = fielding_rotations[selected_game]
                    
                    # Get player availability
                    player_availability = db.get_player_availability(st.session_state.team_id)
                    availability = {}
                    if selected_game in player_availability:
                        availability = player_availability[selected_game]["Available"]
                    
                    # Create a comprehensive game summary table
                    st.subheader("Game Plan")
                    
                    # Initialize columns for the summary dataframe
                    columns = ["Batting Order", "Jersey #", "Player Name", "Available"]
                    for i in range(1, innings + 1):
                        columns.append(f"Inning {i}")
                    
                    # Create empty dataframe with the columns
                    summary_df = pd.DataFrame(columns=columns)
                    
                    # Create a mapping from jersey to player info
                    jersey_to_player = {}
                    for _, player in roster_df.iterrows():
                        jersey = str(player["Jersey Number"])
                        jersey_to_player[jersey] = {
                            "Name": player["Player Name"],
                            "Jersey": jersey
                        }
                    
                    # Display players in batting order first
                    for batting_pos, jersey in enumerate(batting_order, 1):
                        if jersey in jersey_to_player:
                            player = jersey_to_player[jersey]
                            
                            # Check availability
                            is_available = availability.get(jersey, True)
                            
                            # Initialize row data with player info
                            row_data = {
                                "Batting Order": "OUT" if not is_available else batting_pos,
                                "Jersey #": player["Jersey"],
                                "Player Name": player["Name"],
                                "Available": "Yes" if is_available else "No"
                            }
                            
                            # Add fielding positions for each inning
                            for inning in range(1, innings + 1):
                                inning_key = f"Inning {inning}"
                                if inning_key in fielding_data and jersey in fielding_data[inning_key]:
                                    position = fielding_data[inning_key][jersey]
                                    # If position isn't already OUT but player is unavailable, show OUT
                                    if not is_available and position != "OUT":
                                        row_data[f"Inning {inning}"] = "OUT"
                                    else:
                                        row_data[f"Inning {inning}"] = position
                                else:
                                    row_data[f"Inning {inning}"] = "N/A"
                            
                            # Add this player's row to the dataframe
                            summary_df = pd.concat([summary_df, pd.DataFrame([row_data])], ignore_index=True)
                    
                    # Add any players that aren't in the batting order
                    all_jerseys = set(jersey_to_player.keys())
                    batting_jerseys = set(batting_order)
                    missing_jerseys = all_jerseys - batting_jerseys
                    
                    for jersey in missing_jerseys:
                        if jersey in jersey_to_player:
                            player = jersey_to_player[jersey]
                            
                            # Check availability
                            is_available = availability.get(jersey, True)
                            
                            # Initialize row data with player info
                            row_data = {
                                "Batting Order": "OUT" if not is_available else "Bench",
                                "Jersey #": player["Jersey"],
                                "Player Name": player["Name"],
                                "Available": "Yes" if is_available else "No"
                            }
                            
                            # Add fielding positions for each inning
                            for inning in range(1, innings + 1):
                                inning_key = f"Inning {inning}"
                                if inning_key in fielding_data and jersey in fielding_data[inning_key]:
                                    position = fielding_data[inning_key][jersey]
                                    # If position isn't already OUT but player is unavailable, show OUT
                                    if not is_available and position != "OUT":
                                        row_data[f"Inning {inning}"] = "OUT"
                                    else:
                                        row_data[f"Inning {inning}"] = position
                                else:
                                    row_data[f"Inning {inning}"] = "N/A"
                            
                            # Add this player's row to the dataframe
                            summary_df = pd.concat([summary_df, pd.DataFrame([row_data])], ignore_index=True)
                    
                    # Display the comprehensive summary table
                    # Add index starting from 1 instead of 0
                    summary_df.index = range(1, len(summary_df) + 1)
                    st.dataframe(summary_df, use_container_width=True)
                    
                    # Export options
                    st.subheader("Export Game Plan")
                    
                    export_col1, export_col2 = st.columns(2)
                    
                    with export_col1:
                        # Generate and allow download of PDF
                        if st.button("Generate PDF Game Plan"):
                            try:
                                # Create PDF using the function
                                pdf_buffer = generate_game_plan_pdf(st.session_state.team_id, selected_game)
                                
                                # Offer download button for the PDF
                                st.download_button(
                                    label="Download PDF Game Plan",
                                    data=pdf_buffer,
                                    file_name=f"game_{selected_game}_lineup.pdf",
                                    mime="application/pdf"
                                )
                                
                                # Show success message
                                st.success("PDF generated successfully! Click the download button above.")
                            except Exception as e:
                                st.error(f"Error generating PDF: {str(e)}")
                                st.info("Make sure you have the ReportLab library installed. Run: pip install reportlab")
                    
                    with export_col2:
                        # Text version option
                        if st.button("Generate Text Game Plan"):
                            # Create a string buffer
                            buffer = io.StringIO()
                            
                            # Write game info
                            team_info = db.get_team_info(st.session_state.team_id)
                            if team_info["team_name"]:
                                team_name = team_info["team_name"]
                                league = team_info["league"]
                                head_coach = team_info["head_coach"]
                                
                                team_header = f"{team_name}"
                                if league:
                                    team_header += f" ({league})"
                                
                                buffer.write(f"TEAM: {team_header}\n")
                                
                                coach_text = f"COACH: {head_coach}"
                                asst1 = team_info["assistant_coach1"]
                                asst2 = team_info["assistant_coach2"]
                                if asst1 or asst2:
                                    coach_text += " | ASSISTANTS: "
                                    if asst1:
                                        coach_text += asst1
                                    if asst1 and asst2:
                                        coach_text += ", " 
                                    if asst2:
                                        coach_text += asst2
                                
                                if head_coach:
                                    buffer.write(f"{coach_text}\n")
                            
                            # Update to include time if available
                            if "Time" in game_info and pd.notna(game_info["Time"]):
                                # Format the time
                                time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else game_info["Time"]
                                
                                # Format the date without time component
                                date_str = game_info['Date'].strftime("%Y-%m-%d") if isinstance(game_info['Date'], pd.Timestamp) else game_info['Date']
                                
                                game_date_time = f"{date_str} at {time_str}"
                            else:
                                game_date_time = f"{game_info['Date']}"
                            
                            buffer.write(f"GAME {selected_game} LINEUP - {game_info['Opponent']} - {game_date_time}\n")
                            buffer.write("=" * 80 + "\n\n")
                            
                            # Convert dataframe to text format
                            text_table = summary_df.to_string(index=False)
                            buffer.write(text_table)
                            buffer.write("\n\n")
                            
                            # Add legend
                            buffer.write("POSITION LEGEND:\n")
                            buffer.write("-" * 20 + "\n")
                            buffer.write("P - Pitcher, C - Catcher, 1B - First Base, 2B - Second Base, 3B - Third Base\n")
                            buffer.write("SS - Shortstop, LF - Left Field, RF - Right Field, LC - Left Center, RC - Right Center\n")
                            buffer.write("OUT - Player Unavailable\n")
                            
                            # Get the text from the buffer
                            summary_text = buffer.getvalue()
                            
                            # Display the summary
                            st.text_area("Game Plan", summary_text, height=400)
                            
                            # Create a download link
                            st.download_button(
                                label="Download Text Game Plan",
                                data=summary_text,
                                file_name=f"game_{selected_game}_lineup.txt",
                                mime="text/plain"
                            )
                else:
                    st.warning(f"No batting order or fielding rotation data for Game {selected_game}")

    # Tab 9: Data Management / Team Management
    elif selected_tab == "Data Management":
        st.header("Team Management")
        st.write("Create, select, or delete teams in your database.")
        
        # Get all teams for display
        from database import get_db_session, Team
    
        # Show current teams
        # Get list of teams for the current user
        teams = database.get_teams_with_details_for_user(st.session_state.user_id)
        if teams:
            st.subheader("Current Teams")
            
            # Create a table of teams
            team_df = pd.DataFrame(teams)
            team_df.columns = ["ID", "Team Name", "League", "Head Coach"]
            # Add 1-based index
            team_df.index = range(1, len(team_df) + 1)
            st.dataframe(team_df, use_container_width=True)
            
            # Current team indicator
            if st.session_state.team_id is not None:
                current_team = next((t for t in teams if t["id"] == st.session_state.team_id), None)
                if current_team:
                    st.info(f"You are currently working with team: **{current_team['name']}**")
        else:
            st.info("No teams found in the database. Create your first team below.")
        
        # Team creation section
        st.subheader("Create New Team")
        with st.form("create_team_form_management"):
            new_team_name = st.text_input("Team Name", placeholder="Enter team name")
            col1, col2 = st.columns(2)
            with col1:
                new_league = st.text_input("League", placeholder="Optional")
            with col2:
                new_head_coach = st.text_input("Head Coach", placeholder="Optional")
            
            col3, col4 = st.columns(2)
            with col3:
                new_asst_coach1 = st.text_input("Assistant Coach 1", placeholder="Optional")
            with col4:
                new_asst_coach2 = st.text_input("Assistant Coach 2", placeholder="Optional")
            
            submit_new_team = st.form_submit_button("Create Team")
            
            if submit_new_team:
                if not new_team_name:
                    st.error("Team name is required")
                else:
                    team_info = {
                        "team_name": new_team_name,
                        "league": new_league,
                        "head_coach": new_head_coach,
                        "assistant_coach1": new_asst_coach1,
                        "assistant_coach2": new_asst_coach2
                    }
                    
                    # Create the team in the database with user association
                    team_id = database.create_team_with_user(team_info, st.session_state.user_id)
                    
                    st.success(f"Created new team: {new_team_name}")
                    
                    # Initialize session state if not already done
                    if 'team_id' not in st.session_state:
                        st.session_state.team_id = None
                        
                    # Ask if they want to switch to this team
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if st.button("Switch to new team"):
                            st.session_state.team_id = team_id
                            st.rerun()
        
        # Team selection section
        if teams:
            st.subheader("Switch Team")
            
            # Create a selectbox of teams to switch to
            switch_options = [(t["id"], t["name"]) for t in teams]
            selected_team_to_switch = st.selectbox(
                "Select team to work with:",
                options=switch_options,
                format_func=lambda x: x[1],
                key="data_management_team_switch"
            )
            
            if st.button("Switch to Selected Team"):
                selected_id, _ = selected_team_to_switch
                # Update session state
                st.session_state.team_id = selected_id
                st.rerun()
        
        # Team deletion section
        if teams:
            st.subheader("Delete Team")
            
            # Add team deletion functionality
            with st.expander("Delete a Team", expanded=False):
                st.warning("Caution: Deleting a team will remove all associated data including roster, schedule, and game plans.")
                
                # Add function to delete team from database
                def delete_team(team_id):
                    """Delete a team and all its associated data"""
                    session = get_db_session()
                    try:
                        team = session.query(Team).filter(Team.id == team_id).one()
                        team_name = team.name
                        session.delete(team)
                        session.commit()
                        return True, team_name
                    except Exception as e:
                        session.rollback()
                        return False, str(e)
                    finally:
                        session.close()
                
                # Create a selectbox of teams to delete
                delete_options = [(t["id"], t["name"]) for t in teams]
                selected_team_to_delete = st.selectbox(
                    "Select team to delete:",
                    options=delete_options,
                    format_func=lambda x: x[1],
                    key="data_management_team_delete"
                )
                
                # Confirmation flow with team name typing
                st.write("To confirm deletion, type the team name below:")
                
                confirm_name = st.text_input("Type team name to confirm")
                
                if st.button("Delete Team Permanently"):
                    selected_id, selected_name = selected_team_to_delete
                    
                    if confirm_name == selected_name:
                        # Don't allow deleting the currently active team
                        if selected_id == st.session_state.team_id:
                            st.error("You cannot delete the currently active team. Please switch teams first.")
                        else:
                            # Delete the team
                            success, result = delete_team(selected_id)
                            
                            if success:
                                st.success(f"Team '{result}' has been permanently deleted.")
                                st.button("Refresh List", on_click=st.rerun)
                            else:
                                st.error(f"Error deleting team: {result}")
                    else:
                        st.error("Team name doesn't match. Deletion canceled.")
    
    # Add information about database persistence
    st.markdown("---")
    st.subheader("About Database Storage")
    st.info("""
    - All your team data is stored in a secure PostgreSQL database
    - Your data persists automatically between sessions
    - Changes are saved immediately as you work
    - Access your data from any device
    - No need for manual imports or exports
    """)

# Footer
def display_footer():
    st.markdown("---")
    st.markdown("LineupBoss - Helping coaches create fair and balanced rotations")
    
    # Add a feedback/status section in the sidebar
    st.sidebar.markdown("---")
    with st.sidebar.expander("App Status"):
        # Get team info
        team_info = db.get_team_info(st.session_state.team_id) if st.session_state.team_id else None
        
        if st.session_state.team_id is None:
            st.write("**No team selected**")
        else:
            st.write(f"**Current Team:** {team_info['team_name']}")
            
            # Display status of loaded data
            roster_df = db.get_roster(st.session_state.team_id)
            schedule_df = db.get_schedule(st.session_state.team_id)
            batting_orders = db.get_batting_orders(st.session_state.team_id)
            fielding_rotations = db.get_fielding_rotations(st.session_state.team_id)
            
            roster_status = "✅ Loaded" if not roster_df.empty else "❌ Not loaded"
            schedule_status = "✅ Loaded" if not schedule_df.empty else "❌ Not loaded"
            batting_status = "✅ Configured" if batting_orders else "❌ Not configured"
            fielding_status = "✅ Configured" if fielding_rotations else "❌ Not configured"
            
            st.write(f"**Team Roster:** {roster_status}")
            st.write(f"**Game Schedule:** {schedule_status}")
            st.write(f"**Batting Orders:** {batting_status}")
            st.write(f"**Fielding Rotations:** {fielding_status}")

    # Add team management option
    if st.session_state.team_id is not None:
        st.sidebar.markdown("---")
        if st.sidebar.button("Team Management"):
            st.session_state.active_tab = "Data Management"
            st.rerun()

    # Add app info in sidebar footer
    st.sidebar.markdown("---")
    st.sidebar.info("LineupBoss v2.0 (Database Edition)")

if __name__ == "__main__":
    main()
    display_footer()