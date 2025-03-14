# LineupBoss - Baseball Lineup Manager

A comprehensive Streamlit application for managing baseball team lineups, batting orders, and fielding rotations.

![LineupBoss](https://github.com/your-username/lineupboss/raw/main/screenshot.png)

## Features

- **Team Management**: Create and manage team roster with player names and jersey numbers
- **Game Scheduling**: Set up your season schedule with dates, times, and opponents
- **Player Availability**: Track which players are available for each game
- **Batting Order**: Create fair batting orders across all games
- **Fielding Rotation**: Assign fielding positions for each inning
- **Fairness Analysis**: Analyze how balanced your batting and fielding assignments are
- **Game Plans**: Generate and export game-day lineup sheets in PDF or text format
- **Data Management**: Save and load your team data for future use

## Installation

1. Clone this repository:
```bash
git clone https://github.com/your-username/lineupboss.git
cd lineupboss
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Run the app:
```bash
streamlit run lineup.py
```

## Usage Guide

### Step 1: Setup
1. Start at the Team Setup tab to enter your team information and create your roster
2. Create your game schedule with dates, times, and opponent information
3. Use the Player Setup tab to mark availability for each game

### Step 2: Create Lineups
1. Set batting orders for each game in the Batting Order tab
2. Assign fielding positions for each inning in the Fielding Rotation tab
3. Use validation tools to check for issues with your lineups

### Step 3: Analyze Fairness
1. Check the Batting Fairness tab to ensure all players get opportunities in different batting positions
2. Use the Fielding Fairness tab to analyze playing time distribution across positions

### Step 4: Game Day
1. Visit the Game Summary tab to view complete game plans
2. Export game plans as PDF or text files to share with coaches and players
3. Save your data using the Data Management tab

## Data Storage

LineupBoss stores all data in a PostgreSQL database:
1. Changes are saved automatically as you work
2. Your data persists between sessions without manual exports/imports
3. You can access your data from any device

### Local Development
For local development, set up a PostgreSQL database and create a `.env` file with:
```
DATABASE_URL=postgresql://username:password@hostname/database
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### Streamlit Cloud Deployment
To deploy to Streamlit Cloud:
1. Fork/push this repository to GitHub
2. Create a new app in Streamlit Cloud pointing to your repository
3. Add the following secrets in the Streamlit Cloud dashboard:
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `ANTHROPIC_API_KEY`: Your Anthropic API key (if using fielding generation feature)
4. Deploy your app

## Requirements

- Python 3.8+
- Streamlit 1.28+
- See requirements.txt for complete dependencies