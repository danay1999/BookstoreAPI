import os
import secrets

# The app refuses to start without a strong secret, so give the tests a random one.
os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(32))
