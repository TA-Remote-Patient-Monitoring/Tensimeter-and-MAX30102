import secrets

token = secrets.token_hex(32)
print(token, "silahkan paste di file .env sebagai SECRET_KEY")