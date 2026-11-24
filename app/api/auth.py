from ldap3 import Connection, SUBTREE, Server
from ldap3.utils.conv import escape_filter_chars
from app.config import LDAP_HOST, LDAP_PASSWORD, LDAP_USER_BASE, LDAP_USER_DN


def authenticate_ldap(username: str, password: str):
    if not username or not password or not LDAP_PASSWORD:
        return None
    server = Server(LDAP_HOST, connect_timeout=5)
    admin = Connection(server, user=LDAP_USER_DN, password=LDAP_PASSWORD, receive_timeout=5)
    user_conn = None
    try:
        if not admin.bind():
            raise RuntimeError("Falha no bind da conta de serviço LDAP")
        search_filter = f"(&(objectClass=inetOrgPerson)(uid={escape_filter_chars(username)}))"
        if not admin.search(LDAP_USER_BASE, search_filter, SUBTREE, attributes=["uid", "cn", "memberOf"]):
            return None
        if len(admin.entries) != 1:
            return None
        entry = admin.entries[0]
        user_dn = entry.entry_dn
        user_conn = Connection(server, user=user_dn, password=password, receive_timeout=5)
        if not user_conn.bind():
            return None
        admin.search(f"ou=groups,{LDAP_USER_BASE.split(',', 1)[1]}",
                     f"(&(objectClass=groupOfNames)(member={user_dn}))", SUBTREE, attributes=["cn"])
        groups = [str(group.cn).lower() for group in admin.entries]
        role = "PROFESSOR" if "professores" in groups else "ESTUDANTE"
        return {"username": username, "role": role}
    finally:
        if user_conn:
            user_conn.unbind()
        admin.unbind()
