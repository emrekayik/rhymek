from rhymek.nlp.cleaner import process_dataset


process_dataset("data/songs.jsonl", "data/lyrics_clean.parquet")