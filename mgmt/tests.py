import uuid

import pytest
from django.urls import reverse
from ldap3 import Connection, MOCK_SYNC, Server, OFFLINE_DS389_1_3_3

from mgmt.forms import UserForm
from mgmt.users import get_all_users, create_user, get_user


@pytest.fixture(scope="function")
def auth_client(client, django_user_model):
    username = "citc"
    password = "bar"
    django_user_model.objects.create_user(username=username, password=password)
    client.login(username=username, password=password)
    return client


@pytest.fixture(scope="function")
def conn():
    id = str(uuid.uuid4())
    print("Creating new connection", id)
    server = Server(id, get_info=OFFLINE_DS389_1_3_3)
    conn = Connection(server, user='cn=Directory Manager', password='my_password', client_strategy=MOCK_SYNC, auto_bind=True)
    return conn


def test_connection(conn):
    users = get_all_users(conn)
    assert len(users) == 0


def test_create_user(conn, mocker):
    mocker.patch('subprocess.run')
    create_user(conn, 'matt', 'Matt', 'Williams', "https://github.com/milliams.keys")
    users = get_all_users(conn)
    assert len(users) == 1
    assert users[0].sn == "Williams"
    assert users[0].uidNumber == 10001


def test_get_user(conn):
    with pytest.raises(LookupError):
        get_user(conn, "matt")


def test_duplicate_user(conn, mocker):
    mocker.patch('subprocess.run')
    create_user(conn, 'matt', "", "", "")
    with pytest.raises(RuntimeError):
        create_user(conn, 'matt', "", "", "")


def test_create_user_get_uid(conn, mocker):
    mocker.patch('subprocess.run')
    create_user(conn, 'matt1', 'Matt', 'Williams', "https://github.com/milliams.keys")
    create_user(conn, 'matt2', 'Matt', 'Williams', "https://github.com/milliams.keys")
    users = get_all_users(conn)
    assert len(users) == 2
    assert get_user(conn, "matt1").uidNumber == 10001
    assert get_user(conn, "matt2").uidNumber == 10002


def test_create_user_different_key_types(conn, mocker):
    run = mocker.patch('subprocess.run')
    create_user(conn, 'matt', 'Matt', 'Williams', "https://github.com/milliams.keys")
    for call in run.call_args_list:
        if "input" in call.kwargs:
            assert isinstance(call.kwargs["input"], bytes)


@pytest.mark.parametrize("keys", [
    "https://github.com/milliams.keys",
    "ssh-rsa AAAAB3NzaC1yc2 matt@home",
    "ssh-rsa AAAAB3NzaC1yc2 matt@home\nssh-rsa AAAAB3NzaC1yc2 matt@home",
    "ssh-ed25519 AAAAC3NzaC1lZD matt@home",
])
def test_validate_form(conn, keys, mocker):
    mocker.patch("mgmt.users.connection", lambda: conn)
    form = UserForm({"uid": "foo", "given_name": "foo", "sn": "foo", "keys": keys})
    assert form.is_valid(), form.errors


def test_form_create_user(auth_client, conn, mocker):
    mocker.patch("mgmt.users.connection", lambda: conn)
    m = mocker.patch("mgmt.users.create_user")
    auth_client.post(reverse('add_user'), {"uid": "foo", "given_name": "foo", "sn": "foo", "keys": "http://foo"})
    assert m.called_once_with("foo", "foo", "foo", "http://foo")


def test_form_duplicate_user(auth_client, conn, mocker):
    mocker.patch("mgmt.users.connection", lambda: conn)
    mocker.patch('subprocess.run')
    create_user(conn, "foo", "", "", "")
    r = auth_client.post(reverse('add_user'), {"uid": "foo", "given_name": "foo", "sn": "foo", "keys": "http://foo"})
    assert r.status_code == 200
    assert '<div class="invalid-feedback">User already exists</div>' in r.content.decode()
