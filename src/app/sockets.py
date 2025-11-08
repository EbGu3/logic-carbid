from flask import request, current_app
from flask_socketio import Namespace, emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token
from typing import Optional

# Mapeo liviano de sid -> user_id para refrescar auth
_SID_TO_UID = {}

def _extract_uid_from_token(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    try:
        decoded = decode_token(token)
        sub = decoded.get("sub")
        if sub is None:
            return None
        return int(sub)
    except Exception:
        return None

class AuctionNamespace(Namespace):
    def on_connect(self):
        # Token puede venir en auth (recomendado) o en query ?token=
        token = None
        auth = request.args.get("auth")  # poco común
        if isinstance(auth, dict):
            token = auth.get("token")
        if not token:
            token = request.args.get("token")
        # En Socket.IO v4 lo usual es 'auth' JSON desde el cliente, accedido vía environ:
        if not token and "auth" in request.args:
            token = request.args.get("auth", {}).get("token")
        # También soportamos el canal auth del handshake
        try:
            # Werkzeug pone datos del handshake en 'environ'
            auth_dict = request.environ.get("socketio", {}).get("auth") or {}
            token = token or (auth_dict.get("token") if isinstance(auth_dict, dict) else None)
        except Exception:
            pass

        uid = _extract_uid_from_token(token)
        if uid:
            join_room(f"user:{uid}")
            _SID_TO_UID[request.sid] = uid
        # Confirmamos conexión
        emit("connected", {"ok": True, "userId": uid}, to=request.sid)

    def on_disconnect(self):
        uid = _SID_TO_UID.pop(request.sid, None)
        if uid:
            # No es necesario leave_room explícito (se limpia al desconectar),
            # pero mantenemos consistencia si reusamos sid.
            try:
                leave_room(f"user:{uid}")
            except Exception:
                pass

    def on_auth_refresh(self, data):
        """Permite refrescar token post-login sin reconectar el socket."""
        token = (data or {}).get("token")
        new_uid = _extract_uid_from_token(token)
        old_uid = _SID_TO_UID.get(request.sid)
        if old_uid and old_uid != new_uid:
            try:
                leave_room(f"user:{old_uid}")
            except Exception:
                pass
        if new_uid:
            join_room(f"user:{new_uid}")
            _SID_TO_UID[request.sid] = new_uid
        emit("auth_refreshed", {"userId": new_uid}, to=request.sid)

    def on_subscribe_vehicle(self, data):
        vid = (data or {}).get("vehicleId")
        if not vid:
            return
        join_room(f"vehicle:{vid}")
        emit("subscribed", {"vehicleId": vid}, to=request.sid)

    def on_unsubscribe_vehicle(self, data):
        vid = (data or {}).get("vehicleId")
        if not vid:
            return
        leave_room(f"vehicle:{vid}")
        emit("unsubscribed", {"vehicleId": vid}, to=request.sid)

def register_socketio(socketio):
    socketio.on_namespace(AuctionNamespace("/rt"))
