from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
import json

app = Flask(__name__)

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['github_webhooks']
collection = db['events']

def parse_webhook_data(payload):
    """Parse GitHub webhook payload and extract relevant information"""
    event_type = request.headers.get('X-GitHub-Event')
    
    if event_type == 'push':
        return {
            'event_type': 'push',
            'author': payload['pusher']['name'],
            'to_branch': payload['ref'].split('/')[-1],  # Extract branch name from refs/heads/branch
            'timestamp': datetime.utcnow(),
            'repository': payload['repository']['name']
        }
    
    elif event_type == 'pull_request':
        return {
            'event_type': 'pull_request',
            'author': payload['pull_request']['user']['login'],
            'from_branch': payload['pull_request']['head']['ref'],
            'to_branch': payload['pull_request']['base']['ref'],
            'timestamp': datetime.utcnow(),
            'repository': payload['repository']['name']
        }
    
    elif event_type == 'pull_request' and payload['action'] == 'closed' and payload['pull_request']['merged']:
        return {
            'event_type': 'merge',
            'author': payload['pull_request']['merged_by']['login'],
            'from_branch': payload['pull_request']['head']['ref'],
            'to_branch': payload['pull_request']['base']['ref'],
            'timestamp': datetime.utcnow(),
            'repository': payload['repository']['name']
        }
    
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle GitHub webhook events"""
    try:
        payload = request.get_json()
        
        if not payload:
            return jsonify({'error': 'No payload received'}), 400
        
        # Parse the webhook data
        event_data = parse_webhook_data(payload)
        
        if event_data:
            # Store in MongoDB
            collection.insert_one(event_data)
            print(f"Stored event: {event_data}")
            return jsonify({'status': 'success', 'message': 'Event stored successfully'}), 200
        else:
            return jsonify({'status': 'ignored', 'message': 'Event type not supported'}), 200
            
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/events')
def get_events():
    """API endpoint to get latest events"""
    try:
        # Get latest 50 events, sorted by timestamp descending
        events = list(collection.find().sort('timestamp', -1).limit(50))
        
        # Convert ObjectId to string for JSON serialization
        for event in events:
            event['_id'] = str(event['_id'])
            event['timestamp'] = event['timestamp'].isoformat()
        
        return jsonify(events)
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return jsonify({'error': 'Failed to fetch events'}), 500

def format_event_message(event):
    """Format event for display"""
    timestamp = datetime.fromisoformat(event['timestamp']).strftime('%d %B %Y - %I:%M %p UTC')
    
    if event['event_type'] == 'push':
        return f"{event['author']} pushed to {event['to_branch']} on {timestamp}"
    elif event['event_type'] == 'pull_request':
        return f"{event['author']} submitted a pull request from {event['from_branch']} to {event['to_branch']} on {timestamp}"
    elif event['event_type'] == 'merge':
        return f"{event['author']} merged branch {event['from_branch']} to {event['to_branch']} on {timestamp}"
    
    return "Unknown event type"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)