import os
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import torch

class ModelCache:
    _instance = None
    _sentence_model = None
    _sentiment_pipeline = None
    _emotion_pipeline = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelCache, cls).__new__(cls)
        return cls._instance

    _sentence_model_high = None
    _sentence_model_fast = None

    def get_sentence_model(self, quality="high"):
        device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
        if quality == "fast":
            if self._sentence_model_fast is None:
                self._sentence_model_fast = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', device=device)
            return self._sentence_model_fast
        else:
            if self._sentence_model_high is None:
                self._sentence_model_high = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2', device=device)
            return self._sentence_model_high

    @property
    def sentiment_pipeline(self):
        if self._sentiment_pipeline is None:
            device = 0 if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else -1
            self._sentiment_pipeline = pipeline(
                "sentiment-analysis", 
                model="cointegrated/rubert-tiny-sentiment-balanced", 
                device=device
            )
        return self._sentiment_pipeline

    @property
    def emotion_pipeline(self):
        if self._emotion_pipeline is None:
            device = 0 if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else -1
            self._emotion_pipeline = pipeline(
                "text-classification", 
                model="cointegrated/rubert-tiny2-cedr-emotion-detection", 
                device=device,
                return_all_scores=True
            )
        return self._emotion_pipeline

# Singleton instance
models = ModelCache()

def get_sentence_model(quality="high"):
    return models.get_sentence_model(quality)

def get_sentiment_pipeline():
    return models.sentiment_pipeline

def get_emotion_pipeline():
    return models.emotion_pipeline
