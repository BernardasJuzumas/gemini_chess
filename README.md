# Gemini Chess Game

A chess game implementation where two Google Gemini AI models play against each other, featuring beautiful Unicode board visualization and interactive game replay.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up your Google AI API key:
   - Copy `.env.example` to `.env`
   - Add your Google AI API key to the `.env` file
   - Get your API key from: https://ai.google.dev/

3. Run the game:
   ```
   python main.py
   ```

## Usage

### Interactive Menu
Run `python main.py` to access the interactive menu:
- **Play new game**: Start a fresh match between two AI models
- **Replay saved game**: Watch previous games move by move
- **List saved games**: See all games in your collection
- **Exit**: Quit the application

### Command Line Options
- `python main.py --play` - Start a new game directly
- `python main.py --replay <filename.json>` - Replay a specific game
- `python main.py --list` - List all saved games

### Game Replay Controls
- Press **Enter** to advance to the next move
- Press **Ctrl+C** to exit the replay at any time

## Features

- **Unicode Chess Board for CLI**: Clear visual representation with chess piece symbols
- **Interactive Game Replay**: Step through saved games move by move
- **Two AI Players**: Gemini models play against each other with different strategies
- **Full Chess Validation**: Complete rule enforcement using `python-chess`
- **Smart Move Analysis**: AI provides evaluations and explanations for each move
- **Game Collection**: All games saved with timestamps for future replay
- **Fallback System**: Handles AI errors gracefully with valid move selection

## Board Visualization

The game features a beautiful Unicode chess board display:

```

```

## Game Output

- Games are saved as JSON files in the `games/` directory
- Filename format: `game_YYYY-MM-DD-HH-MM-SS.json` with full timestamp
- Each saved game includes:
  - Complete move history with explanations
  - Position evaluations
  - Final result
  - FEN notation for each position


## Customization

You can modify:
- Maximum number of moves per game (default: 100)
- AI model used (currently using `gemini-2.5-flash`)
- Prompting strategy in the `create_prompt_for_ai` method


