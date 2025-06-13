import numpy as np
import matplotlib.pyplot as plt

# Generate a grass-like noise texture
width, height = 32, 32
red = np.random.randint(110, 140, (height, width))
green = np.random.randint(120, 130, (height, width))
blue = np.random.randint(110, 135, (height, width))

# Stack into RGB image
grass = np.stack((red, green, blue), axis=2).astype(np.uint8)

# Save to file
output_path = 'pyfloor_tile_32.png'
plt.imsave(output_path, grass)


