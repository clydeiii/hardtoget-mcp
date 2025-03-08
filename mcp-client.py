import requests
import json
import socketio
import sys
import os
import time
import random

class HardToGetClient:
    def __init__(self, server_url, model_name):
        """
        Initialize a Hard to Get client
        
        Args:
            server_url (str): The URL of the MCP server
            model_name (str): The LLM model name this client is using
        """
        self.server_url = server_url
        self.model_name = model_name
        self.client_id = None
        self.game_id = None
        self.role = None
        self.board = []
        self.current_round = 0
        self.key_word = None  # Only for Witness
        self.game_active = False
        
        # Initialize socketio client
        self.sio = socketio.Client()
        self.setup_socket_handlers()
    
    def setup_socket_handlers(self):
        """Set up socketio event handlers"""
        @self.sio.on('connect')
        def on_connect():
            print("Socket.IO connected")
            if self.client_id and self.game_id:
                self.sio.emit('join', {'client_id': self.client_id, 'game_id': self.game_id})
        
        @self.sio.on('game_started')
        def on_game_started(data):
            print(f"Game started: {data['game_id']}")
            self.game_active = True
        
        @self.sio.on('witness_turn')
        def on_witness_turn(data):
            if self.role == 'Witness':
                self.handle_witness_turn(data)
        
        @self.sio.on('detective_turn')
        def on_detective_turn(data):
            if self.role == 'Detective':
                self.handle_detective_turn(data)
        
        @self.sio.on('game_ended')
        def on_game_ended(data):
            self.handle_game_ended(data)
    
    def register(self):
        """Register with the MCP server and get a client ID"""
        response = requests.post(
            f"{self.server_url}/register",
            json={"model_name": self.model_name}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.client_id = data['client_id']
            print(f"Registered with client ID: {self.client_id}")
            return self.client_id
        else:
            print(f"Registration failed: {response.text}")
            return None
    
    def join_game(self, preferred_role=None):
        """Join a game with optional role preference"""
        if not self.client_id:
            print("Must register before joining a game")
            return False
        
        response = requests.post(
            f"{self.server_url}/join_game",
            json={
                "client_id": self.client_id,
                "preferred_role": preferred_role
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.game_id = data['game_id']
            self.role = data['role']
            self.board = data.get('board', [])
            
            print(f"Joined game {self.game_id} as {self.role}")
            print(f"Game board: {self.board}")
            
            # Connect to socket.io server
            try:
                self.sio.connect(self.server_url)
                self.sio.emit('join', {'client_id': self.client_id, 'game_id': self.game_id})
            except Exception as e:
                print(f"Socket.IO connection error: {e}")
            
            return True
        else:
            print(f"Failed to join game: {response.text}")
            return False
    
    def handle_witness_turn(self, data):
        """Handle witness turn notification"""
        self.key_word = data['key_word']
        self.current_round = data['round']
        dilemma = data['dilemma']
        
        print(f"\n--- Round {self.current_round} ---")
        print(f"You are the Witness. The key word is: {self.key_word}")
        print(f"Dilemma: {dilemma[0]} vs {dilemma[1]}")
        
        # In a real implementation, the LLM would make this decision
        # For this demo, we'll hardcode a simple algorithm
        choice_index = self.choose_dilemma_side(self.key_word, dilemma)
        choice = dilemma[choice_index]
        
        print(f"You chose: {choice}")
        
        # Send the choice to the server
        self.submit_witness_choice(choice)
    
    def choose_dilemma_side(self, key_word, dilemma):
        """
        Use a very simple algorithm to choose a dilemma side
        In a real implementation, the LLM would make this decision
        """
        # This is a placeholder - in reality, an LLM would make this choice
        # For simplicity, we'll make a "random" but deterministic choice
        # based on the hash of the key word and dilemma
        combined = key_word + dilemma[0] + dilemma[1]
        hash_value = sum(ord(c) for c in combined)
        return hash_value % 2
    
    def submit_witness_choice(self, dilemma_choice):
        """Submit the witness's dilemma choice to the server"""
        response = requests.post(
            f"{self.server_url}/witness_choice",
            json={
                "game_id": self.game_id,
                "client_id": self.client_id,
                "dilemma_choice": dilemma_choice
            }
        )
        
        if response.status_code != 200:
            print(f"Error submitting witness choice: {response.text}")
    
    def handle_detective_turn(self, data):
        """Handle detective turn notification"""
        self.current_round = data['round']
        dilemma = data['dilemma']
        witness_choice = data['witness_choice']
        
        print(f"\n--- Round {self.current_round} ---")
        print(f"You are the Detective.")
        print(f"Dilemma: {dilemma[0]} vs {dilemma[1]}")
        print(f"The Witness chose: {witness_choice}")
        print(f"Current board: {self.board}")
        
        # In a real implementation, the LLM would make this decision
        # For this demo, we'll implement a simple algorithm
        eliminated = self.choose_eliminations(dilemma, witness_choice)
        
        print(f"You've chosen to eliminate: {eliminated}")
        
        # Send the eliminations to the server
        self.submit_detective_choice(eliminated)
    
    def choose_eliminations(self, dilemma, witness_choice):
        """
        Choose words to eliminate
        In a real implementation, the LLM would make this decision
        """
        # This is a placeholder - in reality, an LLM would make this choice
        # For this demo, we'll eliminate 1-3 random words
        
        # Find the opposite choice
        opposite_choice = dilemma[0] if dilemma[1] == witness_choice else dilemma[1]
        
        # Determine how many words to eliminate (between 1 and 3)
        num_to_eliminate = min(len(self.board) - 1, random.randint(1, 3))
        
        # Create a simple scoring system based on word similarity to the opposite choice
        scored_words = []
        for word in self.board:
            # In a real implementation, an LLM would determine relevance
            # Here we'll use a simple string-based approach
            similarity = self.simple_similarity(word, opposite_choice)
            scored_words.append((word, similarity))
        
        # Sort by similarity (higher means more similar to opposite choice)
        scored_words.sort(key=lambda x: x[1], reverse=True)
        
        # Choose the top N words to eliminate
        to_eliminate = [word for word, score in scored_words[:num_to_eliminate]]
        
        # Update our local board
        self.board = [word for word in self.board if word not in to_eliminate]
        
        return to_eliminate
    
    def simple_similarity(self, word, term):
        """Very simple string similarity - would be replaced by LLM judgment"""
        # Count common characters
        common_chars = set(word.lower()) & set(term.lower())
        return len(common_chars) / max(len(set(word.lower())), len(set(term.lower())))