import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'joiny_server.settings')
django.setup()

from core.models import Event
from core.serializers import EventSerializer

try:
    events = Event.objects.all()
    for event in events:
        print(f"Serializing event: {event.id} - {event.name}")
        serializer = EventSerializer(event)
        print(serializer.data)
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
