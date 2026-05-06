"""
PhoBERT-based Aspect-Based Sentiment Analysis (ABSA) Module
===========================================================

This module implements TRUE ABSA: linking sentiment directly to each detected aspect.

Methodology:
    1. For each detected aspect in a comment, extract a context window around the aspect keyword
    2. Use PhoBERT (vinai/phobert-base) to encode the context
    3. A classification head predicts sentiment (Positive/Negative/Neutral) per aspect

Example:
    Input:  "Pin rất tốt nhưng dịch vụ quá tệ"
    Aspects detected: [BATTERY_CHARGING, SERVICE_AFTERSALES]

    Context for BATTERY_CHARGING ("pin"): "pin rất tốt"    → Positive
    Context for SERVICE_AFTERSALES ("dịch_vụ"): "dịch_vụ quá tệ" → Negative

    Output: {"BATTERY_CHARGING": 1, "SERVICE_AFTERSALES": -1}
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np

LOG = logging.getLogger("ev.absa")

# ── Lazy imports for heavy libraries ──────────────────────────────────────────
_TORCH_AVAILABLE = False
_TRANSFORMERS_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    LOG.warning("PyTorch not available. ABSA will fall back to rule-based mode.")

try:
    from transformers import AutoTokenizer, AutoModel
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    LOG.warning("Transformers not available. ABSA will fall back to rule-based mode.")


# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def extract_aspect_context(
    tokens: List[str],
    aspect_keywords: List[str],
    window_size: int = 7,
) -> str:
    """
    Extract a context window around aspect keywords in tokenized text.

    Args:
        tokens: List of word tokens from processed text
        aspect_keywords: Keywords that identify the aspect
        window_size: Number of tokens to include on each side of the keyword

    Returns:
        Context string containing tokens around the aspect mention
    """
    context_tokens = []
    token_lower = [t.lower() for t in tokens]

    for i, tok in enumerate(token_lower):
        for kw in aspect_keywords:
            if kw in tok or tok in kw:
                start = max(0, i - window_size)
                end = min(len(tokens), i + window_size + 1)
                context_tokens.extend(tokens[start:end])
                break

    if not context_tokens:
        return ""

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in context_tokens:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return " ".join(unique)


# ══════════════════════════════════════════════════════════════════════════════
# PhoBERT ASPECT SENTIMENT CLASSIFIER
# ══════════════════════════════════════════════════════════════════════════════

class PhoBERTAspectSentimentClassifier(nn.Module if _TORCH_AVAILABLE else object):
    """
    PhoBERT-based classifier for aspect-level sentiment analysis.

    Architecture:
        PhoBERT (frozen/fine-tuned) → [CLS] token → Dropout → Linear → 3-class softmax
        Classes: Negative (-1), Neutral (0), Positive (1)
    """

    def __init__(self, model_name: str = "vinai/phobert-base", num_classes: int = 3,
                 dropout: float = 0.3, freeze_bert: bool = False):
        if not _TORCH_AVAILABLE or not _TRANSFORMERS_AVAILABLE:
            raise RuntimeError("PyTorch and Transformers are required for PhoBERT ABSA.")

        super().__init__()
        self.phobert = AutoModel.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        hidden_size = self.phobert.config.hidden_size  # 768 for phobert-base

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
            nn.Linear(256, num_classes),
        )

        if freeze_bert:
            for param in self.phobert.parameters():
                param.requires_grad = False

        self.label_map = {0: -1, 1: 0, 2: 1}  # class_idx → sentiment_label
        self.reverse_label_map = {-1: 0, 0: 1, 1: 2}

    def forward(self, input_ids, attention_mask):
        outputs = self.phobert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        logits = self.classifier(cls_output)
        return logits

    def predict_sentiment(self, text: str, device: str = "cpu") -> int:
        """Predict sentiment for a single text. Returns -1, 0, or 1."""
        self.eval()
        encoding = self.tokenizer(
            text, return_tensors="pt", max_length=128,
            truncation=True, padding="max_length"
        )
        input_ids = encoding["input_ids"].to(device)
        attention_mask = encoding["attention_mask"].to(device)

        with torch.no_grad():
            logits = self.forward(input_ids, attention_mask)
            pred_class = torch.argmax(logits, dim=1).item()

        return self.label_map[pred_class]


# ══════════════════════════════════════════════════════════════════════════════
# RULE-BASED FALLBACK SENTIMENT (when PhoBERT is unavailable)
# ══════════════════════════════════════════════════════════════════════════════

class RuleBasedAspectSentiment:
    """
    Fallback rule-based aspect sentiment using lexicon matching.
    Used when PhoBERT/PyTorch is not available.
    """

    def __init__(self, positive_lexicon: frozenset, negative_lexicon: frozenset,
                 negation_particles: frozenset):
        self.pos = positive_lexicon
        self.neg = negative_lexicon
        self.negators = negation_particles

    def predict_sentiment(self, text: str) -> int:
        """Predict sentiment for text using lexicon + negation handling."""
        tokens = text.lower().split()
        pos_count = 0
        neg_count = 0
        negate_next = False

        for tok in tokens:
            if tok in self.negators:
                negate_next = True
                continue

            if tok in self.pos:
                if negate_next:
                    neg_count += 1
                    negate_next = False
                else:
                    pos_count += 1
            elif tok in self.neg:
                if negate_next:
                    pos_count += 1
                    negate_next = False
                else:
                    neg_count += 1
            else:
                negate_next = False

        if pos_count > neg_count:
            return 1
        elif neg_count > pos_count:
            return -1
        else:
            return 0


# ══════════════════════════════════════════════════════════════════════════════
# ASPECT-BASED SENTIMENT ANALYZER (Main Interface)
# ══════════════════════════════════════════════════════════════════════════════

class AspectSentimentAnalyzer:
    """
    Main ABSA interface. Supports two modes:
    1. PhoBERT mode (default) — uses fine-tuned PhoBERT for aspect sentiment
    2. Rule-based mode (fallback) — uses lexicon-based sentiment per aspect

    Usage:
        analyzer = AspectSentimentAnalyzer(aspect_map, pos_lexicon, neg_lexicon, negation)
        analyzer.load_model("artifacts/models/phobert_absa.pt")  # optional

        result = analyzer.analyze(
            processed_text="pin rất tốt nhưng dịch_vụ quá tệ",
            detected_aspects=["BATTERY_CHARGING", "SERVICE_AFTERSALES"]
        )
        # result = {"BATTERY_CHARGING": 1, "SERVICE_AFTERSALES": -1}
    """

    def __init__(
        self,
        aspect_map: Dict[str, List[str]],
        positive_lexicon: frozenset,
        negative_lexicon: frozenset,
        negation_particles: frozenset,
        window_size: int = 7,
        model_path: Optional[str] = None,
        device: str = "cpu",
    ):
        self.aspect_map = aspect_map
        self.window_size = window_size
        self.device = device
        self.mode = "rule-based"  # default

        # Always initialize rule-based as fallback
        self.rule_based = RuleBasedAspectSentiment(
            positive_lexicon, negative_lexicon, negation_particles
        )

        # Try to load PhoBERT model
        self.phobert_model = None
        if model_path and os.path.exists(model_path):
            self._load_phobert(model_path)
        elif _TORCH_AVAILABLE and _TRANSFORMERS_AVAILABLE:
            try:
                self.phobert_model = PhoBERTAspectSentimentClassifier(
                    freeze_bert=True
                )
                self.phobert_model.to(device)
                self.mode = "phobert-pretrained"
                LOG.info("✅ PhoBERT ABSA initialized (pretrained, not fine-tuned)")
            except Exception as e:
                LOG.warning("⚠️ PhoBERT init failed: %s. Using rule-based mode.", e)

    def _load_phobert(self, model_path: str):
        """Load a fine-tuned PhoBERT ABSA model."""
        try:
            self.phobert_model = PhoBERTAspectSentimentClassifier()
            state = torch.load(model_path, map_location=self.device)
            self.phobert_model.load_state_dict(state)
            self.phobert_model.to(self.device)
            self.phobert_model.eval()
            self.mode = "phobert-finetuned"
            LOG.info("✅ PhoBERT ABSA model loaded from %s", model_path)
        except Exception as e:
            LOG.warning("⚠️ Failed to load PhoBERT model: %s. Using rule-based.", e)
            self.phobert_model = None

    def analyze(
        self,
        processed_text: str,
        detected_aspects: List[str],
        raw_text: str = "",
    ) -> Dict[str, int]:
        """
        Perform ABSA: predict sentiment for each detected aspect.

        Args:
            processed_text: NLP-processed text (segmented, normalized)
            detected_aspects: List of aspect names detected in this text
            raw_text: Original text (used for PhoBERT tokenization)

        Returns:
            Dict mapping aspect_name → sentiment (-1, 0, 1)
        """
        if not detected_aspects:
            return {}

        tokens = processed_text.split()
        result = {}

        for aspect in detected_aspects:
            keywords = self.aspect_map.get(aspect, [])
            if not keywords:
                continue

            # Extract context window around aspect keywords
            context = extract_aspect_context(tokens, keywords, self.window_size)

            if not context:
                result[aspect] = 0  # No context → neutral
                continue

            # Use PhoBERT if available, otherwise rule-based
            if self.phobert_model is not None:
                try:
                    sentiment = self.phobert_model.predict_sentiment(
                        context, self.device
                    )
                except Exception:
                    sentiment = self.rule_based.predict_sentiment(context)
            else:
                sentiment = self.rule_based.predict_sentiment(context)

            result[aspect] = sentiment

        return result

    def train_on_synthetic(
        self,
        texts: List[str],
        labels: List[int],
        epochs: int = 5,
        batch_size: int = 16,
        learning_rate: float = 2e-5,
        save_path: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Fine-tune PhoBERT on labeled data (e.g., from SyntheticDataGenerator).

        Args:
            texts: List of context text segments
            labels: List of sentiment labels (-1, 0, 1)
            epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate for optimizer
            save_path: Path to save the fine-tuned model

        Returns:
            Dict with training metrics (loss, accuracy per epoch)
        """
        if not _TORCH_AVAILABLE or not _TRANSFORMERS_AVAILABLE:
            LOG.error("PyTorch/Transformers required for training.")
            return {}

        from torch.utils.data import DataLoader, TensorDataset

        # Initialize fresh model for training
        model = PhoBERTAspectSentimentClassifier(freeze_bert=False)
        model.to(self.device)
        tokenizer = model.tokenizer

        # Convert labels: -1→0, 0→1, 1→2
        label_tensor = torch.tensor(
            [model.reverse_label_map[l] for l in labels], dtype=torch.long
        )

        # Tokenize all texts
        encodings = tokenizer(
            texts, return_tensors="pt", max_length=128,
            truncation=True, padding="max_length"
        )

        dataset = TensorDataset(
            encodings["input_ids"], encodings["attention_mask"], label_tensor
        )
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
        criterion = nn.CrossEntropyLoss()

        metrics = {"epoch_losses": [], "epoch_accuracies": []}

        LOG.info("🚀 Starting PhoBERT ABSA fine-tuning: %d samples, %d epochs", len(texts), epochs)

        for epoch in range(epochs):
            model.train()
            total_loss = 0
            correct = 0
            total = 0

            for batch_ids, batch_mask, batch_labels in loader:
                batch_ids = batch_ids.to(self.device)
                batch_mask = batch_mask.to(self.device)
                batch_labels = batch_labels.to(self.device)

                optimizer.zero_grad()
                logits = model(batch_ids, batch_mask)
                loss = criterion(logits, batch_labels)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                preds = torch.argmax(logits, dim=1)
                correct += (preds == batch_labels).sum().item()
                total += len(batch_labels)

            avg_loss = total_loss / len(loader)
            accuracy = correct / total
            metrics["epoch_losses"].append(avg_loss)
            metrics["epoch_accuracies"].append(accuracy)
            LOG.info("  Epoch %d/%d — Loss: %.4f, Accuracy: %.4f", epoch + 1, epochs, avg_loss, accuracy)

        # Save model
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), save_path)
            LOG.info("💾 PhoBERT ABSA model saved to %s", save_path)

        # Update instance
        self.phobert_model = model
        self.phobert_model.eval()
        self.mode = "phobert-finetuned"

        return metrics

    @property
    def info(self) -> str:
        return f"AspectSentimentAnalyzer(mode={self.mode}, aspects={len(self.aspect_map)})"
