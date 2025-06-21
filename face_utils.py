from io import BytesIO

import insightface
import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image

# Load model once
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0)

def get_embedding(img_bytes: bytes) -> np.ndarray:
    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img_np = np.array(img)
        faces = app.get(img_np)
        if not faces:
            raise ValueError("❌ No face detected.")
        return faces[0].embedding
    except Exception as e:
        raise ValueError(f"Face processing failed: {e}")

def cosine(v1: np.ndarray, v2: np.ndarray) -> float:
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
