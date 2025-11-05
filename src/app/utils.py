from flask import jsonify

def api_error(message, status=400, **extra):
    payload = {"ok": False, "error": {"message": message, **extra}}
    return jsonify(payload), status

def api_ok(data=None, **extra):
    return jsonify({"ok": True, "data": data, **extra})
