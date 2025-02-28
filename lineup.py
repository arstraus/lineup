import streamlit as st
import pandas as pd
import numpy as np
import io
import base64
import json

# Set page config
st.set_page_config(
    page_title="Baseball Lineup Manager",
    page_icon="⚾",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'roster' not in st.session_state:
    st.session_state.roster = None
if 'schedule' not in st.session_state:
    st.session_state.schedule = None
if 'batting_orders' not in st.session_state:
    st.session_state.batting_orders = {}
if 'fielding_rotations' not in st.session_state:
    st.session_state.fielding_rotations = {}

# Define positions
POSITIONS = ["Pitcher", "Catcher", "1B", "2B", "3B", "SS", "LF", "RF", "LC", "RC", "Bench"]
INFIELD = ["Pitcher", "1B", "2B", "3B", "SS"]
OUTFIELD = ["Catcher", "LF", "RF", "LC", "RC"]
BENCH = ["Bench"]

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

def analyze_batting_fairness():
    """Analyze the fairness of batting orders across all games"""
    if not st.session_state.roster is None and st.session_state.batting_orders:
        # Create a dataframe to count the number of times each player bats in each position
        players = st.session_state.roster.copy()
        players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
        
        # Initialize counters
        num_players = len(players)
        batting_counts = pd.DataFrame(0, index=players["Player"], columns=range(1, num_players + 1))
        
        # Count the batting positions for each player across all games
        for game_id, batting_order in st.session_state.batting_orders.items():
            for i, player_idx in enumerate(batting_order, 1):
                player = players.iloc[player_idx]["Player"]
                batting_counts.loc[player, i] += 1
        
        return batting_counts
    return None

def analyze_fielding_fairness():
    """Analyze the fairness of fielding positions across all games"""
    if not st.session_state.roster is None and st.session_state.fielding_rotations:
        # Create a dataframe to count the position types for each player
        players = st.session_state.roster.copy()
        players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
        
        # Initialize counters for infield, outfield, and bench positions
        position_counts = pd.DataFrame(0, index=players["Player"], columns=["Infield", "Outfield", "Bench", "Total Innings"])
        
        # Count the position types for each player across all games
        for game_id, fielding_data in st.session_state.fielding_rotations.items():
            game_info = next((g for g in st.session_state.schedule.to_dict('records') if g['Game #'] == game_id), None)
            if game_info:
                innings = game_info.get('Innings', 6)  # Default to 6 if not specified
                
                for inning in range(1, innings + 1):
                    inning_key = f"Inning {inning}"
                    if inning_key in fielding_data:
                        for player_idx, position in enumerate(fielding_data[inning_key]):
                            player = players.iloc[player_idx]["Player"]
                            position_counts.loc[player, "Total Innings"] += 1
                            
                            if position in INFIELD:
                                position_counts.loc[player, "Infield"] += 1
                            elif position in OUTFIELD:
                                position_counts.loc[player, "Outfield"] += 1
                            elif position in BENCH:
                                position_counts.loc[player, "Bench"] += 1
        
        # Calculate percentages
        for col in ["Infield", "Outfield", "Bench"]:
            position_counts[f"{col} %"] = (position_counts[col] / position_counts["Total Innings"] * 100).round(1)
            
        return position_counts
    return None

def generate_game_plan_pdf(game_id, game_info, batting_order, fielding_data, players):
    """Generate a PDF with the game plan"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    import io
    
    # Create a buffer for the PDF
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    section_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Create custom style for player names
    player_style = ParagraphStyle(
        'PlayerStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
    )
    
    # Add game header
    elements.append(Paragraph(f"Game {game_id} Plan", title_style))
    elements.append(Paragraph(f"Opponent: {game_info['Opponent']}", normal_style))
    elements.append(Paragraph(f"Date: {game_info['Date']}", normal_style))
    elements.append(Paragraph(f"Innings: {game_info['Innings']}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Add batting order section
    elements.append(Paragraph("Batting Order", section_style))
    
    # Create batting order table
    batting_data = []
    batting_data.append(["Order", "Player", "Jersey"])
    
    for i, player_idx in enumerate(batting_order, 1):
        player = players.iloc[player_idx]
        batting_data.append([
            str(i), 
            f"{player['First Name']} {player['Last Name']}", 
            f"#{player['Jersey Number']}"
        ])
    
    batting_table = Table(batting_data, colWidths=[0.5*inch, 2.5*inch, 0.75*inch])
    batting_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(batting_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Add fielding positions section
    elements.append(Paragraph("Fielding Positions", section_style))
    
    # Process each inning
    innings = game_info["Innings"]
    for inning in range(1, innings + 1):
        inning_key = f"Inning {inning}"
        
        if inning_key in fielding_data:
            elements.append(Paragraph(f"Inning {inning}", styles['Heading3']))
            
            # Sort positions in a sensible order
            position_assignments = []
            for p_idx, position in enumerate(fielding_data[inning_key]):
                if p_idx < len(players):
                    player = players.iloc[p_idx]
                    position_assignments.append({
                        "Player": f"{player['First Name']} {player['Last Name']}",
                        "Jersey": f"#{player['Jersey Number']}",
                        "Position": position,
                        "Order": POSITIONS.index(position)
                    })
            
            # Create a table for this inning's positions
            positions_data = []
            positions_data.append(["Position", "Player", "Jersey"])
            
            # Sort and add positions
            for pos in sorted(position_assignments, key=lambda x: x["Order"]):
                # Only include non-bench positions in the detailed layout
                if pos["Position"] != "Bench":
                    positions_data.append([pos["Position"], pos["Player"], pos["Jersey"]])
            
            # Add bench players at the end in a single row
            bench_players = [pos for pos in position_assignments if pos["Position"] == "Bench"]
            if bench_players:
                bench_names = ", ".join([f"{p['Player']} {p['Jersey']}" for p in bench_players])
                positions_data.append(["Bench", bench_names, ""])
            
            positions_table = Table(positions_data, colWidths=[1*inch, 2.5*inch, 0.75*inch])
            positions_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Highlight different position types with subtle background colors
                # Infield positions
                *[('BACKGROUND', (0, i), (0, i), colors.Color(0.9, 0.95, 1)) 
                  for i, row in enumerate(positions_data) 
                  if i > 0 and row[0] in INFIELD],
                # Outfield positions
                *[('BACKGROUND', (0, i), (0, i), colors.Color(0.9, 1, 0.9)) 
                  for i, row in enumerate(positions_data) 
                  if i > 0 and row[0] in OUTFIELD],
                # Bench position
                *[('BACKGROUND', (0, i), (0, i), colors.Color(1, 0.9, 0.9)) 
                  for i, row in enumerate(positions_data) 
                  if i > 0 and row[0] in BENCH],
            ]))
            
            elements.append(positions_table)
            elements.append(Spacer(1, 0.15*inch))
    
    # Add footer
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("Baseball Lineup Manager - Game Plan", 
                             ParagraphStyle('Footer', fontSize=8, textColor=colors.gray)))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF from the buffer
    buffer.seek(0)
    return buffer

def save_app_data():
    """Save all application data to a JSON file"""
    import json
    
    # Custom JSON encoder to handle pandas NaT and other special types
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            # Handle pandas NaT (Not a Time) values
            import pandas as pd
            import numpy as np
            if pd.isna(obj):
                return None
            # Handle numpy integer types
            if isinstance(obj, np.integer):
                return int(obj)
            # Handle numpy floating types
            if isinstance(obj, np.floating):
                return float(obj)
            # Handle other numpy arrays
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            # Handle pandas Timestamp objects
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            return super().default(obj)
    
    # Create data dictionary with all session state
    data = {
        "roster": st.session_state.roster.to_dict() if st.session_state.roster is not None else None,
        "schedule": st.session_state.schedule.to_dict() if st.session_state.schedule is not None else None,
        "batting_orders": st.session_state.batting_orders,
        "fielding_rotations": st.session_state.fielding_rotations
    }
    
    # Use the custom encoder to handle special data types
    return json.dumps(data, cls=CustomJSONEncoder)

def load_app_data(json_data):
    """Load application data from JSON"""
    data = json.loads(json_data)
    
    # Restore roster
    if data["roster"] is not None:
        st.session_state.roster = pd.DataFrame.from_dict(data["roster"])
    
    # Restore schedule
    if data["schedule"] is not None:
        schedule_df = pd.DataFrame.from_dict(data["schedule"])
        # Ensure Date column is datetime
        if "Date" in schedule_df.columns:
            schedule_df["Date"] = pd.to_datetime(schedule_df["Date"])
        st.session_state.schedule = schedule_df
    
    # Restore batting orders and fielding rotations
    st.session_state.batting_orders = data["batting_orders"]
    st.session_state.fielding_rotations = data["fielding_rotations"]
    
    # Convert dictionary string keys back to integers for game IDs
    st.session_state.batting_orders = {int(k) if k.isdigit() else k: v for k, v in st.session_state.batting_orders.items()}
    st.session_state.fielding_rotations = {int(k) if k.isdigit() else k: v for k, v in st.session_state.fielding_rotations.items()}

# Main app layout
st.title("⚾ Baseball Team Lineup Manager")

# Create tabs for different sections
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Team Roster", 
    "Game Schedule", 
    "Batting Order", 
    "Fielding Rotation", 
    "Batting Fairness", 
    "Fielding Fairness",
    "Game Summary",
    "Data Management"
])

# Tab 1: Team Roster
with tab1:
    st.header("Team Roster Management")
    
    # Option to download a template
    st.subheader("Download Roster Template")
    num_players = st.number_input("Number of players", min_value=1, max_value=30, value=14)
    template_df = create_empty_roster_template(num_players)
    st.markdown(get_csv_download_link(template_df, "roster_template.csv", "Download Roster Template"), unsafe_allow_html=True)
    
    # Option to upload a roster
    st.subheader("Upload Team Roster")
    roster_file = st.file_uploader("Upload your team roster CSV file", type=["csv"])
    
    if roster_file is not None:
        try:
            df = pd.read_csv(roster_file)
            valid, message = validate_roster(df)
            
            if valid:
                st.session_state.roster = df
                st.success("Roster uploaded successfully!")
                st.dataframe(df)
            else:
                st.error(message)
        except Exception as e:
            st.error(f"Error uploading file: {str(e)}")
    
    # Display current roster if it exists
    if st.session_state.roster is not None:
        st.subheader("Current Team Roster")
        st.dataframe(st.session_state.roster)

# Tab 2: Game Schedule
with tab2:
    st.header("Game Schedule")
    
    # Create or edit game schedule
    st.subheader("Create Game Schedule")
    
    # Initialize or display schedule
    if st.session_state.schedule is None:
        num_games = st.number_input("Number of games", min_value=1, max_value=50, value=10)
        
        if st.button("Initialize Schedule"):
            # Create schedule with proper data types
            schedule_data = []
            for i in range(1, num_games + 1):
                schedule_data.append({
                    "Game #": i,
                    "Date": None,
                    "Opponent": "",
                    "Innings": 6
                })
            st.session_state.schedule = pd.DataFrame(schedule_data)
            # Ensure Date column is datetime type
            st.session_state.schedule["Date"] = pd.to_datetime(st.session_state.schedule["Date"])
    
    # Edit schedule if it exists
    if st.session_state.schedule is not None:
        # Make sure the Date column is datetime type before editing
        if st.session_state.schedule["Date"].dtype != 'datetime64[ns]':
            st.session_state.schedule["Date"] = pd.to_datetime(st.session_state.schedule["Date"], errors='coerce')
            
        edited_schedule = st.data_editor(
            st.session_state.schedule,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Game #": st.column_config.NumberColumn("Game #", help="Game number"),
                "Date": st.column_config.DateColumn("Date", help="Game date", format="YYYY-MM-DD"),
                "Opponent": st.column_config.TextColumn("Opponent", help="Opposing team"),
                "Innings": st.column_config.NumberColumn("Innings", help="Number of innings", min_value=1, max_value=9),
            },
        )
        
        if st.button("Save Schedule"):
            st.session_state.schedule = edited_schedule
            st.success("Schedule saved!")

# Tab 3: Batting Order
with tab3:
    st.header("Batting Order Setup")
    
    if st.session_state.roster is None:
        st.warning("Please upload a team roster first")
    elif st.session_state.schedule is None:
        st.warning("Please create a game schedule first")
    else:
        # Get player info
        players = st.session_state.roster.copy()
        players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
        player_options = players["Player"].tolist()
        
        st.subheader("Batting Orders for All Games")
        
        # Get all games from schedule
        games = st.session_state.schedule.copy()
        
        # Initialize batting orders for all games if they don't exist
        for game_id in games["Game #"].tolist():
            if game_id not in st.session_state.batting_orders:
                st.session_state.batting_orders[game_id] = list(range(len(players)))
        
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
                    game_label += f" ({date_str})"
                except:
                    pass
            col_headers.append(game_label)
        
        # Create an empty DataFrame for the batting order grid
        num_players = len(players)
        batting_grid = pd.DataFrame(index=range(num_players), columns=col_headers)
        
        # Fill in player names
        batting_grid["Player"] = players["Player"].tolist()
        
        # Fill in the current batting positions
        for _, game in games.iterrows():
            game_id = game["Game #"]
            game_col = f"Game {game_id} vs {game['Opponent']}"
            if pd.notna(game["Date"]):
                try:
                    date_str = game["Date"].strftime("%m/%d")
                    game_col += f" ({date_str})"
                except:
                    pass
            
            # Get batting order for this game
            if game_id in st.session_state.batting_orders:
                batting_order = st.session_state.batting_orders[game_id]
                
                # Create a mapping of player index to batting position
                order_map = {idx: pos+1 for pos, idx in enumerate(batting_order)}
                
                # Fill in the batting positions
                for p_idx in range(num_players):
                    batting_grid.loc[p_idx, game_col] = order_map.get(p_idx, "")
        
        # Display the editable grid
        edited_grid = st.data_editor(
            batting_grid,
            use_container_width=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", disabled=True),
                **{col: st.column_config.NumberColumn(
                    col, 
                    min_value=1, 
                    max_value=num_players,
                    step=1,
                    format="%d",
                    width="medium",
                ) for col in batting_grid.columns if col != "Player"}
            },
            hide_index=True,
        )
        
        # Save button for all games
        if st.button("Save All Batting Orders", key="save_all_batting"):
            # Extract the updated orders from the edited grid
            for _, game in games.iterrows():
                game_id = game["Game #"]
                game_col = f"Game {game_id} vs {game['Opponent']}"
                if pd.notna(game["Date"]):
                    try:
                        date_str = game["Date"].strftime("%m/%d")
                        game_col += f" ({date_str})"
                    except:
                        pass
                
                if game_col in edited_grid.columns:
                    # Get the batting positions from the grid
                    positions = edited_grid[game_col].tolist()
                    
                    # Create a mapping of batting position to player index
                    # This handles the case where multiple players have the same position or some positions are missing
                    position_map = {}
                    for idx, pos in enumerate(positions):
                        if pd.notna(pos) and pos != "":
                            position = int(pos)
                            if position not in position_map:
                                position_map[position] = idx
                    
                    # Create the batting order list (sorted by position)
                    batting_order = []
                    for pos in range(1, num_players + 1):
                        if pos in position_map:
                            batting_order.append(position_map[pos])
                        
                    # Fill in any missing positions with players not yet in the order
                    remaining_players = [i for i in range(num_players) if i not in batting_order]
                    batting_order.extend(remaining_players)
                    
                    # Update the session state
                    st.session_state.batting_orders[game_id] = batting_order
            
            st.success("All batting orders saved!")
            
        # Add warnings about duplicate or missing positions
        st.info("Enter the batting order position (1-9+) for each player in each game. Leave blank for players not in the lineup.")
        
        # Validation button
        if st.button("Validate Batting Orders"):
            all_valid = True
            for _, game in games.iterrows():
                game_id = game["Game #"]
                game_col = f"Game {game_id} vs {game['Opponent']}"
                if pd.notna(game["Date"]):
                    try:
                        date_str = game["Date"].strftime("%m/%d")
                        game_col += f" ({date_str})"
                    except:
                        pass
                
                if game_col in edited_grid.columns:
                    # Get the batting positions from the grid
                    positions = [p for p in edited_grid[game_col].tolist() if pd.notna(p) and p != ""]
                    
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

# Tab 4: Fielding Rotation
with tab4:
    st.header("Fielding Rotation Setup")
    
    if st.session_state.roster is None:
        st.warning("Please upload a team roster first")
    elif st.session_state.schedule is None:
        st.warning("Please create a game schedule first")
    else:
        # Select a game to create a fielding rotation for
        game_options = st.session_state.schedule["Game #"].tolist()
        selected_game = st.selectbox("Select a game", game_options, key="fielding_game_select")
        
        # Get the game information
        game_info = st.session_state.schedule[st.session_state.schedule["Game #"] == selected_game].iloc[0]
        innings = game_info["Innings"]
        st.write(f"Game {selected_game} vs {game_info['Opponent']} on {game_info['Date']} ({innings} innings)")
        
        # Initialize fielding rotation for this game if needed
        if selected_game not in st.session_state.fielding_rotations:
            st.session_state.fielding_rotations[selected_game] = {}
            
        # Initialize positions for all innings if needed
        for inning in range(1, innings + 1):
            inning_key = f"Inning {inning}"
            if inning_key not in st.session_state.fielding_rotations[selected_game]:
                num_players = len(st.session_state.roster)
                # Initialize with default positions (cycle through positions, extras to bench)
                default_positions = []
                for p in range(num_players):
                    if p < len(POSITIONS) - 1:  # All but bench
                        default_positions.append(POSITIONS[p])
                    else:
                        default_positions.append("Bench")
                st.session_state.fielding_rotations[selected_game][inning_key] = default_positions
        
        # Get player info
        players = st.session_state.roster.copy()
        players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
        
        # Create a table for all innings at once
        st.subheader("Fielding Positions for All Innings")
        
        # Create a table layout with player names in the leftmost column
        # and innings across the top
        col_headers = ["Player"]
        for i in range(1, innings + 1):
            col_headers.append(f"Inning {i}")
        
        # Create an empty DataFrame for the fielding grid
        fielding_grid = pd.DataFrame(index=range(len(players)), columns=col_headers)
        fielding_grid["Player"] = players["Player"].tolist()
        
        # Fill in the positions
        for inning in range(1, innings + 1):
            inning_key = f"Inning {inning}"
            inning_col = f"Inning {inning}"
            positions = st.session_state.fielding_rotations[selected_game][inning_key]
            for p_idx in range(len(players)):
                if p_idx < len(positions):
                    fielding_grid.loc[p_idx, inning_col] = positions[p_idx]
                else:
                    fielding_grid.loc[p_idx, inning_col] = "Bench"
        
        # Display the editable grid
        edited_grid = st.data_editor(
            fielding_grid,
            use_container_width=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", disabled=True),
                **{f"Inning {i}": st.column_config.SelectboxColumn(
                    f"Inning {i}", 
                    options=POSITIONS,
                    width="medium",
                    help=f"Position for inning {i}"
                ) for i in range(1, innings + 1)}
            },
            hide_index=True,
        )
        
        # Save button for all innings
        if st.button("Save Fielding Positions", key="save_fielding"):
            # Extract the updated positions from the edited grid
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                inning_col = f"Inning {inning}"
                positions = edited_grid[inning_col].tolist()
                st.session_state.fielding_rotations[selected_game][inning_key] = positions
            
            st.success("Fielding positions saved for all innings!")
            
        # Position validation
        st.subheader("Position Coverage Check")
        if st.button("Validate Positions", key="validate_positions"):
            errors = []
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                positions = st.session_state.fielding_rotations[selected_game][inning_key]
                
                # Check for duplicate positions (except bench)
                non_bench_positions = [p for p in positions if p != "Bench"]
                if len(non_bench_positions) != len(set(non_bench_positions)):
                    duplicates = [p for p in non_bench_positions if non_bench_positions.count(p) > 1]
                    errors.append(f"Inning {inning}: Duplicate position(s): {', '.join(set(duplicates))}")
                
                # Check that all required positions are filled
                required_positions = [p for p in POSITIONS if p != "Bench"]
                missing_positions = [p for p in required_positions if p not in positions]
                if missing_positions:
                    errors.append(f"Inning {inning}: Missing position(s): {', '.join(missing_positions)}")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.success("All positions are properly assigned for each inning!")
                st.info("Note: It's normal to have multiple players on the bench.")
        
        # Add individual game fairness analysis
        st.subheader("Game Fielding Fairness")
        
        # Calculate fairness for the selected game
        if selected_game in st.session_state.fielding_rotations:
            # Create a fairness dataframe for this game
            game_fairness = pd.DataFrame(
                0, 
                index=players["Player"], 
                columns=["Infield", "Outfield", "Bench", "Total Innings"]
            )
            
            # Get game details
            game_info = st.session_state.schedule[st.session_state.schedule["Game #"] == selected_game].iloc[0]
            innings = game_info["Innings"]
            
            # Process each inning
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                
                if inning_key in st.session_state.fielding_rotations[selected_game]:
                    positions = st.session_state.fielding_rotations[selected_game][inning_key]
                    
                    for p_idx, position in enumerate(positions):
                        if p_idx < len(players):
                            player = players.iloc[p_idx]["Player"]
                            
                            # Update total innings
                            game_fairness.loc[player, "Total Innings"] += 1
                            
                            # Update position counts
                            if position in INFIELD:
                                game_fairness.loc[player, "Infield"] += 1
                            elif position in OUTFIELD:
                                game_fairness.loc[player, "Outfield"] += 1
                            elif position in BENCH:
                                game_fairness.loc[player, "Bench"] += 1
            
            # Calculate percentages
            for col in ["Infield", "Outfield", "Bench"]:
                game_fairness[f"{col} %"] = (game_fairness[col] / game_fairness["Total Innings"] * 100).round(1)
            
            # Filter out players with no innings
            game_fairness = game_fairness[game_fairness["Total Innings"] > 0]
            
            # Display the table
            st.dataframe(game_fairness[["Infield", "Outfield", "Bench", "Total Innings", "Infield %", "Outfield %", "Bench %"]])
        
        st.info("💡 To see position distribution and fairness across all games, visit the 'Fielding Fairness' tab.")

# Tab 5: Batting Fairness Analysis
with tab5:
    st.header("Batting Fairness Analysis")
    
    if st.session_state.roster is None:
        st.warning("Please upload a team roster first")
    elif not st.session_state.batting_orders:
        st.warning("Please create batting orders first")
    else:
        # Analyze batting fairness
        batting_fairness = analyze_batting_fairness()
        
        if batting_fairness is not None:
            st.subheader("Batting Position Distribution")
            st.write("Number of times each player bats in each position across all games:")
            st.dataframe(batting_fairness)

# Tab 6: Fielding Fairness Analysis
with tab6:
    st.header("Fielding Fairness Analysis")
    
    if st.session_state.roster is None:
        st.warning("Please upload a team roster first")
    elif not st.session_state.fielding_rotations:
        st.warning("Please create fielding rotations first")
    else:
        # Analyze fielding fairness
        fielding_fairness = analyze_fielding_fairness()
        
        if fielding_fairness is not None:
            st.subheader("Fielding Position Distribution")
            st.write("Distribution of infield, outfield, and bench time for each player:")
            
            # Select columns to display
            display_cols = ["Infield", "Outfield", "Bench", "Total Innings", 
                          "Infield %", "Outfield %", "Bench %"]
            st.dataframe(fielding_fairness[display_cols])
            
# Tab 7: Game Summary
with tab7:
    st.header("Game Summary")
    
    if st.session_state.roster is None:
        st.warning("Please upload a team roster first")
    elif st.session_state.schedule is None:
        st.warning("Please create a game schedule first")
    elif not st.session_state.batting_orders or not st.session_state.fielding_rotations:
        st.warning("Please create batting orders and fielding rotations first")
    else:
        # Select a game to summarize
        game_options = st.session_state.schedule["Game #"].tolist()
        selected_game = st.selectbox("Select a game to summarize", game_options, key="summary_game_select")
        
        # Get the game information
        game_info = st.session_state.schedule[st.session_state.schedule["Game #"] == selected_game].iloc[0]
        innings = game_info["Innings"]
        
        st.subheader(f"Game {selected_game} Summary")
        st.write(f"**Opponent:** {game_info['Opponent']}")
        st.write(f"**Date:** {game_info['Date']}")
        st.write(f"**Innings:** {innings}")
        
        # Check if we have data for this game
        if selected_game in st.session_state.batting_orders and selected_game in st.session_state.fielding_rotations:
            # Get roster, batting order, and fielding data
            players = st.session_state.roster.copy()
            players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
            
            batting_order = st.session_state.batting_orders[selected_game]
            fielding_data = st.session_state.fielding_rotations[selected_game]
            
            # Display batting order
            st.subheader("Batting Order")
            batting_df = pd.DataFrame({
                "Order": list(range(1, len(batting_order) + 1)),
                "Player": [players.iloc[idx]["Player"] for idx in batting_order]
            })
            st.table(batting_df)
            
            # Display fielding positions for each inning
            st.subheader("Fielding Positions by Inning")
            
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                
                if inning_key in fielding_data:
                    st.write(f"**Inning {inning}**")
                    
                    # Create a dataframe for this inning's positions
                    inning_positions = []
                    for p_idx, position in enumerate(fielding_data[inning_key]):
                        if p_idx < len(players):
                            inning_positions.append({
                                "Player": players.iloc[p_idx]["Player"],
                                "Position": position
                            })
                    
                    # Sort by position (with a specific order)
                    position_order = {pos: i for i, pos in enumerate(POSITIONS)}
                    inning_df = pd.DataFrame(inning_positions)
                    inning_df["Position Order"] = inning_df["Position"].map(position_order)
                    inning_df = inning_df.sort_values("Position Order")
                    
                    # Display positions (excluding "Position Order" column)
                    st.table(inning_df[["Position", "Player"]])
            
            # Export options
            st.subheader("Export Game Plan")
            
            export_col1, export_col2 = st.columns(2)
            
            with export_col1:
                # Generate and allow download of PDF
                if st.button("Generate PDF Game Plan"):
                    try:
                        # Generate PDF
                        pdf_buffer = generate_game_plan_pdf(
                            selected_game, 
                            game_info, 
                            batting_order, 
                            fielding_data, 
                            players
                        )
                        
                        # Offer download button for the PDF
                        st.download_button(
                            label="Download PDF Game Plan",
                            data=pdf_buffer,
                            file_name=f"game_{selected_game}_plan.pdf",
                            mime="application/pdf"
                        )
                        
                        # Show success message
                        st.success("PDF generated successfully! Click the download button above.")
                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")
                        st.info("Make sure you have the ReportLab library installed. Run: pip install reportlab")
            
            with export_col2:
                # Text version option (as before)
                if st.button("Generate Text Game Plan"):
                    # Create a string buffer
                    buffer = io.StringIO()
                    
                    # Write game info
                    buffer.write(f"GAME {selected_game} PLAN - {game_info['Opponent']} - {game_info['Date']}\n")
                    buffer.write("=" * 50 + "\n\n")
                    
                    # Write batting order
                    buffer.write("BATTING ORDER:\n")
                    buffer.write("-" * 20 + "\n")
                    for i, player_idx in enumerate(batting_order, 1):
                        player = players.iloc[player_idx]
                        buffer.write(f"{i}. {player['First Name']} {player['Last Name']} (#{player['Jersey Number']})\n")
                    buffer.write("\n")
                    
                    # Write fielding positions
                    buffer.write("FIELDING POSITIONS:\n")
                    buffer.write("-" * 20 + "\n")
                    
                    for inning in range(1, innings + 1):
                        inning_key = f"Inning {inning}"
                        
                        if inning_key in fielding_data:
                            buffer.write(f"\nINNING {inning}:\n")
                            
                            # Sort positions in a sensible order
                            position_assignments = []
                            for p_idx, position in enumerate(fielding_data[inning_key]):
                                if p_idx < len(players):
                                    player = players.iloc[p_idx]
                                    position_assignments.append({
                                        "Player": f"{player['First Name']} {player['Last Name']} (#{player['Jersey Number']})",
                                        "Position": position,
                                        "Order": POSITIONS.index(position)
                                    })
                            
                            # Sort and write positions
                            for pos in sorted(position_assignments, key=lambda x: x["Order"]):
                                buffer.write(f"{pos['Position']}: {pos['Player']}\n")
                    
                    # Get the text from the buffer
                    summary_text = buffer.getvalue()
                    
                    # Display the summary
                    st.text_area("Game Plan", summary_text, height=400)
                    
                    # Create a download link
                    st.download_button(
                        label="Download Text Game Plan",
                        data=summary_text,
                        file_name=f"game_{selected_game}_plan.txt",
                        mime="text/plain"
                    )
        else:
            st.warning(f"No batting order or fielding rotation data for Game {selected_game}")

# Tab 8: Data Management
with tab8:
    st.header("Data Management")
    st.write("Save your team data to continue working on it later or on another device.")
    
    # Create two columns for export and import
    export_col, import_col = st.columns(2)
    
    with export_col:
        st.subheader("Export Team Data")
        st.write("Export all your team data including roster, schedule, batting orders, and fielding rotations.")
        
        # Team name for the export
        team_name = st.text_input("Team Name", 
                                 value="MyTeam",
                                 key="export_team_name",
                                 help="Enter a name for your team (used in the filename)")
        
        # Export button
        if st.button("Export Team Data"):
            if (st.session_state.roster is None and 
                st.session_state.schedule is None and 
                not st.session_state.batting_orders and 
                not st.session_state.fielding_rotations):
                st.warning("No data to export. Please set up your team data first.")
            else:
                try:
                    # Generate JSON data
                    json_data = save_app_data()
                    
                    # Create download button
                    st.download_button(
                        label="Download Team Data",
                        data=json_data,
                        file_name=f"{team_name.replace(' ', '_')}_baseball_data.json",
                        mime="application/json",
                        help="Click to download your team data"
                    )
                    
                    st.success("Team data ready for download!")
                    st.info("Keep this file safe. You can use it to restore your team data in the future.")
                except Exception as e:
                    st.error(f"Error exporting data: {str(e)}")
        
        # Add some space
        st.write("")
        
        # Add example data option
        with st.expander("Create Example Data (for testing)"):
            st.write("Click the button below to generate example data for testing.")
            if st.button("Generate Example Data"):
                # Create example roster
                roster_data = {
                    "First Name": ["John", "Michael", "David", "James", "Robert", "William", "Thomas", "Daniel", "Matthew", "Anthony", "Mark", "Steven", "Andrew", "Christopher"],
                    "Last Name": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor", "Thomas"],
                    "Jersey Number": list(range(1, 15))
                }
                st.session_state.roster = pd.DataFrame(roster_data)
                
                # Create example schedule
                schedule_data = []
                for i in range(1, 11):
                    schedule_data.append({
                        "Game #": i,
                        "Date": pd.Timestamp(f"2023-06-{i+10}"),
                        "Opponent": f"Team {i}",
                        "Innings": 6
                    })
                st.session_state.schedule = pd.DataFrame(schedule_data)
                
                # Initialize batting orders and fielding rotations
                num_players = 14
                for game_id in range(1, 11):
                    # Randomize batting order
                    st.session_state.batting_orders[game_id] = list(range(num_players))
                    np.random.shuffle(st.session_state.batting_orders[game_id])
                    
                    # Initialize fielding positions
                    st.session_state.fielding_rotations[game_id] = {}
                    for inning in range(1, 7):
                        inning_key = f"Inning {inning}"
                        positions = []
                        for p in range(num_players):
                            if p < len(POSITIONS) - 1:  # All but bench
                                positions.append(POSITIONS[(p + inning) % (len(POSITIONS) - 1)])
                            else:
                                positions.append("Bench")
                        st.session_state.fielding_rotations[game_id][inning_key] = positions
                
                st.success("Example data generated successfully!")
                st.rerun()
    
    with import_col:
        st.subheader("Import Team Data")
        st.write("Import previously exported team data to continue working on it.")
        
        # File uploader
        uploaded_file = st.file_uploader("Upload Team Data File", type=["json"])
        
        if uploaded_file is not None:
            # Confirmation before overwriting
            st.warning("Importing data will replace any existing data. Make sure to export your current data first if needed.")
            
            if st.button("Import Team Data"):
                try:
                    # Load the JSON data
                    json_data = uploaded_file.getvalue().decode("utf-8")
                    load_app_data(json_data)
                    
                    st.success("Team data imported successfully!")
                    st.info("Your team data has been restored. Navigate to the other tabs to view and edit it.")
                    
                    # Prompt for app rerun to refresh all components
                    st.button("Refresh App", on_click=st.rerun)
                except Exception as e:
                    st.error(f"Error importing data: {str(e)}")
                    st.info("Make sure you're uploading a valid team data file exported from this app.")
    
    # Add information about data persistence
    st.markdown("---")
    st.subheader("About Data Storage")
    st.info("""
    - Your team data is stored in your browser during the session
    - To keep your data for future use, export it using the button above
    - To continue working on your team later, import your saved data file
    - Data files are in JSON format and contain all your team information
    """)
    
    # Add help section
    with st.expander("Data Management Help"):
        st.markdown("""
        ### How to use the data management features

        #### Exporting Data
        1. Enter a team name (used for the filename)
        2. Click "Export Team Data"
        3. Click "Download Team Data" to save the file to your computer
        4. Store this file somewhere safe

        #### Importing Data
        1. Click "Browse files" to select your previously exported JSON file
        2. Click "Import Team Data" to load the data
        3. Click "Refresh App" if needed to see all your data

        #### When to export data
        - After setting up your initial team roster and schedule
        - After making significant changes to batting orders or fielding rotations
        - Before closing the app or if you want to share the lineup with another coach

        #### Troubleshooting
        - If import fails, make sure you're using a file exported from this app
        - If you see strange characters or formatting issues, try exporting a new file
        - If you need to start over, simply refresh the page without importing
        """)

# Footer
st.markdown("---")
st.markdown("Baseball Lineup Manager - Helping coaches create fair and balanced rotations")