import os
import uuid
import random
import json
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
import sqlite3
from threading import Lock

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'hard_to_get_game_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Setup database
def init_db():
    conn = sqlite3.connect('hard_to_get.db')
    cursor = conn.cursor()
    
    # Create clients table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clients (
        uuid TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        status TEXT DEFAULT 'available'
    )
    ''')
    
    # Create games table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id TEXT PRIMARY KEY,
        witness_uuid TEXT,
        detective_uuid TEXT,
        status TEXT DEFAULT 'pending',
        key_word TEXT,
        current_round INTEGER DEFAULT 0,
        board TEXT,
        FOREIGN KEY (witness_uuid) REFERENCES clients (uuid),
        FOREIGN KEY (detective_uuid) REFERENCES clients (uuid)
    )
    ''')
    
    # Create results table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        game_id TEXT PRIMARY KEY,
        witness_uuid TEXT,
        witness_model TEXT,
        detective_uuid TEXT,
        detective_model TEXT,
        result TEXT,
        FOREIGN KEY (game_id) REFERENCES games (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Load words and dilemmas from files
def load_words():
    if not os.path.exists('words.txt'):
        # Generate sample words if file doesn't exist
        generate_words_file()
    with open('words.txt', 'r') as f:
        return [line.strip() for line in f if line.strip()]

def load_dilemmas():
    if not os.path.exists('dilemmas.txt'):
        # Generate sample dilemmas if file doesn't exist
        generate_dilemmas_file()
    with open('dilemmas.txt', 'r') as f:
        return [line.strip().split(',') for line in f if line.strip()]

# Generate sample files if they don't exist
def generate_words_file():
    words = [
        "The Lion King", "Beyonce", "Virtual reality", "Smart phone", "Salad", 
        "Doughnut", "Basketball", "Bowling", "Bookshelf", "Grand Theft Auto", 
        "Anxiety", "Canada", "Hawaii", "Avengers", "Giraffe", "Sausage", 
        "Madonna", "Harry Styles", "Corn dog", "Nachos", "Thor", "James Bond", 
        "Hash browns", "Oatmeal", "Solar system", "Bridge", "Cobra", "Spider", 
        "Eagle", "Poison ivy", "Mount Everest", "Star Wars", "Rowboat", 
        "Horoscope", "Coffee", "Telescope", "Piano", "Guitar", "Diamond", 
        "Football", "Swimming", "Mountain", "Ocean", "Desert", "Forest",
        "Space station", "Chocolate", "Vanilla", "Strawberry", "Winter",
        "Summer", "Spring", "Fall", "Wedding", "Funeral", "Birthday",
        "Anniversary", "Hospital", "School", "University", "Library",
        "Museum", "Theater", "Cinema", "Restaurant", "Cafe", "Park",
        "Beach", "Lake", "River", "Island", "Continent", "Planet",
        "Galaxy", "Universe", "Atom", "Molecule", "Cell", "Tissue",
        "Organ", "System", "Body", "Mind", "Soul", "Spirit",
        "Angel", "Demon", "Ghost", "Vampire", "Werewolf", "Zombie",
        "Robot", "Cyborg", "Android", "AI", "VR", "AR", "MR",
        "Cloud", "Rain", "Snow", "Hail", "Sleet", "Fog", "Mist"
    ]
    
    # Generate 500 words total
    additional_words = [
        f"Item {i}" for i in range(len(words) + 1, 501)
    ]
    
    all_words = words + additional_words
    
    with open('words.txt', 'w') as f:
        for word in all_words:
            f.write(f"{word}\n")

def generate_dilemmas_file():
    dilemmas = [
        "Sinner,Saint", "Soft,Hard", "Dry,Wet", "Slow,Fast", 
        "Where's Waldo,Walter White", "Superman,Batman", 
        "Ghost town,Metropolis", "Puddle,Fountain", "Nature,Nurture", 
        "Coca-Cola,Pepsi", "Checkers,Chess", "Microscope,Telescope", 
        "Jam,Jelly", "Solution,Problem", "Rollerskating,Skateboarding", 
        "Store bought,Homemade", "Fight,Flight", "Peanut,Pistachio", 
        "Dinner,Breakfast", "Sour,Sweet", "Heavy,Light",
        "Introvert,Extrovert", "Online,Offline", "Public,Private",
        "Analog,Digital", "Manual,Automatic", "Simple,Complex"
    ]
    
    # Generate 150 dilemmas total
    additional_dilemmas = [
        f"Option A {i},Option B {i}" for i in range(len(dilemmas) + 1, 151)
    ]
    
    all_dilemmas = dilemmas + additional_dilemmas
    
    with open('dilemmas.txt', 'w') as f:
        for dilemma in all_dilemmas:
            f.write(f"{dilemma}\n")

# Game state management
class GameManager:
    def __init__(self):
        self.lock = Lock()
        self.words = load_words()
        self.dilemmas = load_dilemmas()
        
        # Initialize the database
        init_db()
    
    def register_client(self, model_name):
        """Register a new client and return its UUID"""
        client_id = str(uuid.uuid4())
        
        conn = sqlite3.connect('hard_to_get.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO clients (uuid, model_name) VALUES (?, ?)',
                      (client_id, model_name))
        conn.commit()
        conn.close()
        
        return client_id
    
    def create_or_join_game(self, client_id, preferred_role=None):
        """Create a new game or join an existing one"""
        with self.lock:
            conn = sqlite3.connect('hard_to_get.db')
            cursor = conn.cursor()
            
            # First update client status to searching
            cursor.execute('UPDATE clients SET status = ? WHERE uuid = ?',
                          ('searching', client_id))
            
            # Check if there's a pending game that needs this role
            available_game = None
            
            if preferred_role == 'Detective':
                # Look for a game with a Witness but no Detective
                cursor.execute('''
                SELECT id FROM games 
                WHERE detective_uuid IS NULL AND witness_uuid IS NOT NULL
                AND status = 'pending'
                LIMIT 1
                ''')
                game_result = cursor.fetchone()
                
                if game_result:
                    game_id = game_result[0]
                    cursor.execute('''
                    UPDATE games SET detective_uuid = ? WHERE id = ?
                    ''', (client_id, game_id))
                    available_game = game_id
            
            elif preferred_role == 'Witness':
                # Look for a game with a Detective but no Witness
                cursor.execute('''
                SELECT id FROM games 
                WHERE witness_uuid IS NULL AND detective_uuid IS NOT NULL
                AND status = 'pending'
                LIMIT 1
                ''')
                game_result = cursor.fetchone()
                
                if game_result:
                    game_id = game_result[0]
                    cursor.execute('''
                    UPDATE games SET witness_uuid = ? WHERE id = ?
                    ''', (client_id, game_id))
                    available_game = game_id
            
            else:
                # Random role assignment - check if there's any incomplete game
                cursor.execute('''
                SELECT id, witness_uuid, detective_uuid FROM games 
                WHERE (witness_uuid IS NULL OR detective_uuid IS NULL)
                AND status = 'pending'
                LIMIT 1
                ''')
                game_result = cursor.fetchone()
                
                if game_result:
                    game_id, witness_id, detective_id = game_result
                    
                    if witness_id is None:
                        cursor.execute('''
                        UPDATE games SET witness_uuid = ? WHERE id = ?
                        ''', (client_id, game_id))
                        available_game = game_id
                    else:
                        cursor.execute('''
                        UPDATE games SET detective_uuid = ? WHERE id = ?
                        ''', (client_id, game_id))
                        available_game = game_id
            
            # If no suitable game found, create a new one
            if not available_game:
                game_id = str(uuid.uuid4())
                
                # Generate a board of 16 random words
                board_words = random.sample(self.words, 16)
                board_json = json.dumps(board_words)
                
                if preferred_role == 'Witness':
                    cursor.execute('''
                    INSERT INTO games (id, witness_uuid, board)
                    VALUES (?, ?, ?)
                    ''', (game_id, client_id, board_json))
                elif preferred_role == 'Detective':
                    cursor.execute('''
                    INSERT INTO games (id, detective_uuid, board)
                    VALUES (?, ?, ?)
                    ''', (game_id, client_id, board_json))
                else:
                    # Randomly assign as witness or detective for the new game
                    if random.choice([True, False]):
                        cursor.execute('''
                        INSERT INTO games (id, witness_uuid, board)
                        VALUES (?, ?, ?)
                        ''', (game_id, client_id, board_json))
                    else:
                        cursor.execute('''
                        INSERT INTO games (id, detective_uuid, board)
                        VALUES (?, ?, ?)
                        ''', (game_id, client_id, board_json))
                
                available_game = game_id
            
            # Update client status
            cursor.execute('UPDATE clients SET status = ? WHERE uuid = ?',
                          ('in_game', client_id))
            
            # Check if the game is now complete (has both roles)
            cursor.execute('''
            SELECT witness_uuid, detective_uuid FROM games WHERE id = ?
            ''', (available_game,))
            game_roles = cursor.fetchone()
            
            game_ready = False
            if game_roles and game_roles[0] and game_roles[1]:
                cursor.execute('''
                UPDATE games SET status = 'ready' WHERE id = ?
                ''', (available_game,))
                game_ready = True
            
            conn.commit()
            
            # Get the assigned role for this client
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN witness_uuid = ? THEN 'Witness'
                    WHEN detective_uuid = ? THEN 'Detective'
                    ELSE NULL
                END as role,
                board
            FROM games WHERE id = ?
            ''', (client_id, client_id, available_game))
            
            role_result = cursor.fetchone()
            assigned_role = role_result[0] if role_result else None
            board = json.loads(role_result[1]) if role_result else []
            
            conn.close()
            
            response = {
                'game_id': available_game,
                'role': assigned_role,
                'game_ready': game_ready,
                'board': board
            }
            
            # If game is ready, initiate the first round for the Witness
            if game_ready:
                self.start_game(available_game)
            
            return response
    
    def start_game(self, game_id):
        """Initialize the game by selecting a key word and notifying players"""
        conn = sqlite3.connect('hard_to_get.db')
        cursor = conn.cursor()
        
        # Get the game board
        cursor.execute('SELECT board FROM games WHERE id = ?', (game_id,))
        board_json = cursor.fetchone()[0]
        board = json.loads(board_json)
        
        # Select a random word as the key word
        key_word = random.choice(board)
        
        # Update the game with the key word and set round to 1
        cursor.execute('''
        UPDATE games SET key_word = ?, current_round = 1, status = 'active'
        WHERE id = ?
        ''', (key_word, game_id))
        
        # Get player UUIDs
        cursor.execute('''
        SELECT witness_uuid, detective_uuid FROM games WHERE id = ?
        ''', (game_id,))
        witness_uuid, detective_uuid = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        # Notify players that the game has started
        socketio.emit('game_started', {'game_id': game_id}, room=game_id)
        
        # Send the key word to the witness
        self.send_witness_key_word(game_id, witness_uuid, key_word)
    
    def send_witness_key_word(self, game_id, witness_uuid, key_word):
        """Send the key word to the witness and initiate the first round"""
        # Get a random dilemma
        dilemma = random.choice(self.dilemmas)
        
        # Send the key word and dilemma to the witness
        payload = {
            'key_word': key_word,
            'dilemma': dilemma,
            'round': 1
        }
        
        socketio.emit('witness_turn', payload, room=witness_uuid)
    
    def witness_response(self, game_id, client_id, dilemma_choice):
        """Process witness's dilemma choice and notify detective"""
        conn = sqlite3.connect('hard_to_get.db')
        cursor = conn.cursor()
        
        # Verify this client is the witness for this game
        cursor.execute('''
        SELECT current_round, detective_uuid FROM games 
        WHERE id = ? AND witness_uuid = ? AND status = 'active'
        ''', (game_id, client_id))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return {'error': 'Invalid witness or game state'}
        
        current_round, detective_uuid = result
        
        # Get the dilemma that was presented
        dilemma = self.dilemmas[random.randint(0, len(self.dilemmas) - 1)]
        
        # Create notification for detective
        detective_payload = {
            'game_id': game_id,
            'round': current_round,
            'dilemma': dilemma,
            'witness_choice': dilemma_choice
        }
        
        conn.close()
        
        # Notify detective it's their turn
        socketio.emit('detective_turn', detective_payload, room=detective_uuid)
        
        return {'status': 'success'}
    
    def detective_response(self, game_id, client_id, eliminated_words):
        """Process detective's word eliminations and advance the game"""
        conn = sqlite3.connect('hard_to_get.db')
        cursor = conn.cursor()
        
        # Verify this client is the detective for this game
        cursor.execute('''
        SELECT current_round, witness_uuid, key_word, board 
        FROM games 
        WHERE id = ? AND detective_uuid = ? AND status = 'active'
        ''', (game_id, client_id))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return {'error': 'Invalid detective or game state'}
        
        current_round, witness_uuid, key_word, board_json = result
        board = json.loads(board_json)
        
        # Check if key word was eliminated
        key_word_eliminated = key_word in eliminated_words
        
        # Update board by removing eliminated words
        updated_board = [word for word in board if word not in eliminated_words]
        
        # Determine game state
        game_over = False
        win = False
        
        if key_word_eliminated:
            # Game over - key word eliminated
            game_over = True
            win = False
        elif len(updated_board) == 1 and updated_board[0] == key_word:
            # Game over - only key word remains
            game_over = True
            win = True
        elif current_round >= 5:
            # Game over - reached maximum rounds
            game_over = True
            win = len(updated_board) == 1 and updated_board[0] == key_word
        
        # Update game state
        if game_over:
            cursor.execute('''
            UPDATE games SET status = ?, board = ?
            WHERE id = ?
            ''', ('completed', json.dumps(updated_board), game_id))
            
            # Record the result
            self.save_game_result(cursor, game_id, win)
        else:
            # Move to next round
            cursor.execute('''
            UPDATE games SET current_round = ?, board = ?
            WHERE id = ?
            ''', (current_round + 1, json.dumps(updated_board), game_id))
        
        conn.commit()
        conn.close()
        
        # Send appropriate notifications
        if game_over:
            # Notify both players about game end
            end_payload = {
                'game_id': game_id,
                'win': win,
                'key_word': key_word,
                'final_board': updated_board
            }
            socketio.emit('game_ended', end_payload, room=game_id)
        else:
            # Notify witness for the next round
            self.start_next_round(game_id, witness_uuid, key_word, current_round + 1)
        
        return {
            'status': 'success',
            'game_over': game_over,
            'win': win if game_over else None,
            'remaining_words': updated_board,
            'key_word_eliminated': key_word_eliminated
        }
    
    def start_next_round(self, game_id, witness_uuid, key_word, next_round):
        """Start the next round by sending a new dilemma to the witness"""
        # Get a random dilemma
        dilemma = random.choice(self.dilemmas)
        
        # Send the key word and dilemma to the witness
        payload = {
            'game_id': game_id,
            'key_word': key_word,
            'dilemma': dilemma,
            'round': next_round
        }
        
        socketio.emit('witness_turn', payload, room=witness_uuid)
    
    def save_game_result(self, cursor, game_id, win):
        """Save the game result to the database"""
        # Get player information
        cursor.execute('''
        SELECT g.witness_uuid, c1.model_name, g.detective_uuid, c2.model_name
        FROM games g
        JOIN clients c1 ON g.witness_uuid = c1.uuid
        JOIN clients c2 ON g.detective_uuid = c2.uuid
        WHERE g.id = ?
        ''', (game_id,))
        
        witness_uuid, witness_model, detective_uuid, detective_model = cursor.fetchone()
        
        # Insert into results table
        cursor.execute('''
        INSERT INTO results 
        (game_id, witness_uuid, witness_model, detective_uuid, detective_model, result)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (game_id, witness_uuid, witness_model, detective_uuid, detective_model, 
              'win' if win else 'loss'))

# Initialize game manager
game_manager = GameManager()

# Define Flask routes
@app.route('/register', methods=['POST'])
def register_client():
    data = request.json
    model_name = data.get('model_name', 'unknown')
    
    client_id = game_manager.register_client(model_name)
    
    return jsonify({
        'client_id': client_id,
        'status': 'registered'
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.json
    client_id = data.get('client_id')
    preferred_role = data.get('preferred_role')  # 'Witness', 'Detective', or None for random
    
    if not client_id:
        return jsonify({'error': 'Client ID is required'}), 400
    
    game_info = game_manager.create_or_join_game(client_id, preferred_role)
    
    return jsonify(game_info)

@app.route('/witness_choice', methods=['POST'])
def witness_choice():
    data = request.json
    game_id = data.get('game_id')
    client_id = data.get('client_id')
    dilemma_choice = data.get('dilemma_choice')
    
    if not all([game_id, client_id, dilemma_choice]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    result = game_manager.witness_response(game_id, client_id, dilemma_choice)
    
    return jsonify(result)

@app.route('/detective_choice', methods=['POST'])
def detective_choice():
    data = request.json
    game_id = data.get('game_id')
    client_id = data.get('client_id')
    eliminated_words = data.get('eliminated_words', [])
    
    if not all([game_id, client_id]) or not eliminated_words:
        return jsonify({'error': 'Missing required fields'}), 400
    
    result = game_manager.detective_response(game_id, client_id, eliminated_words)
    
    return jsonify(result)

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    pass

@socketio.on('join')
def handle_join(data):
    client_id = data.get('client_id')
    game_id = data.get('game_id')
    
    if client_id:
        join_room(client_id)  # Join a room for this client
    
    if game_id:
        join_room(game_id)  # Join a room for this game

# Run the application
if __name__ == '__main__':
    # Make sure the data files exist
    if not os.path.exists('words.txt'):
        generate_words_file()
    
    if not os.path.exists('dilemmas.txt'):
        generate_dilemmas_file()
    
    # Initialize the database
    init_db()
    
    # Run the server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
