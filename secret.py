import secrets

def generate_api_key(length=64):
    """Generate a secure random API key."""
    return secrets.token_hex(length // 2)  # Each byte is 2 hex characters

# Generate and print the API key
api_key = generate_api_key()
print("Generated API Key:", api_key)
