import os

KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:replace_with_a_long_random_redis_password@redis:6379/0")
ELASTIC_URL = os.getenv("ELASTIC_URL", "http://elasticsearch:9200")
LDAP_HOST = os.getenv("LDAP_HOST", "ldap://openldap:389")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=example,dc=org")
LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", f"ou=people,{LDAP_BASE_DN}")
LDAP_USER_DN = os.getenv("LDAP_USER_DN", f"cn=admin,{LDAP_BASE_DN}")
LDAP_PASSWORD = os.getenv("LDAP_PASSWORD", "")
API_SECRET = os.getenv("API_SECRET", "")
API_TOKEN_TTL = int(os.getenv("API_TOKEN_TTL", "3600"))
API_ALLOWED_ORIGINS = [x.strip() for x in os.getenv("API_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
