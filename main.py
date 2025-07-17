from google import genai
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os
import chess
import chess.pgn
import json
from datetime import datetime
from typing import Optional
import sys
import glob

# Load environment variables from .env file
load_dotenv()


# Pydantic model structuring a response to one chess move
class ChessMoveResponse(BaseModel):
    move: str = Field(..., description="The chess move in standard algebraic notation")
    evaluation: float = Field(..., description="Evaluation of the move from the AI's perspective")
    explanation: str = Field(..., description="Explanation of why this move is recommended")

# Chess game state
class ChessGameState(BaseModel):
    board: str = Field(..., description="Current state of the chess board in FEN notation")
    turn: str = Field(..., description="Current turn, either 'white' or 'black'")
    history: list[ChessMoveResponse] = Field(default_factory=list, description="History of moves made in the game")
    move_count: int = Field(default=0, description="Number of moves made in the game")
    game_over: bool = Field(default=False, description="Whether the game is over")
    result: Optional[str] = Field(default=None, description="Game result (1-0, 0-1, 1/2-1/2)")

    @classmethod
    def new_game(cls):
        return cls(
            board=chess.STARTING_FEN,
            turn="white",
            history=[],
            move_count=0,
            game_over=False,
            result=None
        )
    

# Game class and methods
class ChessGame(BaseModel):
    state: ChessGameState
    white_client: genai.Client = Field(exclude=True)
    black_client: genai.Client = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        super().__init__(**data)
        if 'white_client' not in data:
            self.white_client = genai.Client()
        if 'black_client' not in data:
            self.black_client = genai.Client()

    @classmethod
    def new_game(cls):
        return cls(
            state=ChessGameState.new_game(),
            white_client=genai.Client(),
            black_client=genai.Client()
        )

    def get_board_visualization(self) -> str:
        """Get a text representation of the current board position."""
        board = chess.Board(self.state.board)
        return self.format_board_unicode(board)
    
    @staticmethod
    def format_board_unicode(board: chess.Board) -> str:
        """Format chess board with Unicode pieces for better visualization."""
        # Unicode chess pieces
        piece_symbols = {
            'P': '♙', 'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔',  # White pieces
            'p': '♟', 'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚'   # Black pieces
        }
        
        lines = []
        lines.append("  ┌───┬───┬───┬───┬───┬───┬───┬───┐")
        
        for rank in range(7, -1, -1):  # 8 to 1
            line = f"{rank + 1} │"
            for file in range(8):  # a to h
                square = chess.square(file, rank)
                piece = board.piece_at(square)
                
                if piece:
                    symbol = piece_symbols.get(piece.symbol(), piece.symbol())
                else:
                    # Checkered pattern for empty squares
                    if (rank + file) % 2 == 0:
                        symbol = ' '  # Light square
                    else:
                        symbol = ' '  # Dark square
                
                line += f" {symbol} │"
            lines.append(line)
            
            if rank > 0:
                lines.append("  ├───┼───┼───┼───┼───┼───┼───┼───┤")
        
        lines.append("  └───┴───┴───┴───┴───┴───┴───┴───┘")
        lines.append("    a   b   c   d   e   f   g   h")
        
        return "\n".join(lines)

    def get_move_history_text(self) -> str:
        """Get formatted move history for the prompt."""
        if not self.state.history:
            return "No moves have been made yet."
        
        history_text = "Move history:\n"
        for i, move_response in enumerate(self.state.history, 1):
            color = "White" if i % 2 == 1 else "Black"
            history_text += f"{i}. {color}: {move_response.move}"
        return history_text

    def create_prompt_for_ai(self, color: str) -> str:
        """Create a detailed prompt for the AI to make a move."""
        opponent_color = "black" if color == "white" else "white"
        
        prompt = f"""You are playing chess as {color}. It's your turn to move.

Current board position (from white's perspective):
{self.get_board_visualization()}

Current board state in FEN notation: {self.state.board}

{self.get_move_history_text()}

Please analyze the position and make your next move. Consider:
1. Tactical opportunities (checks, captures, threats)
2. Strategic elements (piece development, king safety, pawn structure)
3. Your opponent's potential responses
4. Overall game plan

Provide your move in standard algebraic notation (e.g., "e4", "Nf3", "O-O", "Qxd7+").
Give an evaluation of the position from your perspective (positive means good for you).
Explain your reasoning clearly.

You are playing as {color}. Make your move now."""

        return prompt

    def is_valid_move(self, move_str: str) -> bool:
        """Validate if a move is legal in the current position."""
        try:
            board = chess.Board(self.state.board)
            move = board.parse_san(move_str)
            return move in board.legal_moves
        except:
            return False

    def apply_move(self, move_str: str) -> bool:
        """Apply a move to the board and update game state."""
        try:
            board = chess.Board(self.state.board)
            move = board.parse_san(move_str)
            
            if move not in board.legal_moves:
                return False
            
            board.push(move)
            self.state.board = board.fen()
            self.state.turn = "black" if self.state.turn == "white" else "white"
            self.state.move_count += 1
            
            # Check for game over conditions
            if board.is_game_over():
                self.state.game_over = True
                result = board.result()
                self.state.result = result
            
            return True
        except:
            return False

    def get_ai_move(self, color: str) -> ChessMoveResponse:
        """Get AI move from Gemini model."""
        client = self.white_client if color == "white" else self.black_client
        prompt = self.create_prompt_for_ai(color)
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ChessMoveResponse,
                },
            )
            
            if response.text is None:
                raise ValueError("Empty response from AI")
            
            move_response = ChessMoveResponse.model_validate_json(response.text)
            
            # Validate the move
            if not self.is_valid_move(move_response.move):
                # If invalid move, try to get a valid one
                board = chess.Board(self.state.board)
                legal_moves = [board.san(move) for move in board.legal_moves]
                fallback_prompt = f"{prompt}\n\nYour previous move '{move_response.move}' was invalid. Here are the legal moves: {', '.join(legal_moves[:10])}. Please choose one of these moves."
                
                fallback_response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=fallback_prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": ChessMoveResponse,
                    },
                )
                
                if fallback_response.text is None:
                    raise ValueError("Empty fallback response from AI")
                
                move_response = ChessMoveResponse.model_validate_json(fallback_response.text)
            
            return move_response
            
        except Exception as e:
            print(f"Error getting AI move: {e}")
            # Fallback to a random legal move
            board = chess.Board(self.state.board)
            legal_moves = list(board.legal_moves)
            if legal_moves:
                random_move = legal_moves[0]
                return ChessMoveResponse(
                    move=board.san(random_move),
                    evaluation=0.0,
                    explanation=f"Fallback move due to AI error: {e}"
                )
            else:
                raise ValueError("No legal moves available")

    def play_turn(self) -> ChessMoveResponse:
        """Play one turn of the game."""
        if self.state.game_over:
            raise ValueError("Game is already over")
        
        current_color = self.state.turn
        move_response = self.get_ai_move(current_color)
        
        # Apply the move
        if self.apply_move(move_response.move):
            self.state.history.append(move_response)
            return move_response
        else:
            raise ValueError(f"Failed to apply move: {move_response.move}")

    def play_full_game(self, max_moves: int = 100) -> dict:
        """Play a complete game between two AI players."""
        print("Starting new chess game between two Gemini models...")
        print(f"Initial position:\n{self.get_board_visualization()}\n")
        
        game_log = []
        
        while not self.state.game_over and self.state.move_count < max_moves:
            try:
                print(f"Move {self.state.move_count + 1}: {self.state.turn}'s turn")
                move_response = self.play_turn()
                
                game_log.append({
                    "move_number": self.state.move_count,
                    "color": "white" if self.state.move_count % 2 == 1 else "black",
                    "move": move_response.move,
                    "evaluation": move_response.evaluation,
                    "explanation": move_response.explanation,
                    "fen": self.state.board
                })
                
                print(f"  {move_response.move} - {move_response.explanation}")
                print(f"  Evaluation: {move_response.evaluation}")
                print(f"Current position:\n{self.get_board_visualization()}\n")
                
            except Exception as e:
                print(f"Error during move: {e}")
                break
        
        # Game summary
        game_summary = {
            "date": datetime.now().isoformat(),
            "result": self.state.result or "Game incomplete",
            "total_moves": self.state.move_count,
            "final_fen": self.state.board,
            "game_over": self.state.game_over,
            "moves": game_log
        }
        
        print(f"Game finished! Result: {game_summary['result']}")
        print(f"Total moves: {game_summary['total_moves']}")
        
        return game_summary

    def save_game(self, game_summary: dict) -> str:
        """Save the completed game to a JSON file."""
        date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"game_{date_str}.json"
        filepath = os.path.join("games", filename)
        
        # Create games directory if it doesn't exist
        os.makedirs("games", exist_ok=True)
        
        # If file exists, add a counter
        counter = 1
        while os.path.exists(filepath):
            filename = f"game_{date_str}_{counter:02d}.json"
            filepath = os.path.join("games", filename)
            counter += 1
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(game_summary, f, indent=2, ensure_ascii=False)
        
        print(f"Game saved to: {filepath}")
        return filepath

def replay_game(json_file: str):
    """Replay a saved game move by move."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            game_data = json.load(f)
        
        print(f"=== Replaying Game ===")
        print(f"Date: {game_data['date']}")
        print(f"Result: {game_data['result']}")
        print(f"Total moves: {game_data['total_moves']}")
        print("\nPress Enter to see each move, Ctrl+C to exit")
        print("=" * 50)
        
        # Start with initial position
        board = chess.Board()
        print(f"\nInitial position:")
        print(ChessGame.format_board_unicode(board))
        
        try:
            input("\nPress Enter to start...")
        except KeyboardInterrupt:
            print("\nReplay cancelled.")
            return
        
        # Replay each move
        for move_data in game_data['moves']:
            try:
                move_num = move_data['move_number']
                color = move_data['color']
                move = move_data['move']
                evaluation = move_data['evaluation']
                explanation = move_data['explanation']
                
                # Apply the move
                chess_move = board.parse_san(move)
                board.push(chess_move)
                
                print(f"\nMove {move_num}: {color.title()} plays {move}")
                print(f"Evaluation: {evaluation:.2f}")
                print(f"Reasoning: {explanation}")
                print()
                print(ChessGame.format_board_unicode(board))
                
                if move_num < game_data['total_moves']:
                    try:
                        input(f"\nPress Enter for next move...")
                    except KeyboardInterrupt:
                        print("\nReplay cancelled.")
                        return
                        
            except Exception as e:
                print(f"Error replaying move {move_data.get('move_number', '?')}: {e}")
                continue
        
        print(f"\n=== Game Over ===")
        print(f"Final result: {game_data['result']}")
        
    except FileNotFoundError:
        print(f"Game file not found: {json_file}")
    except json.JSONDecodeError:
        print(f"Invalid JSON file: {json_file}")
    except Exception as e:
        print(f"Error replaying game: {e}")

def list_saved_games():
    """List all saved games in the games directory."""
    games_pattern = os.path.join("games", "game_*.json")
    game_files = glob.glob(games_pattern)
    
    if not game_files:
        print("No saved games found in the games directory.")
        return []
    
    print("Saved games:")
    game_files.sort(reverse=True)  # Most recent first
    
    for i, filepath in enumerate(game_files, 1):
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                game_data = json.load(f)
            date = game_data.get('date', 'Unknown date')
            result = game_data.get('result', 'Unknown result')
            moves = game_data.get('total_moves', 0)
            print(f"{i:2d}. {filename} - {date[:19]} - {result} ({moves} moves)")
        except:
            print(f"{i:2d}. {filename} - (Error reading file)")
    
    return game_files

def interactive_menu():
    """Interactive menu for playing or replaying games."""
    while True:
        print("\n" + "=" * 50)
        print("🏁 Gemini Chess Game Menu")
        print("=" * 50)
        print("1. Play new game")
        print("2. Replay saved game")
        print("3. List saved games")
        print("4. Exit")
        print("=" * 50)
        
        try:
            choice = input("Enter your choice (1-4): ").strip()
            
            if choice == "1":
                print("\nStarting new game...")
                main_game()
            
            elif choice == "2":
                game_files = list_saved_games()
                if game_files:
                    try:
                        selection = input(f"\nEnter game number (1-{len(game_files)}) or filename: ").strip()
                        
                        if selection.isdigit():
                            game_index = int(selection) - 1
                            if 0 <= game_index < len(game_files):
                                replay_game(game_files[game_index])
                            else:
                                print("Invalid game number.")
                        else:
                            # Try as filename
                            if not selection.endswith('.json'):
                                selection += '.json'
                            filepath = os.path.join("games", selection)
                            if os.path.exists(filepath):
                                replay_game(filepath)
                            else:
                                print(f"Game file not found: {selection}")
                    except ValueError:
                        print("Invalid input.")
            
            elif choice == "3":
                list_saved_games()
            
            elif choice == "4":
                print("Goodbye!")
                break
            
            else:
                print("Invalid choice. Please enter 1-4.")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break

def main_game():
    """Main function to run a chess game between two Gemini models."""
    try:
        # Create a new chess game
        game = ChessGame.new_game()
        
        # Play the full game
        game_summary = game.play_full_game(max_moves=100)
        
        # Save the game
        filepath = game.save_game(game_summary)
        
        print(f"\n=== Game Summary ===")
        print(f"Result: {game_summary['result']}")
        print(f"Total moves: {game_summary['total_moves']}")
        print(f"Saved to: {filepath}")
        
    except Exception as e:
        print(f"Error running game: {e}")

def main():
    """Main entry point with interactive menu."""
    if len(sys.argv) > 1:
        # Command line argument provided
        arg = sys.argv[1]
        if arg == "--play":
            main_game()
        elif arg == "--replay":
            if len(sys.argv) > 2:
                replay_game(sys.argv[2])
            else:
                print("Please provide a game file to replay.")
                print("Usage: python main.py --replay <game_file.json>")
        elif arg == "--list":
            list_saved_games()
        else:
            print("Unknown argument. Use --play, --replay <file>, or --list")
    else:
        # Interactive menu
        interactive_menu()

if __name__ == "__main__":
    main() 