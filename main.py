from google import genai
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os
import chess
import chess.pgn
import json
from datetime import datetime
from typing import Optional

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
        return str(board)

    def get_move_history_text(self) -> str:
        """Get formatted move history for the prompt."""
        if not self.state.history:
            return "No moves have been made yet."
        
        history_text = "Move history:\n"
        for i, move_response in enumerate(self.state.history, 1):
            color = "White" if i % 2 == 1 else "Black"
            history_text += f"{i}. {color}: {move_response.move} - {move_response.explanation}\n"
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
        date_str = datetime.now().strftime("%Y-%m-%d")
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

def main():
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

if __name__ == "__main__":
    main() 