"""ML signal strategy: standardize -> PCA(>=80% var) -> Random Forest -> signal.

The fitted scaler, PCA and model travel together so the live paper-trading script
transforms new data exactly the way training did.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier

from . import config
from .indicators import FEATURE_COLUMNS


@dataclass
class TradingModel:
    scaler: StandardScaler
    pca: PCA
    model: RandomForestClassifier
    feature_columns: list

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        return self.pca.transform(self.scaler.transform(X[self.feature_columns]))

    def predict_proba_up(self, X: pd.DataFrame) -> np.ndarray:
        """Probability that next-day return is positive (class 1)."""
        return self.model.predict_proba(self.transform(X))[:, 1]


def train_signal_model(X_train: pd.DataFrame, y_train: pd.Series) -> TradingModel:
    """Fit StandardScaler -> PCA(>=80% variance) -> RandomForest on the training set."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    pca = PCA(n_components=config.PCA_VARIANCE_TARGET, svd_solver="full")
    X_pca = pca.fit_transform(X_scaled)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=20,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_pca, y_train)

    return TradingModel(scaler=scaler, pca=pca, model=model, feature_columns=list(FEATURE_COLUMNS))


def generate_signal(tm: TradingModel, X: pd.DataFrame) -> pd.Series:
    """Long (1) when P(up) > threshold, else flat (0)."""
    proba = tm.predict_proba_up(X)
    return pd.Series((proba > config.SIGNAL_THRESHOLD).astype(int), index=X.index, name="signal")
