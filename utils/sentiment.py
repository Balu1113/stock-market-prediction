"""News headline sentiment via VADER (falls back to a tiny lexicon if absent)."""

import re

FALLBACK_LEXICON = {
    'surge': 2.5, 'surges': 2.5, 'soar': 2.5, 'rally': 2.0, 'rallies': 2.0,
    'gain': 1.5, 'gains': 1.5, 'profit': 1.5, 'record': 1.2, 'upgrade': 1.8,
    'bullish': 1.8, 'breakout': 1.5, 'buy': 1.0, 'strong': 1.2, 'beat': 1.5,
    'dividend': 0.8, 'growth': 1.0, 'jump': 1.5, 'high': 0.3,
    'fall': -1.8, 'falls': -1.8, 'drop': -1.8, 'drops': -1.8, 'plunge': -2.5,
    'crash': -3.0, 'loss': -1.5, 'losses': -1.5, 'downgrade': -1.8,
    'bearish': -1.8, 'weak': -1.2, 'miss': -1.5, 'lawsuit': -1.8,
    'probe': -1.5, 'fraud': -2.5, 'recall': -1.2, 'sell': -1.0, 'warning': -1.5,
}

_analyzer = None
_tried = False


def _get_analyzer():
    global _analyzer, _tried
    if _tried:
        return _analyzer
    _tried = True
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        import nltk
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
        _analyzer = SentimentIntensityAnalyzer()
    except Exception:
        _analyzer = None
    return _analyzer


def score_text(text: str) -> float:
    """Compound sentiment in [-1, 1]."""
    text = (text or '').strip()
    if not text:
        return 0.0
    analyzer = _get_analyzer()
    if analyzer is not None:
        return float(analyzer.polarity_scores(text)['compound'])

    words = re.findall(r"[a-z']+", text.lower())
    if not words:
        return 0.0
    total = sum(FALLBACK_LEXICON.get(word, 0.0) for word in words)
    return max(-1.0, min(1.0, total / 5.0))


def label_for(score: float) -> str:
    if score >= 0.15:
        return 'positive'
    if score <= -0.15:
        return 'negative'
    return 'neutral'
