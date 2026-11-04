"""CLI for training the cognitive text classifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.cognitive.neural_model import train_model
from app.config import BASE_DIR, get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Train the AletheiaOS cognitive text model")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=BASE_DIR / "app" / "cognitive" / "training_data.json",
        help="JSON examples with text and label; optional context and actions fields",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.cognitive_model_path,
        help="Output path for the trained model checkpoint",
    )
    parser.add_argument("--epochs", type=int, default=100)
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be positive")

    metrics = train_model(args.dataset, args.output, args.epochs)
    print(json.dumps({**metrics, "checkpoint": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()