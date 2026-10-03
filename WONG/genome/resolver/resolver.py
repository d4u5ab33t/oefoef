# Datei: genome/resolver/resolver.py

class GenomeResolver:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def resolve(self, shot_ast):
        print("Resolver aktiv.")
        return shot_ast