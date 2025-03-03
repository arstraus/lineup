# LineupBoss baseball lineup manager

import streamlit as st
import pandas as pd
import numpy as np
import io
import base64
import json

# Set page config
st.set_page_config(
    page_title="LineupBoss",
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
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Team Roster"
if 'player_availability' not in st.session_state:
    st.session_state.player_availability = {}

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
                if i <= len(batting_counts.columns) and player_idx < len(players):
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
                            if player_idx < len(players):
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
        if player_idx < len(players):
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
    elements.append(Paragraph("LineupBoss - Game Plan", 
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
        "team_info": st.session_state.team_info if 'team_info' in st.session_state else {},
        "roster": st.session_state.roster.to_dict() if st.session_state.roster is not None else None,
        "schedule": st.session_state.schedule.to_dict() if st.session_state.schedule is not None else None,
        "batting_orders": st.session_state.batting_orders,
        "fielding_rotations": st.session_state.fielding_rotations,
        "player_availability": st.session_state.player_availability
    }
    
    # Use the custom encoder to handle special data types
    return json.dumps(data, cls=CustomJSONEncoder)

def load_app_data(json_data):
    """Load application data from JSON"""
    data = json.loads(json_data)
    
    # Restore team info if it exists
    if "team_info" in data:
        st.session_state.team_info = data["team_info"]
    else:
        # Initialize with empty values if not in the data
        st.session_state.team_info = {
            "team_name": "",
            "league": "",
            "head_coach": "",
            "assistant_coach1": "",
            "assistant_coach2": ""
        }
    
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
    
    # Restore player availability if it exists in the data
    if "player_availability" in data:
        st.session_state.player_availability = data["player_availability"]
    
    # Convert dictionary string keys back to integers for game IDs
    st.session_state.batting_orders = {int(k) if k.isdigit() else k: v for k, v in st.session_state.batting_orders.items()}
    st.session_state.fielding_rotations = {int(k) if k.isdigit() else k: v for k, v in st.session_state.fielding_rotations.items()}
    if "player_availability" in data:
        st.session_state.player_availability = {int(k) if k.isdigit() else k: v for k, v in st.session_state.player_availability.items()}

# Main app layout
# Add a sidebar with tabs
st.sidebar.title("⚾ LineupBoss")

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
selected_tab = st.sidebar.radio("Navigation", tabs)

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
    7. **Export Your Data**: Save your work for future use
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

    st.markdown("---")

    # Tips and best practices
    with st.expander("💡 Tips and Best Practices"):
        st.markdown("""
        ### Player Management
        - **Update availability early**: Set player availability as soon as you know who can attend each game
        - **Rotate positions**: Give all players experience in different positions
        - **Balance development with fairness**: Consider player skills but ensure fairness in playing time

        ### Lineup Creation
        - **Plan ahead**: Create batting orders and fielding rotations for multiple games in advance
        - **Check the fairness analysis**: Use the fairness tabs to ensure all players get equal opportunities
        - **Update after games**: Make adjustments based on actual playing time if games end early

        ### Data Management
        - **Save regularly**: Export your data after making significant changes
        - **Create backups**: Keep multiple exported files as backups
        - **Share with assistant coaches**: Export data for others to import and help with planning
        """)

    st.markdown("---")

    # Common questions
    with st.expander("❓ Frequently Asked Questions"):
        st.markdown("""
        ### General Questions
        **Q: Will my data be saved between sessions?**  
        A: Data is stored in your browser during the session. To keep your data for future use, export it using the Data Management tab.

        **Q: How many players can I manage?**  
        A: The app can handle teams of any size, but works best with 10-20 players.

        **Q: Can I track multiple teams?**  
        A: Yes, export each team's data separately and import as needed.

        ### Lineup Questions
        **Q: How do I handle players who arrive late or leave early?**  
        A: Mark them as available but place them appropriately in the batting order and field positions.

        **Q: What happens when a game has fewer innings than planned?**  
        A: The app plans for the full game - make a note of actual playing time for fairness considerations.

        **Q: How do I mark preferred positions for players?**  
        A: The app doesn't explicitly track preferred positions, but you can use your knowledge when creating rotations.

        ### Technical Questions
        **Q: What if the PDF export doesn't work?**  
        A: Ensure you have the ReportLab library installed, or use the text export option instead.

        **Q: Can I edit a saved export file?**  
        A: The export files are in JSON format and could be edited manually, but it's not recommended.

        **Q: How can I share lineups with parents?**  
        A: Generate a PDF or text game plan and share it via email or messaging apps.
        """)


# Tab 1: Team Setup
if selected_tab == "Team Setup":
    ## st.header("Team Setup")
    
    # Track if we need to upload a roster in this session
    if 'upload_roster_flag' not in st.session_state:
        st.session_state.upload_roster_flag = False
    
    # Create columns for team info and roster management
    team_info_col, roster_col = st.columns([1, 2])
    
    with team_info_col:
        st.subheader("Team Information")
        
        # Initialize team information in session state if it doesn't exist
        if 'team_info' not in st.session_state:
            st.session_state.team_info = {
                "team_name": "",
                "league": "",
                "head_coach": "",
                "assistant_coach1": "",
                "assistant_coach2": ""
            }
        
        # Team information form
        with st.form("team_info_form"):
            team_name = st.text_input("Team Name", value=st.session_state.team_info["team_name"])
            league = st.text_input("League", value=st.session_state.team_info["league"])
            head_coach = st.text_input("Head Coach", value=st.session_state.team_info["head_coach"])
            assistant_coach1 = st.text_input("Assistant Coach 1", value=st.session_state.team_info["assistant_coach1"])
            assistant_coach2 = st.text_input("Assistant Coach 2", value=st.session_state.team_info["assistant_coach2"])
            
            save_team_info = st.form_submit_button("Save Team Information")
            
            if save_team_info:
                # Update session state with new values
                st.session_state.team_info = {
                    "team_name": team_name,
                    "league": league,
                    "head_coach": head_coach,
                    "assistant_coach1": assistant_coach1,
                    "assistant_coach2": assistant_coach2
                }
                st.success("Team information saved!")
    
    with roster_col:
        st.subheader("Team Roster Management")
        
        # Option to upload a roster - placing this first for immediate feedback
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
                            st.session_state.roster = df
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
        
        # Display current roster if it exists
        if st.session_state.roster is not None:
            st.subheader("Current Team Roster")
            # Add a row index column that starts at 1
            display_df = st.session_state.roster.copy()
            display_df.index = range(1, len(display_df) + 1)  # Set index to start at 1
            # Display the dataframe with row numbers visible
            st.dataframe(display_df, use_container_width=True)
            
            # Add roster statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Players", len(st.session_state.roster))
    
    # Roster management actions (shown only if roster exists)
    if st.session_state.roster is not None:
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
                        if new_jersey in st.session_state.roster["Jersey Number"].values:
                            st.error(f"Jersey number {new_jersey} already exists")
                        else:
                            # Add new player to roster
                            new_player = pd.DataFrame({
                                "First Name": [new_first_name],
                                "Last Name": [new_last_name],
                                "Jersey Number": [new_jersey]
                            })
                            st.session_state.roster = pd.concat([st.session_state.roster, new_player], ignore_index=True)
                            st.success(f"Added {new_first_name} {new_last_name} (#{new_jersey}) to roster")
                            st.rerun()  # Use standard rerun
        
        # Option to remove a player
        with st.expander("Remove Player"):
            # Create a list of players to select from
            players = st.session_state.roster.copy()
            players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
            player_options = players["Player"].tolist()
            
            selected_player = st.selectbox("Select player to remove", player_options)
            
            if st.button("Remove Selected Player"):
                # Find the index of the selected player
                selected_idx = players[players["Player"] == selected_player].index[0]
                
                # Remove player from roster
                st.session_state.roster = st.session_state.roster.drop(selected_idx).reset_index(drop=True)
                
                # Show success message
                st.success(f"Removed {selected_player} from roster")
                st.rerun()  # Use standard rerun
    
    # Force a rerun when a new roster is uploaded to ensure it displays immediately
    if st.session_state.upload_roster_flag:
        st.session_state.upload_roster_flag = False
        st.rerun()  # Use standard rerun

# Tab 2: Game Schedule
elif selected_tab == "Game Schedule":
    ## st.header("Game Schedule")
    
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
                    "Time": None,
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
        
        # Add Time column if it doesn't exist
        if "Time" not in st.session_state.schedule.columns:
            st.session_state.schedule["Time"] = None
        
        # Create a completely new DataFrame with exactly the columns we want
        columns = ["Game #", "Date", "Time", "Opponent", "Innings"]
        data = []
        
        # Copy the data row by row to ensure clean DataFrame creation
        for _, row in st.session_state.schedule.iterrows():
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
            # Save the edited schedule
            st.session_state.schedule = edited_schedule.copy()
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
    ## st.header("Player Setup")
    
    if st.session_state.roster is None:
        st.warning("Please upload a team roster first")
    elif st.session_state.schedule is None:
        st.warning("Please create a game schedule first")
    else:
        # Select a game to set up players for
        game_options = st.session_state.schedule["Game #"].tolist()
        selected_game = st.selectbox("Select a game", game_options, key="setup_game_select")
        
        # Get the game information
        game_info = st.session_state.schedule[st.session_state.schedule["Game #"] == selected_game].iloc[0]
        
        st.subheader(f"Player Setup for Game {selected_game}")
        st.write(f"**Opponent:** {game_info['Opponent']}")
        st.write(f"**Date:** {game_info['Date']}")
        
        # Get player info
        players = st.session_state.roster.copy()
        players["Player"] = players["First Name"] + " " + players["Last Name"] + " (#" + players["Jersey Number"].astype(str) + ")"
        
        # Initialize player availability for this game if needed
        if selected_game not in st.session_state.player_availability:
            st.session_state.player_availability[selected_game] = {
                "Available": [True] * len(players),
                "Can Play Catcher": [False] * len(players)
            }
        
        # Ensure lists are the right length (in case roster changed)
        if len(st.session_state.player_availability[selected_game]["Available"]) != len(players):
            # Add True for new players
            if len(st.session_state.player_availability[selected_game]["Available"]) < len(players):
                st.session_state.player_availability[selected_game]["Available"].extend(
                    [True] * (len(players) - len(st.session_state.player_availability[selected_game]["Available"]))
                )
                st.session_state.player_availability[selected_game]["Can Play Catcher"].extend(
                    [False] * (len(players) - len(st.session_state.player_availability[selected_game]["Can Play Catcher"]))
                )
            else:  # Remove extras if roster got smaller
                st.session_state.player_availability[selected_game]["Available"] = \
                    st.session_state.player_availability[selected_game]["Available"][:len(players)]
                st.session_state.player_availability[selected_game]["Can Play Catcher"] = \
                    st.session_state.player_availability[selected_game]["Can Play Catcher"][:len(players)]
        
        # Create a dataframe for the player setup grid
        setup_df = pd.DataFrame({
            "Player": players["Player"].tolist(),
            "Jersey #": players["Jersey Number"].tolist(),
            "Available": st.session_state.player_availability[selected_game]["Available"],
            "Can Play Catcher": st.session_state.player_availability[selected_game]["Can Play Catcher"]
        })
        
        # Add index starting from 1 instead of 0
        setup_df.index = range(1, len(setup_df) + 1)
        
        # Display the editable grid
        edited_df = st.data_editor(
            setup_df,
            use_container_width=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", disabled=True),
                "Jersey #": st.column_config.NumberColumn("Jersey #", disabled=True),
                "Available": st.column_config.CheckboxColumn("Available for Game", help="Check if player is available for this game"),
                "Can Play Catcher": st.column_config.CheckboxColumn("Can Play Catcher", help="Check if player can play catcher position")
            },
            hide_index=False,
            key="player_setup_editor"
        )
        
        # Save button
        if st.button("Save Player Setup", key="save_player_setup"):
            # Extract the updated values from the edited dataframe
            st.session_state.player_availability[selected_game]["Available"] = edited_df["Available"].tolist()
            st.session_state.player_availability[selected_game]["Can Play Catcher"] = edited_df["Can Play Catcher"].tolist()
            
            st.success("Player setup saved successfully!")
            
            # Update the batting and fielding tabs with this information
            if selected_game in st.session_state.batting_orders:
                # Get indices of unavailable players
                unavailable_indices = [i for i, available in enumerate(edited_df["Available"].tolist()) if not available]
                
                # Create a new batting order that excludes unavailable players
                current_order = st.session_state.batting_orders[selected_game]
                new_order = [idx for idx in current_order if idx not in unavailable_indices]
                
                # Add unavailable players at the end (bench)
                new_order.extend(unavailable_indices)
                
                # Update the batting order
                st.session_state.batting_orders[selected_game] = new_order
        
        # Add a summary of player availability
        available_count = sum(edited_df["Available"])
        unavailable_count = len(edited_df) - available_count
        catchers_count = sum(edited_df["Can Play Catcher"])
        
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
    ## st.header("Batting Order Setup")
    
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
        num_players = len(players)
        batting_grid = pd.DataFrame(index=range(num_players), columns=col_headers)
        
        # Fill in player names
        batting_grid["Player"] = players["Player"].tolist()
        
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
            availability = [True] * num_players  # Default all players as available
            if game_id in st.session_state.player_availability:
                availability_data = st.session_state.player_availability[game_id]["Available"]
                for idx, avail in enumerate(availability_data):
                    if idx < num_players:
                        availability[idx] = avail
            
            # Get batting order for this game
            if game_id in st.session_state.batting_orders:
                batting_order = st.session_state.batting_orders[game_id]
                
                # Create a mapping of player index to batting position
                order_map = {idx: pos+1 for pos, idx in enumerate(batting_order)}
                
                # Fill in the batting positions or OUT for unavailable players
                for p_idx in range(num_players):
                    if not availability[p_idx]:
                        # Player is unavailable - display OUT
                        batting_grid.loc[p_idx, game_col] = "OUT"
                    else:
                        # Player is available - display batting position
                        batting_grid.loc[p_idx, game_col] = order_map.get(p_idx, "")
        
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
            if game_id in st.session_state.player_availability:
                unavailable_count = len(players) - sum(st.session_state.player_availability[game_id]["Available"])
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
                    # Get the batting positions from the grid
                    positions = edited_grid[game_col].tolist()
                    
                    # Create a mapping of batting position to player index
                    # This handles the case where multiple players have the same position or some positions are missing
                    position_map = {}
                    for idx, pos in enumerate(positions):
                        if pd.notna(pos) and pos != "" and pos != "OUT":
                            # Try to convert to integer for position
                            try:
                                position = int(pos)
                                if position not in position_map:
                                    position_map[position] = idx
                            except ValueError:
                                # Not a number, could be "OUT" or something else, skip
                                pass
                    
                    # Create the batting order list (sorted by position)
                    batting_order = []
                    for pos in range(1, num_players + 1):
                        if pos in position_map:
                            batting_order.append(position_map[pos])
                    
                    # Determine available and unavailable players
                    available = []
                    unavailable = []
                    
                    if game_id in st.session_state.player_availability:
                        availability = st.session_state.player_availability[game_id]["Available"]
                        for idx in range(num_players):
                            if idx < len(availability):
                                if availability[idx]:
                                    if idx not in batting_order:
                                        available.append(idx)
                                else:
                                    unavailable.append(idx)
                    else:
                        # If no availability info, treat all missing players as available
                        available = [i for i in range(num_players) if i not in batting_order]
                    
                    # Add any available players not yet in order
                    batting_order.extend(available)
                    
                    # Add unavailable players at the end
                    batting_order.extend(unavailable)
                    
                    # Update the session state
                    st.session_state.batting_orders[game_id] = batting_order
            
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
                        if pd.notna(p) and p != "" and p != "OUT":
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
        game_options_auto = st.session_state.schedule["Game #"].tolist()
        auto_game = st.selectbox("Select a game to auto-arrange", game_options_auto, key="auto_arrange_game")
        
        if auto_game in st.session_state.player_availability:
            if st.button("Auto-arrange Batting Order", key="auto_arrange"):
                # Get current batting order
                current_order = st.session_state.batting_orders[auto_game]
                
                # Get availability info
                availability = st.session_state.player_availability[auto_game]["Available"]
                
                # Separate available and unavailable players
                available = []
                unavailable = []
                
                for idx in range(len(players)):
                    if idx < len(availability) and availability[idx]:
                        available.append(idx)
                    else:
                        unavailable.append(idx)
                
                # Keep available players in their current relative order
                available_in_order = [idx for idx in current_order if idx in available]
                
                # Add any available players not yet in order
                available_in_order.extend([idx for idx in available if idx not in available_in_order])
                
                # Append unavailable players at the end
                new_order = available_in_order + unavailable
                
                # Update the batting order
                st.session_state.batting_orders[auto_game] = new_order
                
                st.success("Batting order auto-arranged with unavailable players at the end.")
                st.rerun()

# Tab 5: Fielding Rotation
elif selected_tab == "Fielding Rotation":
    ## st.header("Fielding Rotation Setup")
    
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
        
        # Format date and time
        game_date_time = f"{game_info['Date']}"
        if "Time" in game_info and pd.notna(game_info["Time"]):
            # Format the time
            time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else game_info["Time"]
            game_date_time += f" at {time_str}"

        st.write(f"Game {selected_game} vs {game_info['Opponent']} on {game_date_time} ({innings} innings)")
        
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
        
        # Get availability information
        availability = [True] * len(players)  # Default all players as available
        can_play_catcher = [False] * len(players)  # Default no players can play catcher
        
        if selected_game in st.session_state.player_availability:
            avail_data = st.session_state.player_availability[selected_game]["Available"]
            for idx, avail in enumerate(avail_data):
                if idx < len(availability):
                    availability[idx] = avail
            
            catcher_data = st.session_state.player_availability[selected_game]["Can Play Catcher"]
            for idx, can_catch in enumerate(catcher_data):
                if idx < len(can_play_catcher):
                    can_play_catcher[idx] = can_catch
            
            # Add availability warning
            unavailable_count = len(players) - sum(availability)
            if unavailable_count > 0:
                st.warning(f"{unavailable_count} player(s) marked as unavailable. They will show 'OUT' in all innings.")
            
            # Add catcher information
            catcher_count = sum(can_play_catcher)
            if catcher_count == 0:
                st.error("No players marked as capable of playing catcher. Please update player setup.")
            else:
                # Get the names of available catchers
                catcher_names = [players.iloc[i]["Player"] for i in range(len(players)) 
                                if i < len(can_play_catcher) and can_play_catcher[i]]
                st.info(f"Players who can play catcher: {', '.join(catcher_names)}")
        
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
        
        # Fill in the positions or OUT for unavailable players
        for inning in range(1, innings + 1):
            inning_key = f"Inning {inning}"
            inning_col = f"Inning {inning}"
            positions = st.session_state.fielding_rotations[selected_game][inning_key]
            
            for p_idx in range(len(players)):
                if not availability[p_idx]:
                    # Player is unavailable - display OUT
                    fielding_grid.loc[p_idx, inning_col] = "OUT"
                elif p_idx < len(positions):
                    # Player is available - display position
                    fielding_grid.loc[p_idx, inning_col] = positions[p_idx]
                else:
                    # Default to bench for any missing positions
                    fielding_grid.loc[p_idx, inning_col] = "Bench"
        
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
                updated_positions = edited_grid[inning_col].tolist()
                
                # Save positions to session state (keep OUT for unavailable players)
                st.session_state.fielding_rotations[selected_game][inning_key] = updated_positions
            
            st.success("Fielding positions saved for all innings!")
            
        # Position validation
        st.subheader("Position Coverage Check")
        if st.button("Validate Positions", key="validate_positions"):
            errors = []
            warnings = []
            
            for inning in range(1, innings + 1):
                inning_key = f"Inning {inning}"
                inning_col = f"Inning {inning}"
                positions = edited_grid[inning_col].tolist()
                
                # Check for duplicate positions (except bench and OUT)
                non_bench_positions = [p for p in positions if p != "Bench" and p != "OUT"]
                if len(non_bench_positions) != len(set(non_bench_positions)):
                    duplicates = [p for p in non_bench_positions if non_bench_positions.count(p) > 1]
                    errors.append(f"Inning {inning}: Duplicate position(s): {', '.join(set(duplicates))}")
                
                # Check that all required positions are filled
                required_positions = [p for p in POSITIONS if p != "Bench"]
                missing_positions = [p for p in required_positions if p not in positions]
                if missing_positions:
                    errors.append(f"Inning {inning}: Missing position(s): {', '.join(missing_positions)}")
                
                # Check if unavailable players are assigned field positions
                for idx, position in enumerate(positions):
                    if idx < len(availability) and not availability[idx] and position != "OUT":
                        player_name = st.session_state.roster.iloc[idx]["First Name"] + " " + st.session_state.roster.iloc[idx]["Last Name"]
                        warnings.append(f"Inning {inning}: Unavailable player {player_name} should be marked as OUT, not {position}")
                
                # Check if catcher position is assigned to a capable player
                for idx, position in enumerate(positions):
                    if position == "Catcher" and idx < len(can_play_catcher) and not can_play_catcher[idx]:
                        player_name = st.session_state.roster.iloc[idx]["First Name"] + " " + st.session_state.roster.iloc[idx]["Last Name"]
                        warnings.append(f"Inning {inning}: Player {player_name} assigned to Catcher but not marked as capable")
            
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
                positions = st.session_state.fielding_rotations[selected_game][inning_key]
                
                # Set unavailable players to OUT
                for idx in range(len(positions)):
                    if idx < len(availability) and not availability[idx] and positions[idx] != "OUT":
                        positions[idx] = "OUT"
                        updated = True
            
            if updated:
                st.success("Updated all unavailable players to OUT")
                st.rerun()
            else:
                st.info("All unavailable players are already marked as OUT")
        
        # Add individual game fairness analysis
        st.subheader("Game Fielding Fairness")
        
        # Calculate fairness for the selected game
        if selected_game in st.session_state.fielding_rotations:
            # Create a fairness dataframe for this game
            game_fairness = pd.DataFrame(
                0, 
                index=players["Player"], 
                columns=["Infield", "Outfield", "Bench", "OUT", "Total Innings"]
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
        
        Create rotations by assigning positions to each player for each inning.
        """)
        
# Tab 6: Batting Fairness Analysis
elif selected_tab == "Batting Fairness":
    ## st.header("Batting Fairness Analysis")
    
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

# Tab 7: Fielding Fairness Analysis
elif selected_tab == "Fielding Fairness":
    ## st.header("Fielding Fairness Analysis")
    
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

# Tab 8: Game Summary
elif selected_tab == "Game Summary":
    ## st.header("Game Summary")
    
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
        
        # Display team information if available
        if 'team_info' in st.session_state and st.session_state.team_info["team_name"]:
            team_col1, team_col2 = st.columns(2)
            with team_col1:
                st.write(f"**Team:** {st.session_state.team_info['team_name']}")
                if st.session_state.team_info["league"]:
                    st.write(f"**League:** {st.session_state.team_info['league']}")
            
            with team_col2:
                if st.session_state.team_info["head_coach"]:
                    coach_text = f"**Head Coach:** {st.session_state.team_info['head_coach']}"
                    st.write(coach_text)
                
                asst_coaches = []
                if st.session_state.team_info["assistant_coach1"]:
                    asst_coaches.append(st.session_state.team_info["assistant_coach1"])
                if st.session_state.team_info["assistant_coach2"]:
                    asst_coaches.append(st.session_state.team_info["assistant_coach2"])
                
                if asst_coaches:
                    st.write(f"**Assistant Coach(es):** {', '.join(asst_coaches)}")
        
        st.write(f"**Opponent:** {game_info['Opponent']}")
        
        # Update this line to include time if available - fixed to prevent double time display
        if "Time" in game_info and pd.notna(game_info["Time"]):
            # Format the time
            time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else game_info["Time"]
            
            # Format the date without time component
            date_str = game_info['Date'].strftime("%Y-%m-%d") if isinstance(game_info['Date'], pd.Timestamp) else game_info['Date']
            
            st.write(f"**Date/Time:** {date_str} at {time_str}")
        else:
            st.write(f"**Date:** {game_info['Date']}")
            
        st.write(f"**Innings:** {innings}")
        
        # Check if we have data for this game
        if selected_game in st.session_state.batting_orders and selected_game in st.session_state.fielding_rotations:
            # Get roster, batting order, and fielding data
            players = st.session_state.roster.copy()
            batting_order = st.session_state.batting_orders[selected_game]
            fielding_data = st.session_state.fielding_rotations[selected_game]
            
            # Get player availability
            availability = [True] * len(players)  # Default all players as available
            if selected_game in st.session_state.player_availability:
                avail_data = st.session_state.player_availability[selected_game]["Available"]
                for idx, avail in enumerate(avail_data):
                    if idx < len(availability):
                        availability[idx] = avail
            
            # Create a comprehensive game summary table
            st.subheader("Game Plan")
            
            # Initialize columns for the summary dataframe
            columns = ["Batting Order", "Jersey #", "Player Name", "Available"]
            for i in range(1, innings + 1):
                columns.append(f"Inning {i}")
            
            # Create empty dataframe with the columns
            summary_df = pd.DataFrame(columns=columns)
            
            # Fill in the data for each player in the batting order
            for batting_pos, player_idx in enumerate(batting_order, 1):
                if player_idx < len(players):
                    player = players.iloc[player_idx]
                    is_available = availability[player_idx] if player_idx < len(availability) else True
                    
                    # Initialize row data with player info
                    row_data = {
                        "Batting Order": "OUT" if not is_available else batting_pos,
                        "Jersey #": player["Jersey Number"],
                        "Player Name": f"{player['First Name']} {player['Last Name']}",
                        "Available": "Yes" if is_available else "No"
                    }
                    
                    # Add fielding positions for each inning
                    for inning in range(1, innings + 1):
                        inning_key = f"Inning {inning}"
                        if inning_key in fielding_data and player_idx < len(fielding_data[inning_key]):
                            position = fielding_data[inning_key][player_idx]
                            # If position isn't already OUT but player is unavailable, show OUT
                            if not is_available and position != "OUT":
                                row_data[f"Inning {inning}"] = "OUT"
                            else:
                                row_data[f"Inning {inning}"] = position
                        else:
                            row_data[f"Inning {inning}"] = "N/A"
                    
                    # Add this player's row to the dataframe
                    summary_df = pd.concat([summary_df, pd.DataFrame([row_data])], ignore_index=True)
            
            # Add bench players (players not in batting order)
            all_player_indices = set(range(len(players)))
            batting_indices = set([idx for idx in batting_order if idx < len(players)])
            bench_indices = all_player_indices - batting_indices
            
            for player_idx in bench_indices:
                player = players.iloc[player_idx]
                is_available = availability[player_idx] if player_idx < len(availability) else True
                
                # Initialize row data with player info
                row_data = {
                    "Batting Order": "OUT" if not is_available else "Bench",
                    "Jersey #": player["Jersey Number"],
                    "Player Name": f"{player['First Name']} {player['Last Name']}",
                    "Available": "Yes" if is_available else "No"
                }
                
                # Add fielding positions for each inning
                for inning in range(1, innings + 1):
                    inning_key = f"Inning {inning}"
                    if inning_key in fielding_data and player_idx < len(fielding_data[inning_key]):
                        position = fielding_data[inning_key][player_idx]
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
                        # Create a buffer for the PDF
                        from reportlab.lib.pagesizes import letter, landscape
                        from reportlab.lib import colors
                        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        from reportlab.lib.units import inch
                        
                        buffer = io.BytesIO()
                        
                        # Create the PDF document (use landscape for wide tables)
                        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), 
                                               leftMargin=0.5*inch, rightMargin=0.5*inch,
                                               topMargin=0.5*inch, bottomMargin=0.5*inch)
                        elements = []
                        
                        # Get styles
                        styles = getSampleStyleSheet()
                        
                        # Create a custom title style that's smaller
                        custom_title_style = ParagraphStyle(
                            'CustomTitle',
                            parent=styles['Heading2'],  # Use Heading2 instead of Heading1 for smaller text
                            fontSize=14,
                            alignment=1  # Center alignment
                        )
                        
                        section_style = styles['Heading2']
                        normal_style = styles['Normal']
                        
                        # Add game header with the updated title
                        elements.append(Paragraph(f"Game {selected_game} Lineup", custom_title_style))
                        
                        # Add team information if available
                        if 'team_info' in st.session_state and st.session_state.team_info["team_name"]:
                            team_name = st.session_state.team_info["team_name"]
                            league = st.session_state.team_info["league"]
                            head_coach = st.session_state.team_info["head_coach"]
                            
                            elements.append(Paragraph(f"Team: {team_name}", normal_style))
                            if league:
                                elements.append(Paragraph(f"League: {league}", normal_style))
                            if head_coach:
                                coach_text = f"Coach: {head_coach}"
                                asst1 = st.session_state.team_info["assistant_coach1"]
                                asst2 = st.session_state.team_info["assistant_coach2"]
                                if asst1 or asst2:
                                    coach_text += " | Assistants: "
                                    if asst1:
                                        coach_text += asst1
                                    if asst1 and asst2:
                                        coach_text += ", " 
                                    if asst2:
                                        coach_text += asst2
                                elements.append(Paragraph(coach_text, normal_style))
                        
                        elements.append(Paragraph(f"Opponent: {game_info['Opponent']}", normal_style))
                        
                        # Update this section to include time if available - fixed to prevent double time display
                        if "Time" in game_info and pd.notna(game_info["Time"]):
                            # Format the time
                            time_str = game_info["Time"].strftime("%I:%M %p") if isinstance(game_info["Time"], pd.Timestamp) else game_info["Time"]
                            
                            # Format the date without time component
                            date_str = game_info['Date'].strftime("%Y-%m-%d") if isinstance(game_info['Date'], pd.Timestamp) else game_info['Date']
                            
                            elements.append(Paragraph(f"Date/Time: {date_str} at {time_str}", normal_style))
                        else:
                            elements.append(Paragraph(f"Date: {game_info['Date']}", normal_style))
                            
                        elements.append(Paragraph(f"Innings: {innings}", normal_style))
                        elements.append(Spacer(1, 0.25*inch))
                        
                        # Convert dataframe to a list of lists for the table
                        table_data = [summary_df.columns.tolist()]  # Header row
                        
                        # Modify column headers for better wrapping
                        modified_headers = table_data[0].copy()
                        for i, header in enumerate(modified_headers):
                            if header == "Batting Order":
                                modified_headers[i] = "Batting\nOrder"
                            elif header == "Jersey #":
                                modified_headers[i] = "Jersey\n#"
                            elif header == "Player Name":
                                modified_headers[i] = "Player\nName"
                        table_data[0] = modified_headers
                        
                        for _, row in summary_df.iterrows():
                            table_data.append(row.tolist())
                        
                        # Calculate total available width (landscape letter minus margins)
                        available_width = 11*inch - 1*inch  # 11 inches is landscape letter width, minus margins
                        
                        # Distribute column widths more effectively
                        # Increased batting order column width
                        order_width = 0.9*inch     # Batting order column (increased from 0.7)
                        jersey_width = 0.7*inch    # Jersey number column
                        name_width = 1.9*inch      # Player name column (decreased from 2.0)
                        avail_width = 0.7*inch     # Available column
                        
                        # Calculate remaining width for inning columns
                        remaining_width = available_width - (order_width + jersey_width + name_width + avail_width)
                        inning_width = remaining_width / innings if innings > 0 else 1*inch
                        
                        # Set column widths
                        col_widths = [order_width, jersey_width, name_width, avail_width] + [inning_width] * innings
                        
                        # Create the table
                        table = Table(table_data, colWidths=col_widths, repeatRows=1)
                        
                        # Add style to the table
                        table.setStyle(TableStyle([
                            # Header row styling
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('WORDWRAP', (0, 0), (-1, 0), True),  # Enable word wrapping for header row
                            ('LINESPACING', (0, 0), (-1, 0), 0.9),  # Reduce line spacing in header
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  # Adjust bottom padding
                            ('TOPPADDING', (0, 0), (-1, 0), 8),     # Adjust top padding
                            
                            # Body styling
                            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Batting order centered
                            ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Jersey number centered
                            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Available column centered
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            
                            # Inning columns centered
                            *[('ALIGN', (4+i, 1), (4+i, -1), 'CENTER') for i in range(innings)],
                            
                            # Grid
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
                            
                            # Highlight unavailable players with subtle background
                            *[('BACKGROUND', (0, i), (-1, i), colors.lightpink) 
                              for i in range(1, len(table_data)) 
                              if table_data[i][3] == "No"],  # Check Available column
                            
                            # Alternating row colors for available players
                            *[('BACKGROUND', (0, i), (-1, i), colors.lightgrey) 
                              for i in range(1, len(table_data)) 
                              if i % 2 == 0 and table_data[i][3] == "Yes"],
                        ]))
                        
                        elements.append(table)
                        
                        # Add legend for positions
                        elements.append(Spacer(1, 0.3*inch))
                        elements.append(Paragraph("Position Legend:", normal_style))
                        legend_text = "P - Pitcher, C - Catcher, 1B - First Base, 2B - Second Base, 3B - Third Base, SS - Shortstop, "
                        legend_text += "LF - Left Field, RF - Right Field, LC - Left Center, RC - Right Center, OUT - Player Unavailable"
                        elements.append(Paragraph(legend_text, normal_style))
                        
                        # Add footer
                        elements.append(Spacer(1, 0.3*inch))
                        elements.append(Paragraph("LineupBoss - Game Plan", 
                                                 ParagraphStyle('Footer', fontSize=8, textColor=colors.gray)))
                        
                        # Build the PDF
                        doc.build(elements)
                        
                        # Get the PDF from the buffer
                        buffer.seek(0)
                        
                        # Offer download button for the PDF
                        st.download_button(
                            label="Download PDF Game Plan",
                            data=buffer,
                            file_name=f"game_{selected_game}_lineup.pdf",  # Changed to "lineup" instead of "plan"
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
                    team_header = ""
                    if 'team_info' in st.session_state and st.session_state.team_info["team_name"]:
                        team_name = st.session_state.team_info["team_name"]
                        league = st.session_state.team_info["league"]
                        head_coach = st.session_state.team_info["head_coach"]
                        
                        team_header = f"{team_name}"
                        if league:
                            team_header += f" ({league})"
                        
                        buffer.write(f"TEAM: {team_header}\n")
                        
                        coach_text = f"COACH: {head_coach}"
                        asst1 = st.session_state.team_info["assistant_coach1"]
                        asst2 = st.session_state.team_info["assistant_coach2"]
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
                    
                    # Update to include time if available - fixed to prevent double time display
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
                        file_name=f"game_{selected_game}_lineup.txt",  # Changed from "plan" to "lineup"
                        mime="text/plain"
                    )
        else:
            st.warning(f"No batting order or fielding rotation data for Game {selected_game}")

# Tab 9: Data Management
elif selected_tab == "Data Management":
    ## st.header("Data Management")
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
st.markdown("LineupBoss - Helping coaches create fair and balanced rotations")

# Add a feedback/status section in the sidebar
st.sidebar.markdown("---")
with st.sidebar.expander("App Status"):
    # Display status of loaded data
    roster_status = "✅ Loaded" if st.session_state.roster is not None else "❌ Not loaded"
    schedule_status = "✅ Loaded" if st.session_state.schedule is not None else "❌ Not loaded"
    batting_status = "✅ Configured" if st.session_state.batting_orders else "❌ Not configured"
    fielding_status = "✅ Configured" if st.session_state.fielding_rotations else "❌ Not configured"
    
    st.write(f"**Team Roster:** {roster_status}")
    st.write(f"**Game Schedule:** {schedule_status}")
    st.write(f"**Batting Orders:** {batting_status}")
    st.write(f"**Fielding Rotations:** {fielding_status}")

# Add app info in sidebar footer
st.sidebar.markdown("---")
st.sidebar.info("LineupBoss v1.0")

