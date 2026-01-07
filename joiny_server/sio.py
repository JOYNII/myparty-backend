import socketio

# create a Socket.IO server
# create a Socket.IO server
# create a Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[
    '*', 
    'https://estell-supereffective-selena.ngrok-free.dev',
    'http://localhost:3000',
])

class LocationNamespace(socketio.AsyncNamespace):
    async def on_connect(self, sid, environ):
        print(f"Location Client connected: {sid}")

    async def on_disconnect(self, sid):
        print(f"Location Client disconnected: {sid}")

    async def on_join_party(self, sid, data):
        """
        data expectation: { 'party_id': '123' }
        """
        party_id = data.get('party_id')
        if party_id:
            await self.enter_room(sid, f"party_{party_id}")
            await self.emit('response', {'message': f'Joined party {party_id} on location'}, room=sid)
            print(f"Client {sid} joined party_{party_id} on location")

    async def on_leave_party(self, sid, data):
        party_id = data.get('party_id')
        if party_id:
            await self.leave_room(sid, f"party_{party_id}")
            await self.emit('response', {'message': f'Left party {party_id} on location'}, room=sid)

    async def on_location_update(self, sid, data):
        """
        data expectation: 
        { 
          'party_id': '123',
          'user_id': 'user_1',
          'lat': 37.5665, 
          'lng': 126.9780 
        }
        """
        party_id = data.get('party_id')
        if party_id:
            # Broadcast to everyone in the party room EXCEPT the sender
            await self.emit('location_update', data, room=f"party_{party_id}", skip_sid=sid)


from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist

# Import models securely
# We assume django.setup() is already called in asgi.py before this module is imported
from core.models import Participant, ChatMessage, Event
from django.contrib.auth.models import User

class ChatNamespace(socketio.AsyncNamespace):
    async def on_connect(self, sid, environ):
        print(f"Chat Client connected: {sid}")

    async def on_disconnect(self, sid):
        print(f"Chat Client disconnected: {sid}")
    
    async def on_join_party(self, sid, data):
        party_id = data.get('party_id')
        user_id = data.get('user_id') # Expect user_id from frontend

        if party_id:
            await self.enter_room(sid, f"party_{party_id}")
            print(f"Client {sid} joined chat party_{party_id}")
            
            # Message history logic
            if user_id:
                try:
                    # Sync DB access wrapper
                    @sync_to_async
                    def get_chat_history():
                        try:
                            # 1. Get participant info specifically for joined_at
                            # We filter by user_id and party_id (event_id)
                            participant = Participant.objects.get(event_id=party_id, user_id=user_id)
                            joined_at = participant.joined_at
                            
                            # 2. Filter messages created after joined_at
                            msgs = ChatMessage.objects.filter(
                                event_id=party_id, 
                                created_at__gte=joined_at
                            ).order_by('created_at').select_related('sender')
                            
                            # 3. Serialize
                            history = []
                            for m in msgs:
                                history.append({
                                    'user_name': m.sender.username, # Or m.sender.first_name etc
                                    'message': m.message,
                                    'timestamp': m.created_at.isoformat(),
                                    'sid': 'history' # Marker
                                })
                            return history
                        except (Participant.DoesNotExist, ObjectDoesNotExist) as e:
                            print(f"Error fetching history: {e}")
                            return []

                    history = await get_chat_history()
                    if history:
                        await self.emit('chat_history', history, room=sid)
                        
                except Exception as e:
                    print(f"Unexpected error in on_join_party: {e}")

    async def on_leave_party(self, sid, data):
        party_id = data.get('party_id')
        if party_id:
            await self.leave_room(sid, f"party_{party_id}")
    
    async def on_chat_message(self, sid, data):
        """
        data: { 'party_id': '123', 'message': 'hello', 'user_name': 'Kim', 'user_id': '1' }
        """
        party_id = data.get('party_id')
        message = data.get('message')
        user_name = data.get('user_name')
        user_id = data.get('user_id')
        
        if party_id and message:
            # 1. Save to DB
            if user_id:
                try:
                    @sync_to_async
                    def save_message():
                        ChatMessage.objects.create(
                            event_id=party_id,
                            sender_id=user_id,
                            message=message
                        )
                    await save_message()
                except Exception as e:
                    print(f"Failed to save message: {e}")

            # 2. Broadcast to all
            await self.emit('chat_message', {
                'user_name': user_name,
                'message': message,
                'sid': sid,
                'timestamp': None # Frontend will add current time or we could send DB time
            }, room=f"party_{party_id}")

sio.register_namespace(LocationNamespace('/location'))
sio.register_namespace(ChatNamespace('/chat'))
