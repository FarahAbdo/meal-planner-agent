import json
import os
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys

# the API key
MODEL_STUDIO_API_KEY = os.environ.get('MODEL_STUDIO_API_KEY')

# Debug: Check if API key is set
if not MODEL_STUDIO_API_KEY:
    print("WARNING: No API key found in environment variables DASHSCOPE_API_KEY or MODEL_STUDIO_API_KEY")
else:
    print(f"API key found: {MODEL_STUDIO_API_KEY[:10]}...{MODEL_STUDIO_API_KEY[-4:]}")  # Show first 10 and last 4 chars

def handler(event, context):
    """
    Function Compute entry point - this is what gets called when the function runs
    """
    try:
        # Parse the incoming event
        print(f"Received event: {json.dumps(event)}")
        
        # Get the HTTP method
        http_method = event.get('httpMethod', 'GET')
        
        # Debug: Print all event keys
        print(f"Event keys: {list(event.keys())}")
        print(f"HTTP Method: {http_method}")
        
        if http_method == 'POST':
            # Get the request body - try multiple possible locations
            body_str = None
            
            # Method 1: Direct body field
            if 'body' in event:
                body_str = event['body']
                print(f"Found body in event.body: {body_str}")
            
            # Method 2: Check if it's in a different field
            elif 'data' in event:
                body_str = event['data']
                print(f"Found body in event.data: {body_str}")
            
            # Method 3: The entire event might be the body
            else:
                print("No body field found, trying entire event as body")
                body_str = json.dumps(event)
            
            print(f"Raw body string: {body_str}")
            print(f"Body string type: {type(body_str)}")
            
            # Parse the JSON body
            try:
                if isinstance(body_str, str):
                    body = json.loads(body_str) if body_str else {}
                elif isinstance(body_str, dict):
                    body = body_str
                else:
                    body = {}
                print(f"Parsed body: {body}")
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                # Try parsing the event directly
                body = event
                print(f"Using event directly as body: {body}")
            
            # Try to extract message from various possible locations
            user_message = ''
            user_id = 'anonymous'
            
            # Try different ways to get the message
            if 'message' in body:
                user_message = body['message']
                user_id = body.get('user_id', 'anonymous')
                print(f"Found message directly in body: {user_message}")
            elif 'body' in body and isinstance(body['body'], str):
                # Maybe it's double-nested
                try:
                    inner_body = json.loads(body['body'])
                    user_message = inner_body.get('message', '')
                    user_id = inner_body.get('user_id', 'anonymous')
                    print(f"Found message in nested body: {user_message}")
                except:
                    pass
            
            print(f"Final extracted - message: '{user_message}', user_id: '{user_id}'")
            
            # Generate response
            if user_message.strip():
                print(f"Processing user message: {user_message}")
                response = get_ai_response(user_message, user_id)
            else:
                print("Still no message found - showing debug info")
                response = f"[DEBUG] Could not extract message. Event structure: {json.dumps(event, indent=2)[:500]}..."
            
            # Create the response
            response_data = {
                'response': response,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps(response_data)
            }
            
        elif http_method == 'GET':
            # Handle GET requests - return a simple status
            response_data = {
                'status': 'AI Meal Planner is running!',
                'message': 'Send a POST request with {"message": "your message", "user_id": "optional"} to chat with me.',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response_data)
            }
            
        elif http_method == 'OPTIONS':
            # Handle OPTIONS requests for CORS
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': ''
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        # If something goes wrong, return an error message
        error_response = {
            'response': f"Sorry, I encountered an error: {str(e)}",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_response)
        }

def get_ai_response(user_message, user_id):
    """
    Generate AI response using Alibaba Cloud Model Studio
    """
    try:
        # Check if we have an API key
        if not MODEL_STUDIO_API_KEY:
            return "I'm having trouble connecting to the AI service. Please check that the API key is configured correctly."
        
        # Create a meal planning prompt
        system_prompt = """You are a helpful AI meal planning assistant. You help users plan their meals based on their dietary preferences, restrictions, and goals. 

Key guidelines:
- Ask about dietary restrictions (vegetarian, vegan, gluten-free, etc.)
- Consider nutritional balance
- Suggest specific meals and recipes
- Be encouraging and helpful
- Keep responses concise but informative

User preferences to remember:
- Dietary restrictions
- Cuisine preferences  
- Cooking skill level
- Time constraints"""

        # Try the international endpoint first
        url = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        
        headers = {
            "Authorization": f"Bearer {MODEL_STUDIO_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "qwen-turbo",  # Using Qwen-Turbo model
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": user_message
                    }
                ]
            },
            "parameters": {
                "max_tokens": 500,
                "temperature": 0.7
            }
        }
        
        print(f"Making API request to: {url}")
        print(f"Using API key: {MODEL_STUDIO_API_KEY[:10]}...{MODEL_STUDIO_API_KEY[-4:]}")
        
        # Make the API call
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"API Response status: {response.status_code}")
        print(f"API Response: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Extract the generated text
            if 'output' in response_data and 'text' in response_data['output']:
                ai_response = response_data['output']['text']
                return ai_response
            else:
                return f"I received your message about meal planning! Here's a personalized suggestion: For a healthy vegetarian lunch, try a quinoa bowl with roasted vegetables, chickpeas, and tahini dressing. It's nutritious and delicious!"
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            
            # Try the regular endpoint if international fails
            if "dashscope-intl" in url:
                print("Trying regular DashScope endpoint...")
                url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
                response = requests.post(url, headers=headers, json=data, timeout=30)
                print(f"Regular endpoint response: {response.status_code} - {response.text}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    if 'output' in response_data and 'text' in response_data['output']:
                        return response_data['output']['text']
            
            # Fallback response with helpful information
            if response.status_code == 401:
                return f"I'm having trouble with my API key. Please check that it's correctly configured. Meanwhile, here's a suggestion: For a healthy vegetarian lunch, try a colorful salad with quinoa, roasted vegetables, and protein like chickpeas or tofu!"
            else:
                return f"I'm having some technical difficulties right now, but I'd love to help you plan healthy meals! For a vegetarian lunch, I suggest a nutrient-packed bowl with quinoa, fresh vegetables, and a protein source."
            
    except Exception as e:
        print(f"Error in get_ai_response: {str(e)}")
        # Fallback response
        return f"I received your message about meal planning. I'm having some technical difficulties right now, but here's a great suggestion: Try a Mediterranean-style quinoa bowl with chickpeas, cucumber, tomatoes, and olive oil dressing for a healthy vegetarian lunch!"

# Keep the HTTP server code for local testing
class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests for local testing"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode('utf-8'))
            
            # Simulate the Function Compute event structure
            event = {
                'httpMethod': 'POST',
                'body': json.dumps(body)
            }
            
            # Call the handler function
            result = handler(event, {})
            
            # Send response
            self.send_response(result['statusCode'])
            for header, value in result.get('headers', {}).items():
                self.send_header(header, value)
            self.end_headers()
            self.wfile.write(result['body'].encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {'error': str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests for local testing"""
        event = {'httpMethod': 'GET'}
        result = handler(event, {})
        
        self.send_response(result['statusCode'])
        for header, value in result.get('headers', {}).items():
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(result['body'].encode('utf-8'))

def start_server():
    """Start the HTTP server for local testing"""
    port = int(os.environ.get('FC_SERVER_PORT', 9000))
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    print(f"Starting local test server on port {port}")
    server.serve_forever()

if __name__ == '__main__':
    # For local testing
    start_server()
