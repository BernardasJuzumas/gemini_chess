# Gemini Chess Game

A chess game implementation where two Google Gemini AI models play against each other.

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

## Features

- Two Gemini AI models play chess against each other
- Full chess rule validation using the `python-chess` library
- Dynamic prompting that adapts based on the current player (white/black)
- Game state tracking with FEN notation
- Automatic game saving to `games/` directory with timestamp
- Move history and explanations
- Position evaluation from AI perspective

## Game Output

- Games are saved as JSON files in the `games/` directory
- Filename format: `game_YYYY-MM-DD.json` (with counter if multiple games per day)
- Each saved game includes:
  - Complete move history with explanations
  - Position evaluations
  - Final result
  - FEN notation for each position

  ## Sample console output

```
Move 26: black's turn
  Rc8 - The move Rc8 is a strong and principled choice that continues Black's development and actively exploits White's central pawn structure. As Black is currently up a knight, the strategy should focus on simplifying the position and maintaining the initiative. By moving the rook to c8, Black achieves several key objectives: 1. Develops the last major piece: The rook on a8 comes into play on the c-file, coordinating with other pieces. 2. Applies direct pressure on White's d4 pawn: The rook immediately attacks White's strong central pawn, forcing White to respond and potentially leading to simplification or a weakening of White's center. 3. Prepares for further central expansion: The c-file is opened, allowing for potential future advances of Black's c-pawn or further rook activity. This move creates threats and maintains Black's advantage, pushing towards a winning endgame by actively converting the material lead.
  Evaluation: 2.5
Current position:
. . r q r . k .
. . p . b p p p
p . . p . n . .
. p . . n b . .
. . . P P . . .
. B . . . . . .
P P . N . P P P
R . B Q . R K .

Move 27: white's turn
  Qe2 - White is facing a significant material disadvantage, being down a bishop and a knight. In this critical situation, the move Qe2 is the most principled and strongest choice for White. It serves several crucial purposes: Firstly, it actively develops the queen to a more central and active square, bringing it into play and preparing to connect the rooks. Secondly, and most importantly, Qe2 simultaneously defends both the d4 and e4 central pawns, which are currently under attack by Black's rook on c8 and bishop on f5 respectively. This prophylactic move ensures the stability of White's pawn structure and prevents further material losses. While this move does not regain material or create immediate threats, it solidifies White's position, improves piece coordination, and aims to weather Black's significant material advantage by maintaining a cohesive defense and hoping for tactical opportunities in the long run. White's strategic objective must now shift towards creating counterplay and seeking to complicate the game to compensate for the lost material.
  Evaluation: -6.0
Current position:
. . r q r . k .
. . p . b p p p
p . . p . n . .
. p . . n b . .
. . . P P . . .
. B . . . . . .
P P . N Q P P P
R . B . . R K .
```

## Customization

You can modify:
- Maximum number of moves per game (default: 100)
- AI model used (currently using `gemini-2.5-flash`)
- Prompting strategy in the `create_prompt_for_ai` method


