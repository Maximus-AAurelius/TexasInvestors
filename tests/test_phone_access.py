import base64
import http.client
import ssl
from pathlib import Path
import pytest
from app import LocalAppServer, AppHandler
from phone_access import create_config, authorized


def test_password_comparison_and_bad_inputs():
    token="test-password-only-123456"
    header="Basic "+base64.b64encode(("investor:"+token).encode()).decode()
    assert authorized(header,token)
    assert not authorized(header,token+'x')
    assert not authorized('Basic not base64',token)
    assert not authorized(None,token)


def test_config_private_ip_and_cert(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    config=create_config(tmp_path,'192.168.1.67')
    assert len(config['password'])>=20
    cert=x509.load_pem_x509_certificate((tmp_path/'output/phone/cert.pem').read_bytes())
    assert cert.fingerprint(hashes.SHA256()).hex()==config['fingerprint_sha256']
    with pytest.raises(ValueError):
        create_config(tmp_path,'8.8.8.8')


def test_https_requires_auth_and_blocks_wrong_origin(tmp_path):
    import threading
    config=create_config(tmp_path,'192.168.1.67')
    server=LocalAppServer(('127.0.0.1',0),AppHandler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path/'output/phone/cert.pem',tmp_path/'output/phone/key.pem')
    server.tls_context=context;server.auth_token=config['password'];server.url_scheme='https'
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def fetch(headers):
        client=http.client.HTTPSConnection('127.0.0.1',server.server_port,context=ssl._create_unverified_context(),timeout=5)
        client.request('GET','/api/health',headers=headers)
        response=client.getresponse();status=response.status;response.read();client.close();return status
    try:
        assert fetch({})==401
        headers={'Authorization':'Basic '+base64.b64encode(('investor:'+config['password']).encode()).decode()}
        assert fetch(headers)==200
        assert fetch({**headers,'Origin':'https://attacker.example'})==403
        assert fetch({**headers,'Origin':f'https://127.0.0.1:{server.server_port}'})==200
    finally:
        server.shutdown();server.server_close();thread.join()
