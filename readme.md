# Hard to Get - MCP Server

This is a Model Context Protocol (MCP) server that allows LLMs to play the cooperative word association board game "Hard to Get" with each other. The server manages game state, coordinates player turns, and tracks game results.

## Overview

Hard to Get is a cooperative word association game where two players work together:
- The **Witness** knows the secret "key word" and must provide clues
- The **Detective** must eliminate words based on the Witness's clues to find the key word

The game lasts 5 rounds, and each round:
1. The Witness is given a dilemma with two options (e.g., "Hot vs. Cold")
2. The Witness chooses which option better matches the key word
3. The Detective eliminates at least one word from the board that doesn't match the chosen option
4. The game continues until all non-key words are eliminated, the key word is eliminated, or 5 rounds are completed

## Requirements

- Python 3.7+
- Flask
- Flask-SocketIO
- SQLite3
- Python-SocketIO client (for the client implementation)

You can install the dependencies with:

```bash
pip install flask flask-socketio python-socketio requests
```

## Project Structure

```
├── server.py           # MCP server implementation
├── client.py           # Client implementation for LLMs
├── words.txt           # 500 words/phrases for the game board
├── dilemmas.txt        # 150 dilemmas for the Witness to evaluate
├── hard_to_get.db      # SQLite database (created automatically)
└── README.md           # This file
```

## Running the Server

1. Make sure you have all dependencies installed
2. Run the server:

```bash
python server.py
```

The server will start on http://localhost:5000

## Client API

Clients (LLMs) interact with the server using the following API endpoints:

### 1. Register a new client

```
POST /register
Body: {"model_name": "model-name-string"}
Response: {"client_id": "uuid", "status": "registered"}
```

### 2. Join a game

```
POST /join_game
Body: {"client_id": "uuid", "preferred_role": "Witness|Detective|null"}
Response: {
  "game_id": "uuid",
  "role": "Witness|Detective",
  "game_ready": true|false,
  "board": ["word1", "word2", ...]
}
```

### 3. Submit Witness choice

```
POST /witness_choice
Body: {
  "game_id": "uuid",
  "client_id": "uuid",
  "dilemma_choice": "selected-dilemma-option"
}
Response: {"status": "success"}
```

### 4. Submit Detective choice

```
POST /detective_choice
Body: {
  "game_id": "uuid",
  "client_id": "uuid",
  "eliminated_words": ["word1", "word2", ...]
}
Response: {
  "status": "success",
  "game_over": true|false,
  "win": true|false,
  "remaining_words": ["word1", "word2", ...],
  "key_word_eliminated": true|false
}
```

## Real-time Notifications

The server uses Socket.IO to notify clients about game events:

1. Connect to the Socket.IO server and join the game and client rooms:
```javascript
socket.emit('join', {'client_id': clientId, 'game_id': gameId});
```

2. Listen for events:
- `game_started`: Notifies when a game has started
- `witness_turn`: Tells the Witness it's their turn, provides the key word and dilemma
- `detective_turn`: Tells the Detective it's their turn, provides the dilemma and Witness's choice
- `game_ended`: Notifies both players of game end and result

## Database Schema

The server maintains three tables:

### 1. clients
- `uuid`: Unique client identifier
- `model_name`: String identifying the LLM model
- `status`: Client status (available, searching, in_game)

### 2. games
- `id`: Unique game identifier
- `witness_uuid`: UUID of the Witness client
- `detective_uuid`: UUID of the Detective client
- `status`: Game status (pending, active, completed)
- `key_word`: The secret word the Detectives must find
- `current_round`: Current game round (1-5)
- `board`: JSON string of words currently on the board

### 3. results
- `game_id`: Game identifier
- `witness_uuid`: UUID of the Witness client
- `witness_model`: Model name of the Witness
- `detective_uuid`: UUID of the Detective client
- `detective_model`: Model name of the Detective
- `result`: Game result (win or loss)

## Running the Client

A sample client implementation is provided in `client.py`. To run it:

```bash
python client.py http://localhost:5000 "model-name" [role]
```

Arguments:
- `http://localhost:5000`: Server URL
- `model-name`: LLM model name (e.g., "gpt-4", "claude-3")
- `role` (optional): Preferred role ("Witness" or "Detective")

The sample client shows how to connect to the server, interact with the API, and handle Socket.IO events. In a real implementation, the LLM would make the game decisions based on its language model capabilities.

## Implementing LLM Clients

To create a real LLM client for this game:

1. Replace the `choose_dilemma_side` method with LLM-based decision making to evaluate which side of the dilemma better matches the key word
2. Replace the `choose_eliminations` method with LLM-based decision making to determine which words to eliminate based on the dilemma and Witness's choice

The current client implementation includes placeholder logic that should be replaced with actual LLM calls in a production system.

## Generating Data Files

The server will automatically generate `words.txt` and `dilemmas.txt` if they don't exist. However, you can customize these files to include your own words and dilemmas.

- `words.txt`: One word/phrase per line
- `dilemmas.txt`: One dilemma per line, with options separated by comma (e.g., "Hot,Cold")
