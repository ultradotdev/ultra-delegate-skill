"""Opt-in TypeSafe HTTP transport and OS credentials; no worker execution."""
from __future__ import annotations

import json
import math
import multiprocessing
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
REQUEST_LIMIT = 24 * 1024
RESPONSE_LIMIT = 256 * 1024
DEADLINE = 20.0
SERVICE = "ultra-delegation.typesafe"
SECURE_BACKENDS = {
    ("keyring.backends.macOS", "Keyring"),
    ("keyring.backends.Windows", "WinVaultKeyring"),
    ("keyring.backends.SecretService", "Keyring"),
    ("keyring.backends.kwallet", "DBusKeyring"),
    ("keyring.backends.kwallet", "DBusKeyringKWallet4"),
    ("keyring.backends.kwallet", "DBusKeyringKWallet5"),
}


class ServiceError(Exception):
    """Only fixed codes cross the transport boundary."""
    def __init__(self, code, attempts=0):
        self.code, self.attempts = code, attempts
        super().__init__(code)


def secure_backend():
    try:
        import keyring
        backend = keyring.get_keyring()
        if (type(backend).__module__, type(backend).__name__) not in SECURE_BACKENDS:
            raise ServiceError("unsupported-credential-store")
        return backend
    except ServiceError:
        raise
    except Exception:
        raise ServiceError("credential-store-unavailable") from None


def credential(ref, environ=None, service=SERVICE):
    env = os.environ if environ is None else environ
    value = env.get("TYPESAFE_API_KEY")
    if value:
        return value, "environment"
    try:
        value = secure_backend().get_password(service, ref)
    except ServiceError:
        raise
    except Exception:
        raise ServiceError("credential-store-unavailable") from None
    if not value:
        raise ServiceError("missing-credential")
    return value, "os-store"


def auth(action, ref, model, service=SERVICE):
    # Credential lifecycle belongs to the user, never to this adapter.
    if action not in ("status", "check"):
        raise ServiceError("unsupported-auth-action")
    try:
        key, source = credential(ref, service=service)
    except ServiceError as e:
        if action == "status": return {"configured": False, "verified": False, "reason": e.code}
        raise
    if action == "status": return {"configured": True, "source": source, "verified": False}
    payload = {"model": model, "state": "Synthetic credential check: the word is apple.",
               "questions": {"check": {"type": "noul", "instructions": "Is the word apple?"}}}
    result, meta = request(payload, key)
    validate_response(payload, result)
    return {"configured": True, "source": source, "verified": True, **meta}


def encoded_payload(payload):
    try: data = json.dumps(payload, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (ValueError, TypeError): raise ServiceError("invalid-request") from None
    if len(data) > REQUEST_LIMIT: raise ServiceError("request-too-large")
    return data


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ServiceError("redirect-refused")


def _request_loop(data, key, deadline, opener=None, clock=time.monotonic, sleep=time.sleep, on_attempt=None):
    opener = opener or urllib.request.build_opener(NoRedirect())
    for attempt in (1, 2):
        remaining = deadline - clock()
        if remaining <= 0: raise ServiceError("deadline-exceeded", attempt - 1)
        if on_attempt: on_attempt(attempt)
        req = urllib.request.Request(ENDPOINT, data=data, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        try:
            with opener.open(req, timeout=remaining) as response:
                body = response.read(RESPONSE_LIMIT + 1)
            if clock() > deadline: raise ServiceError("deadline-exceeded", attempt)
            if len(body) > RESPONSE_LIMIT: raise ServiceError("response-too-large", attempt)
            try: parsed = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError): raise ServiceError("invalid-response", attempt) from None
            return parsed, attempt
        except urllib.error.HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After", "0.25") if error.headers else "0.25"
            error.close()
            if status in (401, 403): raise ServiceError("authentication-failed", attempt) from None
            if status == 422: raise ServiceError("request-rejected", attempt) from None
            if 300 <= status < 400: raise ServiceError("redirect-refused", attempt) from None
            if status not in (429, 500, 502, 503, 504, 529) or attempt == 2:
                raise ServiceError("service-unavailable", attempt) from None
            try: delay = max(0.25, float(retry_after))
            except ValueError: delay = 0.25
            if not math.isfinite(delay) or delay >= deadline - clock():
                raise ServiceError("deadline-exceeded", attempt) from None
            sleep(delay)
        except ServiceError as error:
            raise ServiceError(error.code, attempt) from None
        except (OSError, ValueError):
            if attempt == 2: raise ServiceError("connection-failed", attempt) from None
            if deadline - clock() <= 0.25: raise ServiceError("deadline-exceeded", attempt) from None
            sleep(0.25)
    raise ServiceError("service-unavailable", 2)


def _worker(connection, data, key, deadline):
    try:
        result, attempts = _request_loop(data, key, deadline, on_attempt=lambda n: connection.send(("attempt", n)))
        connection.send(("result", True, result, attempts))
    except ServiceError as e:
        connection.send(("result", False, e.code, e.attempts))
    except Exception:
        connection.send(("result", False, "transport-failed", 0))
    finally:
        connection.close()


def request(payload, key):
    data = encoded_payload(payload)
    started = time.monotonic()
    # A child process bounds DNS, TLS, retries and slow streaming together. No key
    # is passed through argv, a file, or the child's environment.
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(sender, data, key, started + DEADLINE), daemon=True)
    try:
        process.start()
        sender.close()
        attempts = 0
        while True:
            if not receiver.poll(max(0, DEADLINE - 0.5 - (time.monotonic() - started))):
                raise ServiceError("deadline-exceeded", attempts)
            try: message = receiver.recv()
            except EOFError: raise ServiceError("transport-failed", attempts) from None
            if message[0] == "attempt":
                attempts = message[1]
                continue
            _, ok, value, reported_attempts = message
            attempts = max(attempts, reported_attempts)
            if not ok: raise ServiceError(value, attempts)
            return value, {"attempts": attempts, "latency_ms": (time.monotonic() - started) * 1000}
    except ServiceError:
        raise
    except Exception:
        raise ServiceError("transport-failed") from None
    finally:
        receiver.close()
        sender.close()
        if process.pid:
            if process.is_alive(): process.terminate()
            process.join(timeout=max(0, min(0.25, DEADLINE - (time.monotonic() - started))))
            if process.is_alive():
                process.kill()
                process.join(timeout=max(0, DEADLINE - (time.monotonic() - started)))


def number(value, low=0, high=1):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and low <= value <= high


def validate_response(payload, result):
    def bad(): raise ServiceError("invalid-response")
    if not isinstance(result, dict) or result.get("model") != payload["model"]: bad()
    answers = result.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(payload["questions"]): bad()
    usage = result.get("usage")
    if not isinstance(usage, dict): bad()
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")): bad()
    clean = {}
    for key, q in payload["questions"].items():
        a = answers[key]
        if not isinstance(a, dict) or a.get("type") != q["type"]: bad()
        if q["type"] == "noul":
            if not number(a.get("noul")): bad()
            clean[key] = {"yes": a["noul"]}
            continue
        options = set(q["criteria"]) if q["type"] == "choice" else {str(i) for i in range(len(q["criteria"]))}
        probs = a.get("probabilities")
        if not isinstance(probs, dict) or set(probs) != options or any(not number(v) for v in probs.values()): bad()
        if abs(sum(probs.values()) - 1) > 1e-5 or not number(a.get("confidence")): bad()
        if q["type"] == "choice":
            if a.get("choice") not in options or probs[a["choice"]] < max(probs.values()): bad()
        else:
            if a.get("legend") != {str(i): s for i, s in enumerate(q["criteria"])}: bad()
            expected = sum(int(k) * v for k, v in probs.items())
            if not number(a.get("score"), 0, len(options) - 1) or abs(a["score"] - expected) > 1e-5: bad()
        clean[key] = probs
    return clean, {k: usage[k] for k in ("input_tokens", "output_tokens")}
