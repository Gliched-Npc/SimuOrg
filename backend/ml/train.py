# backend/ml/train.py
# Run this to train all models and generate calibration in one step.
# Usage: python -m backend.ml.train

from backend.ml.attrition_model import train_attrition_model
from backend.ml.burnout_estimator import train_burnout_estimator
from backend.ml.calibration import calibrate


def train_all():
    print("=" * 50)
    print("🚀 SimuOrg ML Training Pipeline")
    print("=" * 50)

    print("\n[1/3] Training attrition model...")
    train_attrition_model()

    print("\n[2/3] Training burnout estimator...")
    train_burnout_estimator()

    print("\n[3/3] Running calibration...")
    calibrate()

    print("\n" + "=" * 50)
    print("✅ All models trained and calibration complete.")
    print("   Ready to run simulations.")
    print("=" * 50)


if __name__ == "__main__":
    train_all()