import re

import re

def is_valid_username(username):
    if not username:
        return False, "Username cannot be empty."
    
    if len(username) < 4:
        return False, "Username must be at least 4 characters long."
    
    if len(username) > 20:
        return False, "Username cannot exceed 20 characters."
    
    # Must contain at least one letter (a-z)
    if not re.search(r"[a-z]", username):
        return False, "Username must contain at least one lowercase letter."
    
    # Only lowercase letters, numbers, and underscores allowed
    if not re.fullmatch(r"[a-z0-9_]+", username):
        return False, "Username may contain only lowercase letters, numbers, and underscores."
    
    if username.startswith("_") or username.endswith("_"):
        return False, "Username cannot start or end with an underscore."
    
    if "__" in username:
        return False, "Username cannot contain consecutive underscores."
    
    return True, None


def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-]", password):
        return False, "Password must contain at least one special character."

    return True, None
