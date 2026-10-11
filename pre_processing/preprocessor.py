from abc import ABC, abstractmethod

class PreprocessorStrategy(ABC):
    @abstractmethod
    def preprocess(self):
        pass

class Preprocessor:
    def __init__(self, preprocessStrategy : PreprocessorStrategy):
        self.preprocessStrategy = preprocessStrategy

    def preprocess(self):
        print(f"Preprocessing is starting...")
        self.preprocessStrategy.preprocess()
        print(f"Preprocessing is done.") 