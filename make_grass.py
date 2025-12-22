import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

# -------------------------
# Tile size
# -------------------------
width, height = 128, 128
rng = np.random.default_rng()  # better RNG

# -------------------------
# Helpers
# -------------------------
def norm01(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    return (a - a.min()) / (np.ptp(a) + 1e-6)

def wrapped_blur(a: np.ndarray, sigma):
    # mode="wrap" is the key to seamless tiling
    return gaussian_filter(a, sigma=sigma, mode="wrap")

# -------------------------
# Base grass color (float)
# -------------------------
base_green = rng.uniform(125, 165)
base = np.zeros((height, width, 3), dtype=np.float32)
base[..., 1] = base_green
base[..., 0] = base_green * 0.45
base[..., 2] = base_green * 0.45

# -------------------------
# Seamless noise layers
# -------------------------
low = wrapped_blur(rng.random((height, width)), sigma=6)
low = norm01(low)

high = wrapped_blur(rng.random((height, width)), sigma=1)
high = norm01(high)

# Blade directionality: blur more along x than y (or vice versa)
# To suggest blades, streak primarily in one axis.
blade = wrapped_blur(rng.random((height, width)), sigma=(0.6, 2.8))
blade = norm01(blade)

# Combine
variation = 0.60 * low + 0.30 * high + 0.10 * blade
variation = norm01(variation)

# -------------------------
# Periodic lighting (tileable)
# -------------------------
# Cosine fields repeat at edges -> seamless
yy = np.linspace(0, 2 * np.pi, height, endpoint=False)[:, None]
xx = np.linspace(0, 2 * np.pi, width,  endpoint=False)[None, :]

light = (
    1.0
    + 0.03 * np.cos(yy)          # gentle vertical lighting
    + 0.02 * np.cos(xx * 1.0)    # gentle horizontal lighting
    + 0.01 * np.cos(xx + yy)     # subtle diagonal variation
).astype(np.float32)

variation = np.clip(variation * light, 0.0, 1.0)

# -------------------------
# Apply variation
# -------------------------
grass = base * (0.78 + 0.42 * variation[..., None])

# -------------------------
# Tileable color jitter derived from seamless noise
# -------------------------
# Instead of independent random jitter per channel, use wrapped noise so edges match.
hue_noise = wrapped_blur(rng.random((height, width)), sigma=2)
hue_noise = norm01(hue_noise)

grass[..., 1] *= (0.95 + 0.10 * hue_noise)   # green varies most
grass[..., 0] *= (0.90 + 0.06 * hue_noise)
grass[..., 2] *= (0.90 + 0.06 * hue_noise)

grass = np.clip(grass, 0, 255).astype(np.uint8)
plt.imsave("pygrass_tile.png", grass)

# Optional: quick visual sanity check (writes a 5x5 tiled preview)
preview = np.tile(grass, (5, 5, 1))
plt.imsave("pygrass_tile_preview_5x5.png", preview)
