import pickle

data = pickle.loads(b"something")  # Flagged by Bandit
