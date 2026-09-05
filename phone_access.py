"""Opt-in HTTPS access on one private LAN address, with a random password."""
import base64
import binascii
import hmac
import ipaddress
import json
import secrets
import ssl
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


def create_config(root, ip):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    address = ipaddress.ip_address(ip)
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError("Use this computer's private Wi-Fi IPv4 address")
    directory = Path(root) / "output" / "phone"
    directory.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Texas Investors local phone access")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5))
            .not_valid_after(now+timedelta(days=90))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    (directory / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (directory / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    config = {"ip": str(address), "port": 8766, "username": "investor", "password": secrets.token_urlsafe(18),
              "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(), "expires": (now+timedelta(days=90)).isoformat()}
    (directory / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def authorized(header, password):
    if not isinstance(header, str) or len(header) > 1024 or not header.startswith("Basic "):
        return False
    try:
        value = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeError):
        return False
    return hmac.compare_digest(value.encode(), ("investor:" + password).encode())


def start_phone(root, server_class, handler):
    directory = Path(root) / "output" / "phone"
    try:
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, {"enabled": False}
    address = ipaddress.ip_address(config["ip"])
    if not address.is_private or address.is_loopback or len(config["password"]) < 20:
        raise ValueError("Invalid phone access configuration")
    if datetime.fromisoformat(config["expires"]) <= datetime.now(timezone.utc):
        raise ValueError("Phone certificate expired; run setup_phone.py again")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(directory / "cert.pem", directory / "key.pem")
    server = server_class((config["ip"], config["port"]), handler)
    server.tls_context = context
    server.auth_token = config["password"]
    server.allowed_hosts = {f"{config['ip']}:{config['port']}"}
    server.url_scheme = "https"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, {"enabled": True, "url": f"https://{config['ip']}:{config['port']}",
                    "username": config["username"], "password": config["password"],
                    "fingerprint_sha256": config["fingerprint_sha256"], "expires": config["expires"]}
