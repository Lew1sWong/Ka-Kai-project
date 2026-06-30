from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from mirrorquant_demo.train_vqvae import VQVAE


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def parse_args():
    parser = argparse.ArgumentParser(description="Encode all training windows with the VQ-VAE model.")
    parser.add_argument(
        "--market",
        choices=["us", "cn"],
        default="us",
        help="Market to encode for. Determines input/output file paths.",
    )
    return parser.parse_args()


def _paths(market: str):
    suffix = "_cn" if market == "cn" else ""
    return (
        DATA_DIR / f"training_windows{suffix}.npz",
        DATA_DIR / f"training_windows_meta{suffix}.csv",
        DATA_DIR / f"vqvae_model{suffix}.pt",
        DATA_DIR / f"window_embeddings{suffix}.npz",
        DATA_DIR / f"window_embedding_meta{suffix}.csv",
    )


def load_model_bundle(model_path: Path):
    bundle = torch.load(model_path, map_location="cpu", weights_only=False)
    return bundle


def load_windows(windows_path: Path, meta_path: Path):
    data = np.load(windows_path)
    X = data["X"].astype(np.float32)
    meta_df = pd.read_csv(meta_path)
    return X, meta_df


def normalize_windows(X: np.ndarray, mean: np.ndarray, std: np.ndarray):
    return (X - mean) / std


def flatten_windows(X: np.ndarray):
    return X.reshape(X.shape[0], -1)


def encode_all_windows(model: VQVAE, X_flat: np.ndarray):
    model.eval()

    x_tensor = torch.tensor(X_flat, dtype=torch.float32)

    with torch.no_grad():
        z_e = model.encoder(x_tensor)
        z_q, _, _, code_indices = model.quantizer(z_e)

    embeddings = z_q.cpu().numpy()
    codes = code_indices.cpu().numpy()

    return embeddings, codes


def main():
    args = parse_args()
    windows_path, meta_path, model_path, embeddings_path, output_meta_path = _paths(args.market)

    for path in (windows_path, meta_path, model_path):
        if not path.exists():
            raise SystemExit(
                f"Required file not found: {path}\n"
                f"Run build_training_data.py and train_vqvae.py --market {args.market} first."
            )

    bundle = load_model_bundle(model_path)

    mean = bundle["mean"]
    std = bundle["std"]
    input_dim = bundle["input_dim"]
    latent_dim = bundle["latent_dim"]
    num_codes = bundle["num_codes"]

    X, meta_df = load_windows(windows_path, meta_path)
    X_norm = normalize_windows(X, mean, std)
    X_flat = flatten_windows(X_norm)

    model = VQVAE(
        input_dim=input_dim,
        latent_dim=latent_dim,
        num_codes=num_codes,
    )
    model.load_state_dict(bundle["model_state_dict"])

    embeddings, codes = encode_all_windows(model, X_flat)

    np.savez_compressed(
        embeddings_path,
        embeddings=embeddings,
        codes=codes,
    )

    meta_df = meta_df.copy()
    meta_df["code"] = codes
    meta_df.to_csv(output_meta_path, index=False)

    print(f"Encoded windows for market={args.market}")
    print("Embeddings shape:", embeddings.shape)
    print("Codes shape:", codes.shape)
    print("Saved embeddings to:", embeddings_path)
    print("Saved metadata to:", output_meta_path)


if __name__ == "__main__":
    main()
