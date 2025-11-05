import json
from queue import Queue
from flask import Response, stream_with_context

# Canal -> lista de colas (una por cliente conectado)
CHANNELS = {}

def publish(channel: str, event: str, data: dict):
    payload = f"event: {event}\n" + f"data: {json.dumps(data)}\n\n"
    queues = CHANNELS.get(channel, [])
    for q in list(queues):
        try:
            q.put_nowait(payload)
        except Exception:
            pass

def stream(channel: str):
    q = Queue()
    CHANNELS.setdefault(channel, []).append(q)
    try:
        # Primer “ping” para abrir
        yield "event: ping\ndata: {}\n\n"
        while True:
            msg = q.get()  # bloqueante
            yield msg
    except GeneratorExit:
        pass
    finally:
        CHANNELS[channel].remove(q)

def sse_response(generator):
    return Response(
        stream_with_context(generator),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
