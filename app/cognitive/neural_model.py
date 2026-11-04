"""Train and run a compact PyTorch text classifier for cognitive perceptions."""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def _feature_tokens(text: str, context: dict[str, Any] | None = None) -> list[str]:
    tokens = tokenize(text)
    for key, value in sorted((context or {}).items()):
        tokens.extend(("context", *tokenize(key), *tokenize(str(value))))
    return tokens


def _network(
    torch: Any,
    vocab_size: int,
    label_count: int,
    action_count: int,
    embedding_dim: int,
    hidden_dim: int,
):
    class TextClassifier(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = torch.nn.EmbeddingBag(vocab_size, embedding_dim, mode="mean")
            self.shared = torch.nn.Sequential(
                torch.nn.Linear(embedding_dim, hidden_dim),
                torch.nn.ReLU(),
                torch.nn.Dropout(0.2),
            )
            self.label_head = torch.nn.Linear(hidden_dim, label_count)
            self.action_head = torch.nn.Linear(hidden_dim, action_count)

        def forward(self, token_ids: Any, offsets: Any) -> tuple[Any, Any]:
            features = self.shared(self.embedding(token_ids, offsets))
            return self.label_head(features), self.action_head(features)

    return TextClassifier()


class NeuralInferenceModel:
    def __init__(self, checkpoint_path: str | Path) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self._torch: Any = None
        self._model: Any = None
        self._vocabulary: dict[str, int] = {}
        self._labels: list[str] = []
        self._actions: list[str] = []
        self._unavailable_logged = False
        self._load_failed = False

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        if not self.checkpoint_path.is_file():
            return False

        try:
            import torch
        except ImportError:
            if not self._unavailable_logged:
                logger.warning("PyTorch is unavailable; neural inference is disabled")
                self._unavailable_logged = True
            return False

        checkpoint = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
        if checkpoint.get("format_version") != 2:
            logger.warning("Cognitive model checkpoint is outdated; retrain the model")
            self._load_failed = True
            return False
        self._vocabulary = checkpoint["vocabulary"]
        self._labels = checkpoint["labels"]
        self._actions = checkpoint["actions"]
        self._torch = torch
        self._model = _network(
            torch,
            len(self._vocabulary),
            len(self._labels),
            len(self._actions),
            checkpoint["embedding_dim"],
            checkpoint["hidden_dim"],
        )
        self._model.load_state_dict(checkpoint["state_dict"])
        self._model.eval()
        logger.info("Loaded cognitive model checkpoint from %s", self.checkpoint_path)
        return True

    def predict(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, float, list[str]] | None:
        if not self._load():
            return None

        token_ids = [
            self._vocabulary[token]
            for token in _feature_tokens(text, context)
            if token in self._vocabulary
        ]
        if not token_ids:
            return None

        torch = self._torch
        with torch.inference_mode():
            label_logits, action_logits = self._model(
                torch.tensor(token_ids, dtype=torch.long),
                torch.tensor([0], dtype=torch.long),
            )
            label_probabilities = torch.softmax(label_logits[0], dim=0)
            action_probabilities = torch.sigmoid(action_logits[0])
            index = int(torch.argmax(label_probabilities).item())
            actions = [
                action
                for action, probability in zip(self._actions, action_probabilities)
                if action != "__no_action__" and float(probability.item()) >= 0.6
            ]
        return self._labels[index], float(label_probabilities[index].item()), actions


@lru_cache(maxsize=4)
def get_neural_model(checkpoint_path: str) -> NeuralInferenceModel:
    return NeuralInferenceModel(checkpoint_path)


def train_model(
    dataset_path: str | Path,
    output_path: str | Path,
    epochs: int = 100,
) -> dict[str, float | int]:
    """Train condition and action heads from JSON {text, label, context, actions} records."""
    import torch

    with Path(dataset_path).open(encoding="utf-8") as dataset_file:
        samples = json.load(dataset_file)
    if not isinstance(samples, list) or not samples:
        raise ValueError("Training data must be a non-empty JSON array")

    labels = sorted({sample["label"] for sample in samples})
    actions = sorted({action for sample in samples for action in sample.get("actions", [])})
    if not actions:
        actions = ["__no_action__"]
    sample_tokens = [
        _feature_tokens(sample["text"], sample.get("context")) for sample in samples
    ]
    vocabulary = {
        token: index
        for index, token in enumerate(sorted({token for tokens in sample_tokens for token in tokens}))
    }
    if len(labels) < 2 or not vocabulary:
        raise ValueError("Training data must contain at least two labels and vocabulary terms")

    label_ids = {label: index for index, label in enumerate(labels)}
    offsets: list[int] = []
    flattened_tokens: list[int] = []
    targets: list[int] = []
    action_targets: list[list[float]] = []
    action_ids = {action: index for index, action in enumerate(actions)}
    for sample, tokens in zip(samples, sample_tokens):
        offsets.append(len(flattened_tokens))
        flattened_tokens.extend(vocabulary[token] for token in tokens)
        targets.append(label_ids[sample["label"]])
        target_actions = set(sample.get("actions", []))
        action_targets.append(
            [float(action in target_actions) for action in actions]
        )
    if any(start == end for start, end in zip(offsets, offsets[1:] + [len(flattened_tokens)])):
        raise ValueError("Every training example must contain at least one token")

    torch.manual_seed(17)
    embedding_dim = 32
    hidden_dim = 64
    model = _network(
        torch, len(vocabulary), len(labels), len(actions), embedding_dim, hidden_dim
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    loss_function = torch.nn.CrossEntropyLoss()
    action_loss_function = torch.nn.BCEWithLogitsLoss()
    token_tensor = torch.tensor(flattened_tokens, dtype=torch.long)
    offset_tensor = torch.tensor(offsets, dtype=torch.long)
    target_tensor = torch.tensor(targets, dtype=torch.long)
    action_target_tensor = torch.tensor(action_targets, dtype=torch.float32)

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        label_logits, action_logits = model(token_tensor, offset_tensor)
        loss = loss_function(label_logits, target_tensor) + action_loss_function(
            action_logits, action_target_tensor
        )
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.inference_mode():
        label_logits, action_logits = model(token_tensor, offset_tensor)
        predictions = label_logits.argmax(dim=1)
        accuracy = float((predictions == target_tensor).float().mean().item())
        action_predictions = torch.sigmoid(action_logits) >= 0.6
        action_accuracy = float(
            (action_predictions == action_target_tensor.bool()).float().mean().item()
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "format_version": 2,
            "state_dict": model.state_dict(),
            "vocabulary": vocabulary,
            "labels": labels,
            "actions": actions,
            "embedding_dim": embedding_dim,
            "hidden_dim": hidden_dim,
        },
        output,
    )
    return {
        "samples": len(samples),
        "labels": len(labels),
        "actions": len(actions),
        "training_accuracy": accuracy,
        "action_training_accuracy": action_accuracy,
    }